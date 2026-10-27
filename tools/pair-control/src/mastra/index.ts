// Mastra 진입점. `mastra dev`가 Studio(/)와 이 도구의 작은 관제 화면(/pair)을 같은 localhost 서버로 제공한다.
import path from 'node:path';
import { Mastra } from '@mastra/core/mastra';
import { registerApiRoute } from '@mastra/core/server';
import { LibSQLStore } from '@mastra/libsql';
import { loadConfig } from '../executor/config.ts';
import { Executor, UserError } from '../executor/executor.ts';
import { notifyUser } from '../executor/freeGuard.ts';
import { pairTaskWorkflow, prepareTaskWorkflow } from '../workflow.ts';
import { planTask } from '../executor/prepare.ts';
import { acknowledgeFindings, prepareRevert, preflight, runPush, verifyPush } from '../executor/push.ts';
import { progressDraft, progressItems } from '../executor/progress.ts';
import { setMain, swapBlockers } from '../executor/mainRole.ts';
import { bindRuntime, getExecutor, prepareTask, snapshot, startReview, startTask, resumeStep } from '../runtime.ts';
import { activityOf, archiveFinished, createVenv, discardTask, setArchived, tailPostLog, withdrawApproval } from '../executor/taskControl.ts';
import { extractScope } from '../executor/scope.ts';
import fs from 'node:fs';

const cfg = loadConfig();
const HOST = '127.0.0.1';
const ALLOWED_HOSTS = new Set([`127.0.0.1:${cfg.port}`, `localhost:${cfg.port}`]);
const ALLOWED_ORIGINS = [`http://127.0.0.1:${cfg.port}`, `http://localhost:${cfg.port}`];

const executor = new Executor(cfg, {
  onTrip: (a) => {
    notifyUser('유료 전환 신호 감지 — 서비스 종료', a.detail);
    // 이 실행기가 만든 프로세스만 중단한 뒤 서버를 종료한다. 실행기(start.mjs)가 dev 서버를 정리한다.
    setTimeout(() => process.exit(3), 3500).unref?.();
  },
});
executor.guard.checkEnv();
void executor.refreshProbes();

export const mastra = new Mastra({
  workflows: { pairTaskWorkflow, prepareTaskWorkflow },
  storage: new LibSQLStore({ id: 'pair-control', url: `file:${path.join(cfg.stateDir, 'mastra.db')}` }),
  server: {
    host: HOST,
    port: cfg.port,
    cors: { origin: ALLOWED_ORIGINS, allowMethods: ['GET', 'POST', 'OPTIONS'], credentials: false },
    middleware: [
      async (c: any, next: any) => {
        // DNS rebinding·타 사이트 요청 차단: Host는 localhost만, 상태 변경 요청은 같은 출처 Origin만 허용.
        const host = c.req.header('host') ?? '';
        if (!ALLOWED_HOSTS.has(host)) return c.json({ error: 'host not allowed' }, 403);
        const m = c.req.method;
        if (m !== 'GET' && m !== 'HEAD' && m !== 'OPTIONS') {
          const origin = c.req.header('origin');
          if (origin && !ALLOWED_ORIGINS.includes(origin)) return c.json({ error: 'origin not allowed' }, 403);
          if (c.req.path.startsWith('/pair/api/') && (origin === undefined || c.req.header('x-pair-control') !== '1')) {
            return c.json({ error: 'pair-control 요청 헤더/출처 누락' }, 403);
          }
        }
        await next();
      },
    ],
    apiRoutes: buildRoutes(),
  },
});
bindRuntime(executor, mastra);

function act(fn: (c: any) => Promise<unknown>) {
  return async (c: any) => {
    try { return c.json({ ok: true, data: await fn(c) }); }
    catch (err) {
      const user = err instanceof UserError;
      return c.json({ ok: false, error: user ? err.message : `내부 오류: ${(err as Error).message}` }, user ? 400 : 500);
    }
  };
}

const body = async (c: any) => { try { return await c.req.json(); } catch { return {}; } };

/** 화면 모듈(src/ui/js/*.js)만 정해진 이름 형식으로 제공한다. 경로 조합·다른 폴더 접근은 없다. */
function serveStatic(c: any) {
  const file = String(c.req.param('file'));
  const full = path.join(cfg.toolRoot, 'src', 'ui', 'js', file);
  if (!/^[a-z][a-z-]{0,30}\.js$/.test(file) || !fs.existsSync(full)) return c.text('not found', 404);
  return c.body(fs.readFileSync(full, 'utf8'), 200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
}

function buildRoutes() {
  const ex = () => getExecutor();
  const id = (c: any) => String(c.req.param('id'));
  return [
    registerApiRoute('/pair', { method: 'GET', handler: async (c: any) => c.html(fs.readFileSync(path.join(cfg.toolRoot, 'src', 'ui', 'page.html'), 'utf8')) }),
    registerApiRoute('/pair/static/:file', { method: 'GET', handler: async (c: any) => serveStatic(c) }),
    registerApiRoute('/pair/api/state', { method: 'GET', handler: act(async () => snapshot()) }),
    registerApiRoute('/pair/api/tasks', { method: 'POST', handler: act(async (c) => prepareTask(await body(c))) }),
    registerApiRoute('/pair/api/plan', { method: 'POST', handler: act(async (c) => planTask(ex(), await body(c))) }),
    registerApiRoute('/pair/api/tasks/:id/start', { method: 'POST', handler: act(async (c) => startTask(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/cancel', { method: 'POST', handler: act(async (c) => ex().cancel(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/apply-exit', { method: 'POST', handler: act(async (c) => ex().applyObservedExit(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/ack-unknown', { method: 'POST', handler: act(async (c) => ex().acknowledgeUnknown(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/approve', {
      method: 'POST', handler: act(async (c) => {
        const t = ex().task(id(c)); const { sha } = await body(c);
        const a = await ex().approve(t.taskId, String(sha ?? ''), { requireHandoff: true });
        await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
        return a;
      }),
    }),
    registerApiRoute('/pair/api/tasks/:id/reject', {
      method: 'POST', handler: act(async (c) => {
        const t = ex().task(id(c)); const { reason } = await body(c);
        const prev = t.status;
        const step = prev === 'approved' ? 'integrate-gate' : 'review-gate';
        ex().reject(t.taskId, String(reason ?? '사용자 거절'));
        if (t.runId && (prev === 'approved' || prev === 'review_pending')) await resumeStep(t.runId, step, step === 'review-gate' ? { decision: 'reject', reason } : { action: 'reject', reason });
        return ex().task(t.taskId);
      }),
    }),
    registerApiRoute('/pair/api/tasks/:id/integrate', {
      method: 'POST', handler: act(async (c) => {
        const t = ex().task(id(c));
        if (t.status !== 'approved') throw new UserError(`승인된 상태가 아님(${t.status})`);
        await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
        return ex().task(t.taskId);
      }),
    }),
    registerApiRoute('/pair/api/tasks/:id/unapprove', { method: 'POST', handler: act(async (c) => withdrawApproval(ex(), id(c), resumeStep, startReview)) }),
    registerApiRoute('/pair/api/tasks/:id/archive', { method: 'POST', handler: act(async (c) => setArchived(ex(), id(c), (await body(c)).archived !== false)) }),
    registerApiRoute('/pair/api/tasks/:id/discard', { method: 'POST', handler: act(async (c) => discardTask(ex(), id(c), String((await body(c)).reason ?? ''), resumeStep)) }),
    registerApiRoute('/pair/api/archive-finished', { method: 'POST', handler: act(async () => archiveFinished(ex())) }),
    registerApiRoute('/pair/api/scope', { method: 'POST', handler: act(async (c) => extractScope(String((await body(c)).text ?? ''))) }),
    registerApiRoute('/pair/api/tasks/:id/rereview', { method: 'POST', handler: act(async (c) => startReview(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/diff', { method: 'GET', handler: act(async (c) => ({ diff: await ex().diff(id(c)) })) }),
    registerApiRoute('/pair/api/execs/:id/log', {
      method: 'GET', handler: act(async (c) => ex().logTail(id(c), Number(c.req.query('from') ?? 0))),
    }),
    registerApiRoute('/pair/api/tasks/:id/review', {
      method: 'POST', handler: act(async (c) => {
        const b = await body(c);
        return ex().startReviewJob(id(c), { reviewer: b.reviewer, mode: b.mode === 'real' ? 'real' : 'mock', mockScenario: b.mockScenario });
      }),
    }),
    registerApiRoute('/pair/api/tasks/:id/run-checks', { method: 'POST', handler: act(async (c) => ex().runChecks(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/start-prompt', {
      method: 'POST', handler: act(async (c) => {
        const b = await body(c);
        return ex().startPrompt(id(c), { unattended: b.unattended === true, extraDocs: Array.isArray(b.extraDocs) ? b.extraDocs.map(String) : [] });
      }),
    }),
    registerApiRoute('/pair/api/tasks/:id/handoff', { method: 'POST', handler: act(async (c) => ex().handoffToMain(id(c), { auto: (await body(c)).auto === true })) }),
    registerApiRoute('/pair/api/tasks/:id/handoff-text', { method: 'GET', handler: act(async (c) => ex().readHandoff(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/handoff-confirm', { method: 'POST', handler: act(async (c) => ex().confirmHandoff(id(c), String((await body(c)).note ?? ''))) }),
    registerApiRoute('/pair/api/tasks/:id/handoff-cancel', { method: 'POST', handler: act(async (c) => ex().cancelHandoff(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/finish-manual', { method: 'POST', handler: act(async (c) => ex().finishManual(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/recollect', { method: 'POST', handler: act(async (c) => ex().recollect(id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/create-venv', { method: 'POST', handler: act(async (c) => createVenv(ex(), id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/post-log', { method: 'GET', handler: act(async (c) => tailPostLog(ex(), id(c), String(c.req.query('check') ?? ''), Number(c.req.query('from') ?? 0))) }),
    registerApiRoute('/pair/api/tasks/:id/activity', { method: 'GET', handler: act(async (c) => activityOf(ex(), id(c))) }),
    registerApiRoute('/pair/api/tasks/:id/recheck-env', { method: 'POST', handler: act(async (c) => ex().recheckEnv(id(c))) }),
    registerApiRoute('/pair/api/progress', { method: 'GET', handler: act(async () => progressItems(ex())) }),
    registerApiRoute('/pair/api/progress/draft', { method: 'POST', handler: act(async (c) => progressDraft(ex(), String((await body(c)).id ?? ''))) }),
    registerApiRoute('/pair/api/main/blockers', { method: 'GET', handler: act(async () => ({ blockers: await swapBlockers(ex()) })) }),
    registerApiRoute('/pair/api/main/swap', { method: 'POST', handler: act(async (c) => { const b = await body(c); return setMain(ex(), String(b.agent ?? ''), String(b.reason ?? '')); }) }),
    registerApiRoute('/pair/api/push/preflight', { method: 'POST', handler: act(async () => preflight(ex())) }),
    registerApiRoute('/pair/api/push/ack', { method: 'POST', handler: act(async (c) => { const b = await body(c); return acknowledgeFindings(ex(), Array.isArray(b.fingerprints) ? b.fingerprints.map(String) : []); }) }),
    registerApiRoute('/pair/api/push/run', { method: 'POST', handler: act(async (c) => runPush(ex(), String((await body(c)).confirm ?? ''))) }),
    registerApiRoute('/pair/api/push/verify', { method: 'POST', handler: act(async (c) => verifyPush(ex(), String((await body(c)).id ?? ''))) }),
    registerApiRoute('/pair/api/push/revert-prepare', { method: 'POST', handler: act(async (c) => prepareRevert(ex(), String((await body(c)).id ?? ''))) }),
    registerApiRoute('/pair/api/limit/clear', { method: 'POST', handler: act(async () => ex().clearLimit()) }),
    registerApiRoute('/pair/api/probes', { method: 'POST', handler: act(async () => ex().refreshProbes()) }),
  ];
}

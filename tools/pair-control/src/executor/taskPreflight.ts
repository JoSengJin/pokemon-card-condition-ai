import { limitFor } from './executorPolicy.ts';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { chargeRisks } from './adapters.ts';
import { checkVenv, neededEnv } from './envcheck.ts';
import type { Executor, Task, Check } from './executor.ts';

export async function preflightChecks(taskExecutor: Executor, t: Task): Promise<Check[]> {
  const c: Check[] = [];
  const add = (name: string, ok: boolean, detail: string) => c.push({ name, ok, detail });
  if (!taskExecutor.cfg.repo) { add('설정', false, 'config.repo 미설정'); return c; }
  const wts = await G.worktrees(taskExecutor.cfg.repo);
  const main = wts[0]?.path;
  const integ = taskExecutor.cfg.integration.checkout && fs.existsSync(taskExecutor.cfg.integration.checkout) ? fs.realpathSync.native(taskExecutor.cfg.integration.checkout) : null;
  const wt = wts.find((w) => w.path === t.worktree);
  add('worktree 등록', !!wt, wt ? '저장소 worktree 목록에 있음' : '저장소의 git worktree 목록에 없는 경로');
  add('기본 checkout 분리', t.worktree !== main && t.worktree !== integ, t.worktree === main || t.worktree === integ ? '기본/통합 checkout에서는 병렬 작업을 실행하지 않음' : '별도 worktree');
  if (!wt) return c;
  const branch = await G.currentBranch(t.worktree);
  add('브랜치', branch === t.branch, `현재 ${branch ?? '(detached)'} / 계약 ${t.branch}`);
  const baseOk = !!(await G.revParse(t.worktree, t.baseSha)) && (await G.isAncestor(t.worktree, t.baseSha, 'HEAD'));
  add('기준 SHA', baseOk, baseOk ? `${t.baseSha.slice(0, 12)}…는 HEAD의 조상` : '기준 SHA가 없거나 HEAD의 조상이 아님');
  const op = await G.operationInProgress(t.worktree);
  add('Git 진행 중 작업 없음', !op, op ?? '없음');
  if (t.contractSha) {
    // 실행 준비: worktree가 있어도 자체 가상환경·import 경로가 준비되지 않으면 시작하지 않는다.
    t.envReadiness = await checkVenv(t.worktree, neededEnv(t, t.usesDevelopLock), t.requiredModules);
    for (const e of t.envReadiness.checks) add(`환경: ${e.name}`, e.ok, e.detail);
  }
  if (t.usesDevelopLock) {
    const dev = path.join(t.worktree, 'develop');
    let ok = false; try { fs.accessSync(dev, fs.constants.X_OK); ok = true; } catch { /* missing */ }
    add('./develop 잠금 경로', ok, ok ? '모델·worker 경로 → worktree의 ./develop -- <CLI> 로 실행' : 'worktree에 실행 가능한 ./develop 없음');
  }
  add('과금 신호', !taskExecutor.guardAlert, taskExecutor.guardAlert ? `감지됨: ${taskExecutor.guardAlert.detail}` : '감지 없음(무료 보장 아님)');
  if (t.mode === 'real') {
    // 실제 CLI는 구독 로그인으로만 시작한다. API 키·설정 주입·금지 옵션·한도 상태·사용자 확인 표시를 모두 본다.
    const risks = chargeRisks(t.agent, taskExecutor.cfg, { worktree: t.worktree });
    for (const r of risks) add(`무과금: ${r.code}`, false, `${r.message} → ${r.fix}`);
    if (!risks.length) add('무과금 검사', true, '환경변수·설정에서 API 과금 경로 없음(로그인 방식은 확인 불가 — 사용자 확인 표시에 의존)');
    add('구독 확인 표시', taskExecutor.cfg.confirmedSubscriptionAuth, taskExecutor.cfg.confirmedSubscriptionAuth ? '사용자가 구독 로그인·추가 크레딧 꺼짐을 확인함' : 'config.confirmedSubscriptionAuth=false');
    const lim = limitFor(taskExecutor, t.agent);
    add('구독 한도', !lim, lim ? lim.detail : '한도 도달 없음');
  }
  return c;
}

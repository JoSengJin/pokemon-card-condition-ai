import crypto from 'node:crypto';
import * as G from './git.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { authorize } from './approvalGate.ts';
import { checkout } from './pushConfig.ts';
import { redactText } from './pushTransport.ts';
import { UserError } from './executor.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function executePush(ex: Executor, plan: PushPlan, sessionId?: string, tasks: string[] = []): Promise<PushRecord> {
  const cwd = checkout(ex);
  const owner = crypto.randomUUID();
  if (!ex.locks.acquire('integration', { owner, kind: 'push' })) throw new UserError(`다른 통합·푸시가 진행 중: ${JSON.stringify(ex.locks.holder('integration'))}`);
  try {
    const env = sanitizedChildEnv();
    env.GIT_TERMINAL_PROMPT = '0';
    if (process.env.SSH_AUTH_SOCK) env.SSH_AUTH_SOCK = process.env.SSH_AUTH_SOCK;
    const before = await G.run('git', ['ls-remote', plan.remote, `refs/heads/${plan.branch}`], cwd, 60_000, env);
    const beforeSha = before.code === 0 ? before.stdout.trim().split(/\s+/)[0] : null;
    if (before.code !== 0) throw new UserError(`원격 확인 실패: ${redactText(before.stderr.trim().slice(0, 300))}`);
    if (beforeSha !== plan.remoteHead) throw new UserError('점검 이후 원격이 바뀜 — 다시 점검');
    if (sessionId) {
      for (const id of tasks) authorize(ex, sessionId, 'integrate_task', id);
      authorize(ex, sessionId, 'push_main', plan.branch);
    }
    const command = ['git', 'push', '--porcelain', plan.remote, `${plan.localHead}:refs/heads/${plan.branch}`];
    const rec: PushRecord = {
      id: crypto.randomUUID(), at: new Date().toISOString(), kind: plan.revertOf ? 'revert' : 'push', remote: plan.remote, remoteUrl: plan.remoteUrl, branch: plan.branch,
      preRemoteHead: plan.remoteHead!, pushedSha: plan.localHead, commits: plan.commits.map((c) => c.sha), tasks: plan.tasks, command, status: 'push_unverified', detail: '푸시 실행 중',
      revertOf: plan.revertOf ?? undefined,
    };
    (ex.state.pushes ??= {})[rec.id] = rec;
    ex.state.pushPlan = null;
    ex.audit('push_started', { id: rec.id, sha: rec.pushedSha, kind: rec.kind });
    ex.store.save();
    const r = await G.run('git', command.slice(1), cwd, 120_000, env);
    const out = redactText((r.stdout + (r.stderr ? `\n${r.stderr}` : '')).trim().slice(-600));
    const after = await G.run('git', ['ls-remote', plan.remote, `refs/heads/${plan.branch}`], cwd, 60_000, env);
    const afterSha = after.code === 0 ? after.stdout.trim().split(/\s+/)[0] : null;
    const afterDetail = redactText(after.stderr.trim().slice(0, 300));
    if (r.code !== 0) {
      // 실패해도 원격 상태를 한 번 확인해 기록한다(성공했는데 응답만 실패한 경우 대비). 자동 재시도는 없다.
      rec.status = after.code === 0 && afterSha === rec.pushedSha ? 'push_unverified' : 'push_failed';
      rec.detail = rec.status === 'push_failed' ? `push 실패(code ${r.code}): ${out}` : `push가 오류를 냈지만 원격이 대상 SHA와 같음 — 결과를 직접 확인하세요: ${out}`;
    } else {
      if (after.code === 0 && afterSha === rec.pushedSha) { rec.status = 'pushed_verified'; rec.verifiedAt = new Date().toISOString(); rec.detail = '푸시 후 원격 SHA가 대상 SHA와 일치'; }
      else if (after.code === 0) { rec.status = 'remote_mismatch'; rec.detail = `푸시는 성공했지만 원격 SHA(${afterSha?.slice(0, 12) ?? '없음'})가 대상과 다름 — 다른 푸시가 있었는지 확인`; }
      else { rec.status = 'push_unverified'; rec.detail = `푸시는 성공했지만 사후 확인 실패: ${afterDetail}`; }
    }
    if (rec.revertOf && rec.status === 'pushed_verified') { const o = ex.state.pushes![rec.revertOf]; if (o?.revert) o.revert.pushedAs = rec.id; }
    ex.audit('push_finished', { id: rec.id, status: rec.status });
    ex.store.save();
    return rec;
  } finally { ex.locks.release('integration', 'owner', owner); }
}

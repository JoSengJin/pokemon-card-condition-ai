import { assertMainActive } from './executorPolicy.ts';
import { integrationState } from './integrationSnapshot.ts';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { contractHashAt } from './contractFile.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { checkVenv } from './envcheck.ts';
import { setStatus } from './taskState.ts';
import { runPostChecks } from './verificationPost.ts';
import { UserError } from './errors.ts';
import type { Executor, Task, TaskStatus } from './executor.ts';

export async function integrate(taskExecutor: Executor, taskId: string): Promise<{ outcome: string; detail: string }> {
  assertMainActive(taskExecutor, '통합');
  const t = taskExecutor.task(taskId);
  if (t.status !== 'approved' || !t.approval) throw new UserError(`승인된 상태가 아님(${t.status})`);
  if (taskExecutor.guardAlert) throw new UserError('무료 가드 발동 상태');
  const owner = crypto.randomUUID();
  if (!taskExecutor.locks.acquire('integration', { owner, taskId })) {
    return endIntegration(taskExecutor, t, 'integration_blocked', `다른 통합 진행 중: ${JSON.stringify(taskExecutor.locks.holder('integration'))}`, true);
  }
  try {
    setStatus(taskExecutor, t, 'integrating');
    const a = t.approval;
    const checkout = taskExecutor.cfg.integration.checkout;
    const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
    const s = await integrationState(taskExecutor, t, a.sha);
    const branchNow = await G.currentBranch(checkout);
    const changes: string[] = [];
    if (head !== a.sha) changes.push(`작업 브랜치 SHA 변경 ${a.sha.slice(0, 12)} → ${head?.slice(0, 12)}`);
    if (branchNow !== a.baseBranch) changes.push(`통합 checkout 브랜치 ${branchNow} ≠ ${a.baseBranch}`);
    if (s.baseHead !== a.baseHead) changes.push(`기준 브랜치 이동 ${a.baseHead.slice(0, 12)} → ${s.baseHead?.slice(0, 12)}`);
    if (s.filesHash !== a.filesHash) changes.push('관련 파일 목록 변경');
    if (t.verification?.status !== 'passed' || t.verification.sha !== a.sha) changes.push('작업 테스트 결과가 승인 SHA와 다름');
    const hashAtSha = await contractHashAt(t.worktree, t.taskId, a.sha);
    if (hashAtSha !== a.contractHash || a.contractHash !== t.contractHash) changes.push('작업 계약 변경');
    if (changes.length) {
      t.approval = null;
      return endIntegration(taskExecutor, t, 'integration_refused', `승인 무효화: ${changes.join('; ')}`);
    }
    const dirty = (await G.dirtyFiles(checkout)).filter((f) => !f.startsWith('artifacts/'));
    const op = await G.operationInProgress(checkout);
    if (dirty.length || op) return endIntegration(taskExecutor, t, 'integration_blocked', `통합 checkout이 깨끗하지 않음: ${op ?? dirty.join(', ')}`, true);
    const develop = path.join(checkout, 'develop');
    if (!fs.existsSync(develop)) return endIntegration(taskExecutor, t, 'integration_blocked', '통합 checkout에 ./develop 없음', true);
    // ./develop은 통합 checkout 자체의 .venv/bin/python으로 실행된다.
    const integEnv = await checkVenv(checkout, 'python');
    if (!integEnv.ready) return endIntegration(taskExecutor, t, 'integration_blocked', `통합 checkout 실행 환경 미준비: ${integEnv.checks.filter((c) => !c.ok).map((c) => `${c.name}(${c.detail})`).join(', ')}`, true);
    const commits = await G.commitsBetween(t.worktree, t.baseSha, a.sha);
    const r = await G.run(develop, ['--', 'git', 'cherry-pick', '-x', ...commits], checkout, 120_000, sanitizedChildEnv());
    if (r.code === 0) {
      const newHead = await G.revParse(checkout, 'HEAD');
      const post = await runPostChecks(taskExecutor, t, checkout, develop, { base: a.baseHead, head: newHead!, contract: t.contractSha });
      t.integration = { at: new Date().toISOString(), outcome: 'integrated', detail: r.stdout.slice(-2000), newHead, preHead: a.baseHead, commits, postStatus: post.status, postChecks: post.items };
      if (post.status === 'failed') {
        const bad = post.items.filter((i) => i.status !== 'passed').map((i) => `${i.name}(${i.status}, code ${i.exitCode ?? '-'})`).join(', ');
        return endIntegration(taskExecutor, t, 'integrated_check_failed', `통합은 됐지만 통합 후 검사 실패: ${bad}. 통합 전 ${a.baseHead} / 통합 후 ${newHead}. 자동 되돌림 없음 — 확인 후 사람이 ./develop -- git revert 로 복구`);
      }
      return endIntegration(taskExecutor, t, 'integrated', post.status === 'not_run' ? `통합 완료 → ${newHead} · 통합 후 검사 미지정(미실행)` : `통합 완료 → ${newHead} · 통합 후 검사 ${post.items.length}개 통과`);
    }
    if (/사용 중/.test(r.stderr)) return endIntegration(taskExecutor, t, 'integration_blocked', `./develop 잠금 사용 중: ${r.stderr.trim()}`, true);
    const unmerged = (await G.git(checkout, 'diff', '--name-only', '--diff-filter=U')).stdout.split('\n').filter(Boolean);
    const abort = await G.run(develop, ['--', 'git', 'cherry-pick', '--abort'], checkout, 60_000, sanitizedChildEnv());
    t.integration = { at: new Date().toISOString(), outcome: 'conflict', detail: (r.stderr || r.stdout).slice(-2000), conflictFiles: unmerged, commits };
    t.approval = null;
    return endIntegration(taskExecutor, t, 'integration_conflict', `충돌 파일: ${unmerged.join(', ') || '(확인 불가)'} · cherry-pick --abort ${abort.code === 0 ? '완료' : `실패(code ${abort.code}) — 통합 checkout 직접 확인 필요`}. 자동 ours/theirs·reset 없음.`);
  } finally {
    taskExecutor.locks.release('integration', 'owner', owner);
  }
}

export function endIntegration(taskExecutor: Executor, t: Task, s: TaskStatus, detail: string, keepApproval = false) {
  if (!keepApproval && s !== 'integrated' && s !== 'integrated_check_failed') t.approval = null;
  if (s !== 'integrated' && s !== 'integrated_check_failed') t.integration = { ...(t.integration ?? {}), at: new Date().toISOString(), outcome: s, detail };
  setStatus(taskExecutor, t, keepApproval && s === 'integration_blocked' ? 'approved' : s, detail);
  return { outcome: s, detail };
}

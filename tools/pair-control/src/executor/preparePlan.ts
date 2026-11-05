import * as G from './git.ts';
import { effectiveGroups, conflicts, type ConflictReason } from './contract.ts';
import { OCCUPYING, type Check, type Executor } from './executor.ts';
import { PrepareInput, type Plan } from './prepareInput.ts';
import { inspectPreparedWorktree } from './prepareResume.ts';
import { suggestTaskId, planWorktree } from './prepareWorktree.ts';
import { planContract } from './prepareContract.ts';

export async function planTask(ex: Executor, raw: unknown): Promise<Plan> {
  const checks: Check[] = [];
  const warnings: string[] = [];
  const add = (name: string, ok: boolean, detail: string) => checks.push({ name, ok, detail });
  const fail = (name: string, detail: string): Plan => { add(name, false, detail); return { ok: false, task: null, createWorktree: false, baseRef: '', baseSubject: '', checks, conflicts: [], warnings }; };

  const p = PrepareInput.safeParse(raw);
  if (!p.success) return fail('입력', p.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
  const input = p.data;
  const repo = ex.cfg.repo;
  if (!repo) return fail('설정', 'config.repo 미설정');

  // task ID
  const taskId = input.taskId || (await suggestTaskId(ex, input.agent));
  add('task ID', !ex.state.tasks[taskId], input.taskId ? taskId : `${taskId} (자동 생성)`);

  // 기준 SHA: 기본은 통합 브랜치 HEAD
  const baseRef = input.baseSha ? '직접 지정' : `${ex.cfg.integration.branch} 최신`;
  const baseSha = input.baseSha
    ? (G.FULL_SHA.test(input.baseSha) ? await G.revParse(repo, input.baseSha) : null)
    : await G.revParse(repo, `refs/heads/${ex.cfg.integration.branch}`);
  if (!baseSha) return fail('기준 SHA', input.baseSha ? '40자 커밋 SHA가 아니거나 저장소에 없음' : `${ex.cfg.integration.branch} 브랜치를 읽지 못함`);
  const baseSubject = (await G.git(repo, 'log', '-1', '--format=%s (%cr)', baseSha)).stdout.trim();
  add('기준 SHA', true, `${baseSha.slice(0, 12)} · ${baseRef} · ${baseSubject}`);

  const resume = await inspectPreparedWorktree(ex, input, taskId, baseSha);
  const location = await planWorktree(ex, input, taskId, baseSha, add, resume);
  if ('error' in location) return fail('기존 worktree', location.error);
  const { branch, worktree, createWorktree } = location;

  const { v, envAuto, scopeDefault } = await planContract(ex, input, taskId, branch, worktree, baseSha, add, warnings);

  // 진행 중 작업과의 겹침(배정은 가능, 시작은 그 작업이 끝날 때까지 거절)
  const found: ConflictReason[] = [];
  if (v.success) {
    for (const o of Object.values(ex.state.tasks)) {
      if (OCCUPYING.includes(o.status)) found.push(...conflicts(v.data, o, { a: effectiveGroups(v.data), b: effectiveGroups(o) }));
    }
  }
  if (found.length) warnings.push(`진행 중 작업과 겹침 → 그 작업이 통합/거절될 때까지 시작 불가: ${[...new Set(found.map((c) => `${c.otherTask}(${c.detail})`))].join(', ')}`);
  if (ex.guardAlert) add('무료 가드', false, `발동됨: ${ex.guardAlert.detail}`);

  const ok = checks.every((c) => c.ok);
  return { ok, task: v.success ? v.data : null, createWorktree, baseRef, baseSubject, checks, conflicts: found, warnings, envAuto, scopeDefault };
}

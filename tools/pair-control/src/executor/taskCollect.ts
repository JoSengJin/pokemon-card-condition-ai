import { getTask } from './executorLookup.ts';
import * as G from './git.ts';
import { isAllowed } from './contract.ts';
import { contractHashAt } from './contractFile.ts';
import { UserError } from './errors.ts';
import { setStatus } from './taskState.ts';
import type { Executor, Check } from './executor.ts';

export async function collect(owner: Executor, taskId: string, execId: string | null) {
  const t = getTask(owner, taskId);
  const ex = execId ? owner.state.executions[execId] : null;
  const checks: Check[] = [];
  const add = (name: string, ok: boolean, detail: string) => checks.push({ name, ok, detail });
  if (ex) add('종료코드', ex.exitCode === 0, `code=${ex.exitCode} signal=${ex.signal ?? '-'}${ex.spawnError ? ` spawn=${ex.spawnError}` : ''}`);
  const branchHead = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
  const head = await G.revParse(t.worktree, 'HEAD');
  add('브랜치 HEAD 일치', !!head && head === branchHead, `HEAD ${head?.slice(0, 12)} / ${t.branch} ${branchHead?.slice(0, 12)}`);
  const anc = !!head && (await G.isAncestor(t.worktree, t.contractSha, head));
  add('계약 커밋 위의 작업', anc, anc ? `계약 ${t.contractSha.slice(0, 12)}..HEAD` : '계약 커밋의 후손이 아님');
  const hashNow = head ? await contractHashAt(t.worktree, t.taskId, head) : null;
  add('계약 파일 불변', hashNow === t.contractHash, hashNow === t.contractHash ? '등록 시 계약과 같음' : '계약 파일이 바뀌거나 사라짐(검사·승인 기준 무효)');
  const commits = head && anc ? await G.commitsBetween(t.worktree, t.contractSha, head) : [];
  add('전달 커밋 존재', commits.length > 0, `계약 이후 ${commits.length}개`);
  const changed = head && anc ? await G.changedFiles(t.worktree, t.contractSha, head) : [];
  const dirty = await G.dirtyFiles(t.worktree);
  add('미커밋 변경 없음', dirty.length === 0, dirty.length ? dirty.join(', ') : '깨끗함');
  const outOfScope = [...new Set([...changed, ...dirty])].filter((f) => !isAllowed(f, t.allowedFiles));
  add('허용 파일 범위', outOfScope.length === 0, outOfScope.length ? `범위 밖: ${outOfScope.join(', ')}` : `${changed.length}개 모두 허용 목록 안`);
  const checksPassed = checks.every((c) => c.ok);
  t.result = { execId, headSha: head, commits, changedFiles: changed, dirtyFiles: dirty, outOfScope, checks, checksPassed, collectedAt: new Date().toISOString() };
  const ok = !ex || (ex.exitCode === 0 && ex.status === 'exited');
  setStatus(owner, t, ok ? 'review_pending' : ex?.status === 'cancelled' ? 'cancelled' : 'failed',
    ok ? (checksPassed ? '검토 대기' : '검토 대기(검사 실패 포함 — 승인 불가)') : ex?.status === 'cancelled' ? '사용자 중단' : `종료코드 ${ex?.exitCode ?? '없음'}${ex?.spawnError ? ` (${ex.spawnError})` : ''}`);
  return t.result;
}

export async function recollect(owner: Executor, taskId: string) {
  const t = getTask(owner, taskId);
  if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 다시 수집(${t.status})`);
  if (t.verification?.status === 'running' || t.review?.status === 'running') throw new UserError('작업 테스트나 리뷰가 실행 중');
  return collect(owner, taskId, t.result?.execId ?? null);
}

export async function diff(owner: Executor, taskId: string) {
  const t = getTask(owner, taskId);
  const head = t.result?.headSha;
  if (!head) return '';
  return G.diffText(t.worktree, t.baseSha, head);
}

import { getTask } from './executorLookup.ts';
import { groupAlive } from './processIdentity.ts';
import { UserError } from './errors.ts';
import { setStatus, releaseExecLocks } from './taskState.ts';
import type { Executor } from './executor.ts';

export function acknowledgeUnknown(owner: Executor, taskId: string) {
  const t = getTask(owner, taskId);
  if (t.status !== 'unknown') throw new UserError('결과 불명 상태가 아님');
  const ex = t.lastExecId ? owner.state.executions[t.lastExecId] : null;
  if (ex && groupAlive(owner, ex.pgid)) throw new UserError(`프로세스 그룹 ${ex.pgid}가 아직 살아 있음`);
  if (ex) { ex.status = 'abandoned'; releaseExecLocks(owner, t, ex.execId); }
  setStatus(owner, t, 'abandoned', '사용자가 결과 불명을 확정(완료로 보지 않음)');
}

export async function applyObservedExit(owner: Executor, taskId: string) {
  const t = getTask(owner, taskId);
  if (t.status !== 'exit_observed') throw new UserError('재시작 후 종료 관찰 상태가 아님');
  const ex = owner.state.executions[t.lastExecId!];
  setStatus(owner, t, 'collecting', '사용자 확인 후 결과 반영');
  if (!owner.resumer) throw new UserError('workflow 연결 없음');
  await owner.resumer(ex.runId, 'await-exit', { execId: ex.execId, exitCode: ex.exitCode ?? null, signal: ex.signal ?? null, cancelled: ex.status === 'cancelled' });
}

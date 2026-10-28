// 행동을 호출한 뒤 "실제로 그 결과가 됐는지"를 작업 상태에서 확인한다. 연결부가 예외 없이 돌아왔다는 사실만으로 성공이라고 하지 않는다.
// 문제가 없으면 null, 있으면 사유를 돌려준다.
import type { Executor } from './executor.ts';
import type { MainAction } from './mainTypes.ts';

export function outcomeProblem(ex: Executor, a: MainAction, taskId: string): string | null {
  if (a.type === 'push_main') return null; // 작업이 아니라 원격 상태이며, 검증은 dispatch(pushed_verified 확인)에서 이미 했다
  const t = ex.state.tasks[taskId];
  if (!t) return `${taskId}: 작업이 존재하지 않음`;
  if (a.type === 'assign_task') return a.input?.start !== false && ['assigned', 'blocked'].includes(t.status) ? `${taskId}: 배정됐지만 구현이 시작되지 않음(상태 ${t.status})` : null;
  if (a.type === 'confirm_handoff') return t.handoff?.confirmedAt && t.handoff.headSha === a.sha ? null : `${taskId}: 확인이 기록되지 않음`;
  if (a.type === 'approve_task') return t.status === 'approved' ? null : `${taskId}: 승인되지 않음(상태 ${t.status})`;
  const why = t.statusReason ? ` — ${t.statusReason}` : '';
  if (t.status !== 'integrated') return `${taskId}: 통합되지 않음(상태 ${t.status})${why}`;
  const post = t.integration?.postStatus;
  if (!t.integration?.newHead) return `${taskId}: 통합 HEAD 기록이 없음`;
  if (t.postChecks?.length && post !== 'passed') return `${taskId}: 필수 통합 후 검사가 통과하지 않음(${post ?? '미실행'})`;
  return null;
}

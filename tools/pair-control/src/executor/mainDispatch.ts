import { authorize } from './approvalGate.ts';
import type { RuntimeOrigin } from '../runtimeRequests.ts';
import { confirmHandoff } from './handoffRecords.ts';
// 확인 행동의 마지막 증거를 검사하고 기존 연결 서비스로 직접 넘긴다. 승인 범위 검사는 행동 상태 기계가 먼저 한다.
// 확인(confirm_handoff)은 모델이 diff를 실제로 본 증거(현재 SHA·변경 파일 전체·도구가 계산한 diff 해시·메모)가 맞을 때만 받는다. 그래도 의미 검토 자체를 증명하지는 못한다.
import { assertMainActive } from './executorPolicy.ts';
import crypto from 'node:crypto';
import * as G from './git.ts';
import { UserError, type Executor } from './executor.ts';
import type { MainAction } from './mainTypes.ts';

/** 확인 행동의 증거를 현재 실제 상태와 대조한다. 어긋나면 UserError. */
export async function confirmAction(ex: Executor, a: MainAction, taskId: string, selfReview: boolean, origin?: RuntimeOrigin) {
  assertMainActive(ex, '인계 확인');
  if (origin) authorize(ex, origin.sessionId, origin.action, origin.target, origin.sha, origin);
  const generation = ex.runtime.generation;
  const t = ex.state.tasks[taskId], h = t?.handoff, r = t?.result;
  if (!t || t.status !== 'review_pending' || !h || h.cancelledAt || h.confirmedAt) throw new UserError(`${taskId}: 확인할 수 있는 인계 상태가 아님`);
  const live = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
  if (!r?.headSha || a.sha !== r.headSha || h.headSha !== r.headSha || live !== r.headSha) throw new UserError(`${taskId}: 확인 SHA가 현재 결과·인계·Git과 다름`);
  if (!r.checksPassed || t.verification?.status !== 'passed' || t.verification.sha !== r.headSha) throw new UserError(`${taskId}: 계약 검사·작업 테스트가 현재 SHA에서 통과하지 않음`);
  if (t.agent === ex.mainAgent && !selfReview) throw new UserError(`${taskId}: 구현 에이전트(${t.agent})와 메인이 같아 독립 확인이 아님 — 사용자가 confirm_handoff 승인에 selfReview를 명시해야 함`);
  const seen = [...new Set(a.reviewedFiles ?? [])].sort().join('\n');
  if (!String(a.note ?? '').trim() || seen !== [...r.changedFiles].sort().join('\n')) throw new UserError(`${taskId}: 검토 메모가 없거나 검토한 파일 목록이 변경 파일 전체와 다름`);
  if (a.diffHash !== crypto.createHash('sha256').update((await G.git(t.worktree, 'diff', '--binary', t.baseSha, r.headSha)).stdout).digest('hex')) throw new UserError(`${taskId}: diff 해시가 도구 계산값과 다름 — 실제 diff를 읽은 증거 없음`);
  assertMainActive(ex, '인계 확인', generation);
  if (origin) authorize(ex, origin.sessionId, origin.action, origin.target, origin.sha, origin);
  if (ex.state.tasks[taskId] !== t || t.status !== 'review_pending' || t.handoff !== h || h.cancelledAt || h.confirmedAt || t.result !== r) throw new UserError('준비 중 인계·결과가 바뀜 — 확인하지 않음');
  if (!r.checksPassed || t.verification?.status !== 'passed' || t.verification.sha !== r.headSha || t.verification.contractHash !== t.contractHash) throw new UserError('준비 중 작업 검사 결과가 바뀜 — 확인하지 않음');
  confirmHandoff(ex, taskId, `${t.agent === ex.mainAgent ? '[자기 확인 — 독립 확인 아님] ' : ''}${String(a.note)}`.slice(0, 500));
}

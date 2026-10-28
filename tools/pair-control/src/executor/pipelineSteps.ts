// 모델 없이 도구가 한 번씩만 하는 단계: 구현 결과 도착 뒤 지정 검사 실행 → 통과하면 인계 문서 생성.
// 승인 범위에 덮인 작업만 대상이며, 같은 키(작업+SHA+단계)는 다시 시도하지 않는다(실패·결과 불명도 재시도 없음).
import { covers } from './mainApprovals.ts';
import { pipe } from './pipelineState.ts';
import type { Executor, Task } from './executor.ts';

async function once(ex: Executor, key: string, fn: () => Promise<unknown>) {
  const steps = pipe(ex).steps;
  if (steps[key]) return;
  steps[key] = { at: new Date().toISOString(), ok: false, detail: '수행 중(완료 기록 전에 중단되면 결과 불명 — 재시도하지 않음)' };
  ex.store.save();
  try { await fn(); steps[key].ok = true; steps[key].detail = '완료'; } catch (e) { steps[key].detail = `실패: ${(e as Error).message}`; }
  ex.audit('pipeline_step', { key, ok: steps[key].ok, detail: steps[key].detail });
  ex.store.save();
}

async function advance(ex: Executor, t: Task) {
  const head = t.result?.headSha, v = t.verification;
  if (!head || t.review?.status === 'running') return;
  if (!v || v.sha !== head) return once(ex, `checks:${t.taskId}:${head}`, () => ex.runChecks(t.taskId));
  if (v.status === 'passed' && t.result!.checksPassed && !(t.handoff && !t.handoff.cancelledAt && t.handoff.headSha === head)) await once(ex, `handoff:${t.taskId}:${head}`, () => ex.handoffToMain(t.taskId));
}

export async function autoSteps(ex: Executor, sessionId: string) {
  for (const t of Object.values(ex.state.tasks)) if (t.status === 'review_pending' && covers(ex, sessionId, t.taskId)) await advance(ex, t);
}

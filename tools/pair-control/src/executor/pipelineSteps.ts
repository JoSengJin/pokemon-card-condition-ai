import { handoffToMain } from './handoffCreate.ts';
// 모델 없이 도구가 한 번씩만 하는 단계: 구현 결과 도착 뒤 지정 검사 실행 → 통과하면 인계 문서 생성.
// 준비 권한(prepare_checks 또는 confirm_handoff 승인)이 열린 작업만 대상이며(approve_task 등 다른 승인으로 확대하지 않음),
// 같은 키(작업+SHA+단계)는 다시 시도하지 않는다(실패·결과 불명도 재시도 없음).
import { PREP, whyClosed } from './approvalScope.ts';
import { pipe } from './pipelineState.ts';
import type { Executor, Task } from './executor.ts';

/** 단계 시작을 영속 기록한다. 이미 시도한 키면 false(수행 중 표시만 남은 결과 불명도 다시 하지 않음). */
function begin(ex: Executor, key: string): boolean {
  const steps = pipe(ex).steps;
  if (steps[key]) return false;
  steps[key] = { at: new Date().toISOString(), ok: false, detail: '수행 중(완료 기록 전에 중단되면 결과 불명 — 재시도하지 않음)' };
  ex.store.save();
  return true;
}

function finish(ex: Executor, key: string, err?: Error) {
  const st = pipe(ex).steps[key];
  st.ok = !err; st.detail = err ? `실패: ${err.message}` : '완료';
  ex.audit('pipeline_step', { key, ok: st.ok, detail: st.detail });
  ex.store.save();
}

/** 이 작업에 지금 필요한 도구 단계 하나(없으면 null): 검사가 없거나 다른 SHA면 검사, 통과했는데 인계가 없으면 인계 문서. */
function nextStep(t: Task): { key: string; kind: 'checks' | 'handoff' } | null {
  const head = t.result?.headSha, v = t.verification, h = t.handoff;
  if (!head || t.review?.status === 'running') return null;
  if (!v || v.sha !== head) return { key: `checks:${t.taskId}:${head}`, kind: 'checks' };
  const handedOff = !!h && !h.cancelledAt && h.headSha === head;
  return v.status === 'passed' && t.result!.checksPassed && !handedOff ? { key: `handoff:${t.taskId}:${head}`, kind: 'handoff' } : null;
}

export async function autoSteps(ex: Executor, sessionId: string) {
  for (const t of Object.values(ex.state.tasks)) {
    if (t.status !== 'review_pending' || whyClosed(ex, sessionId, PREP, t.taskId)) continue;
    const step = nextStep(t);
    if (!step || !begin(ex, step.key)) continue;
    try { await (step.kind === 'checks' ? ex.runChecks(t.taskId) : handoffToMain(ex, t.taskId)); finish(ex, step.key); } catch (e) { finish(ex, step.key, e as Error); }
  }
}

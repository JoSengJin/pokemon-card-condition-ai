// 행동 하나를 수행하기 전의 준비: 승인 검사와 실행이 함께 쓸 실제 대상 확정(plan), 결과 불명 대상 차단(uncertain), 결과 기록 형식(note).
import type { Executor } from './executor.ts';
import type { ActionResult, MainAction } from './mainTypes.ts';

export const PENDING = '수행 중(완료 기록 전에 중단되면 결과 불명 — 재실행하지 않음)';

export const note = (id: string, type: string, ok: boolean, detail: string): ActionResult => ({ id, type, ok, detail, at: new Date().toISOString() });

/** 승인 검사와 실행이 함께 쓸 실제 대상을 먼저 확정한다. 배정은 생성될 task ID를 input에 고정해 돌려준다. */
export function plan(ex: Executor, a: MainAction): { target: string; input?: Record<string, unknown> } | { error: string } {
  if (a.type === 'push_main') return { target: String(a.target ?? ex.cfg.integration.branch) };
  if (a.type !== 'assign_task') return { target: a.type === 'run_experiment' ? String(a.target ?? '') : String(a.taskId ?? '') };
  const input: Record<string, unknown> = { ...(a.input ?? {}) };
  if (a.taskId && input.taskId && String(input.taskId) !== a.taskId) return { error: `배정 대상 불일치: 바깥 taskId(${a.taskId})와 input.taskId(${String(input.taskId)})가 일치하지 않음` };
  input.taskId = String(input.taskId ?? a.taskId ?? '');
  if (!input.taskId) return { error: '배정할 task ID가 확정되지 않음' };
  return { target: String(input.taskId), input };
}

/** 완료 여부를 모르는 대상은 확인 전에 다시 건드리지 않는다. 막아야 하면 사유, 아니면 null. */
export function uncertain(ex: Executor, a: MainAction): string | null {
  const t = a.taskId ? ex.state.tasks[a.taskId] : undefined;
  if (t && ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'].includes(t.status)) return `${t.taskId}: 결과 불명·진행 중(${t.status}) — 확인 전 재실행하지 않음`;
  for (const p of Object.values(ex.state.pushes ?? {})) {
    if ((p.status === 'push_unverified' || p.status === 'remote_mismatch') && (a.type === 'push_main' || (a.taskId && p.tasks.includes(a.taskId)))) return `${a.taskId}: push 결과 불명(${p.id.slice(0, 8)}) — 원격 확인 전 재수행하지 않음`;
  }
  return null;
}

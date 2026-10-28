// 새 메인이 낸 행동을 수행한다. 수행 전에 세션·세대, 중복 ID, 결과 불명 대상, 승인 범위를 모두 통과해야 한다.
// 실제 수행은 기존 기능(배정·승인·통합)을 호출하는 쪽이 넘겨 준 MainOps로만 한다. 새 권한을 만들지 않는다.
import { authorize } from './mainApprovals.ts';
import { type Executor } from './executor.ts';
import type { ActionResult, MainAction, MainSession } from './mainTypes.ts';

const note = (id: string, type: string, ok: boolean, detail: string): ActionResult => ({ id, type, ok, detail, at: new Date().toISOString() });

function targetOf(a: MainAction): string {
  return a.type === 'assign_task' ? String(a.input?.taskId ?? a.taskId ?? 'new') : a.type === 'run_experiment' ? String(a.target ?? '') : String(a.taskId ?? '');
}

/** 완료 여부를 모르는 대상은 확인 전에 다시 건드리지 않는다. */
function uncertain(ex: Executor, a: MainAction): string | null {
  const t = a.taskId ? ex.state.tasks[a.taskId] : undefined;
  if (t && ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'].includes(t.status)) return `${t.taskId}: 결과 불명·진행 중(${t.status}) — 확인 전 재실행하지 않음`;
  const p = Object.values(ex.state.pushes ?? {}).find((x) => (x.status === 'push_unverified' || x.status === 'remote_mismatch') && a.taskId && x.tasks.includes(a.taskId));
  return p ? `${a.taskId}: push 결과 불명(${p.id.slice(0, 8)}) — 원격 확인 전 재수행하지 않음` : null;
}

async function runOne(ex: Executor, s: MainSession, a: MainAction): Promise<ActionResult> {
  if (!a.id || !a.type) return note(String(a.id ?? '?'), String(a.type ?? '?'), false, '행동 ID·종류가 없음');
  if (ex.runtime.processed[a.id]) return note(a.id, a.type, false, '중복 행동 ID — 다시 수행하지 않음');
  if (a.type === 'note') return note(a.id, a.type, true, '기록만 함(상태 변경 없음)');
  const hold = uncertain(ex, a);
  if (hold) return note(a.id, a.type, false, hold);
  try { authorize(ex, s.id, a.type, targetOf(a)); } catch (e) { return note(a.id, a.type, false, (e as Error).message); }
  const ops = ex.mainOps;
  try {
    if (a.type === 'approve_task' && ops.approve) { await ops.approve(String(a.taskId), String(a.sha ?? '')); return note(a.id, a.type, true, `${a.taskId} 승인 처리`); }
    if (a.type === 'integrate_task' && ops.integrate) { await ops.integrate(String(a.taskId)); return note(a.id, a.type, true, `${a.taskId} 통합 처리`); }
    if (a.type === 'assign_task' && ops.assign) { await ops.assign(a.input ?? {}); return note(a.id, a.type, true, '작업 배정'); }
  } catch (e) { return note(a.id, a.type, false, `수행 실패: ${(e as Error).message}`); }
  return note(a.id, a.type, false, `지원하지 않거나 연결되지 않은 행동(${a.type}) — 수행하지 않음`);
}

/** 세션이 현재 유효할 때만 행동을 순서대로 수행하고, 각 결과를 장부(processed)와 세션에 기록한다. 늦게 도착한 이전 세션은 아무것도 수행하지 못한다. */
export async function applyActions(ex: Executor, s: MainSession, actions: MainAction[]): Promise<ActionResult[]> {
  const rt = ex.runtime;
  if (rt.session?.id !== s.id || rt.generation !== s.generation) return actions.map((a) => note(String(a.id), String(a.type), false, '이전 세대의 메인 — 상태를 바꾸지 못함'));
  const out: ActionResult[] = [];
  for (const a of actions) {
    const r = await runOne(ex, s, a);
    rt.processed[r.id] ??= r; // 거부된 행동 ID도 다시 쓰지 못하게 남긴다(재전송 방지)
    out.push(r);
    ex.audit('main_action', { session: s.id, generation: s.generation, id: r.id, type: r.type, ok: r.ok, detail: r.detail });
  }
  s.actionResults.push(...out);
  ex.store.save();
  return out;
}

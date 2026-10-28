// 새 메인이 낸 행동을 수행한다. 수행 직전마다 세션·세대·정지 상태, 중복 ID, 결과 불명 대상, 승인 범위(조건 포함)를 통과해야 한다.
// 실제 수행은 기존 기능(배정·승인·통합)을 호출하는 쪽이 넘겨 준 MainOps로만 한다. 새 권한을 만들지 않는다.
// 행동 수행과 교대는 serialize로 한 줄에 세워, 교대 도중 이전 메인의 남은 행동이 끼어들지 못하게 한다.
import { authorize } from './mainApprovals.ts';
import { dispatch } from './mainDispatch.ts';
import { outcomeProblem } from './mainOutcome.ts';
import { serialize } from './mainSerial.ts';
import { suggestTaskId } from './prepare.ts';
import { type Executor } from './executor.ts';
import type { ActionResult, Approval, MainAction, MainSession } from './mainTypes.ts';

const note = (id: string, type: string, ok: boolean, detail: string): ActionResult => ({ id, type, ok, detail, at: new Date().toISOString() });
const PENDING = '수행 중(완료 기록 전에 중단되면 결과 불명 — 재실행하지 않음)';

/** 승인 검사와 실행이 함께 쓸 실제 대상을 먼저 확정한다. 배정은 생성될 task ID를 input에 고정해 돌려준다. */
async function plan(ex: Executor, a: MainAction): Promise<{ target: string; input?: Record<string, unknown> } | { error: string }> {
  if (a.type === 'push_main') return { target: String(a.target ?? ex.cfg.integration.branch) };
  if (a.type !== 'assign_task') return { target: a.type === 'run_experiment' ? String(a.target ?? '') : String(a.taskId ?? '') };
  const input: Record<string, unknown> = { ...(a.input ?? {}) };
  if (a.taskId && input.taskId && String(input.taskId) !== a.taskId) return { error: `배정 대상 불일치: 바깥 taskId(${a.taskId})와 input.taskId(${String(input.taskId)})가 일치하지 않음` };
  input.taskId = String(input.taskId ?? a.taskId ?? await suggestTaskId(ex, String(input.agent ?? 'claude')));
  return { target: String(input.taskId), input };
}

/** 완료 여부를 모르는 대상은 확인 전에 다시 건드리지 않는다. */
function uncertain(ex: Executor, a: MainAction): string | null {
  const t = a.taskId ? ex.state.tasks[a.taskId] : undefined;
  if (t && ['unknown', 'orphan_running', 'exit_observed', 'starting', 'collecting', 'cancelling', 'integrating'].includes(t.status)) return `${t.taskId}: 결과 불명·진행 중(${t.status}) — 확인 전 재실행하지 않음`;
  const p = Object.values(ex.state.pushes ?? {}).find((x) => (x.status === 'push_unverified' || x.status === 'remote_mismatch') && (a.type === 'push_main' || (a.taskId && x.tasks.includes(a.taskId))));
  return p ? `${a.taskId}: push 결과 불명(${p.id.slice(0, 8)}) — 원격 확인 전 재수행하지 않음` : null;
}

async function runOne(ex: Executor, s: MainSession, a: MainAction): Promise<ActionResult> {
  const rt = ex.runtime;
  if (!a.id || !a.type) return note(String(a.id ?? '?'), String(a.type ?? '?'), false, '행동 ID·종류가 없음');
  if (rt.session?.id !== s.id || rt.generation !== s.generation || rt.frozen) return note(a.id, a.type, false, '이전 세대의 메인이거나 교대 진행 중 — 상태를 바꾸지 못함');
  if (rt.processed[a.id]) return note(a.id, a.type, false, '중복 행동 ID — 다시 수행하지 않음');
  rt.processed[a.id] = note(a.id, a.type, false, PENDING); // 검사·실행·기록 사이의 중복을 막기 위해 실행 전에 남긴다
  ex.store.save();
  const fin = (ok: boolean, detail: string) => (rt.processed[a.id] = note(a.id, a.type, ok, detail)); // 거부된 행동 ID도 다시 쓰지 못하게 남긴다
  if (a.type === 'note') return fin(true, '기록만 함(상태 변경 없음)');
  const hold = uncertain(ex, a);
  if (hold) return fin(false, hold);
  const p = await plan(ex, a);
  if ('error' in p) return fin(false, p.error);
  let ap: Approval;
  try { ap = authorize(ex, s.id, a.type, p.target, a.sha); } catch (e) { return fin(false, (e as Error).message); }
  try { await dispatch(ex, s.id, a, p, ap); } catch (e) { return fin(false, `수행 실패: ${(e as Error).message}`); }
  const bad = outcomeProblem(ex, a, p.target);
  return bad ? fin(false, `수행했으나 결과가 성공이 아님 — ${bad}`) : fin(true, `${p.target} ${a.type} 처리 확인`);
}

/** 행동을 순서대로, 하나씩 직렬화해 수행한다. 각 행동 직전에 소유권을 다시 확인하며 결과를 장부(processed)와 세션에 기록한다. */
export async function applyActions(ex: Executor, s: MainSession, actions: MainAction[]): Promise<ActionResult[]> {
  const out: ActionResult[] = [], failedTasks = new Set<string>();
  for (const a of actions) {
    let r: ActionResult;
    // 같은 작업의 앞 행동이 실패하면 뒤 행동은 하지 않고, push는 앞 행동이 하나라도 실패하면 하지 않는다(단계를 무조건 넘기지 않음).
    const blocked = (a.taskId && failedTasks.has(a.taskId)) || (a.type === 'push_main' && out.some((x) => !x.ok && x.type !== 'note'));
    if (blocked && a.id && !ex.runtime.processed[a.id]) r = ex.runtime.processed[a.id] = note(a.id, a.type, false, '같은 작업(또는 push 앞)의 이전 행동이 실패해 수행하지 않음');
    else try { r = await serialize(ex, () => runOne(ex, s, a)); } catch (e) { r = note(String(a?.id ?? '?'), String(a?.type ?? '?'), false, `예기치 않은 예외: ${(e as Error).message}`); }
    try { ex.audit('main_action', { session: s.id, generation: s.generation, id: r.id, type: r.type, ok: r.ok, detail: r.detail }); } catch { /* 감사 기록 실패가 행동 결과를 바꾸지 않는다 */ }
    if (!r.ok && a.taskId) failedTasks.add(a.taskId);
    out.push(r);
  }
  s.actionResults.push(...out);
  ex.store.save();
  return out;
}

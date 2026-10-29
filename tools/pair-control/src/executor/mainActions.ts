// 새 메인이 낸 행동을 수행한다. 수행 직전마다 세션·세대·정지 상태, 중복 ID, 결과 불명 대상, 승인 범위(조건 포함)를 통과해야 한다.
// 승인 뒤 행동별 기존 서비스에 직접 연결하며, 연결부 MainOps가 새 권한을 만들지는 않는다.
// 행동 수행과 교대는 lock으로 한 줄에 세워, 교대 도중 이전 메인의 남은 행동이 끼어들지 못하게 한다.
import { authorize } from './approvalGate.ts';
import { note, PENDING, plan, uncertain } from './actionPlan.ts';
import { confirmAction, pushAction } from './mainDispatch.ts';
import { outcomeProblem } from './mainOutcome.ts';
import { lock } from './mainSerial.ts';
import { UserError, type Executor } from './executor.ts';
import type { ActionResult, Approval, MainAction, MainSession } from './mainTypes.ts';

/**
 * 행동 하나를 lock으로 직렬화해 수행한다. 앞 행동이 실패한 작업(또는 push 앞 실패)에 속하면 수행하지 않는다(단계를 무조건 넘기지 않음).
 * 수행 직전마다 소유권(세션·세대·정지)을 다시 확인하고, 실행 전에 처리 중 ID를 남겨 검사·실행·기록 사이의 중복을 막는다.
 */
async function runOne(ex: Executor, s: MainSession, a: MainAction, skip: boolean): Promise<ActionResult> {
  const rt = ex.runtime;
  if (!a.id || !a.type) return note(String(a.id ?? '?'), String(a.type ?? '?'), false, '행동 ID·종류가 없음');
  if (skip && !rt.processed[a.id]) return (rt.processed[a.id] = note(a.id, a.type, false, '같은 작업(또는 push 앞)의 이전 행동이 실패해 수행하지 않음'));
  const release = await lock(ex);
  const fin = (ok: boolean, detail: string) => (rt.processed[a.id] = note(a.id, a.type, ok, detail)); // 거부된 행동 ID도 다시 쓰지 못하게 남긴다
  try {
    if (rt.session?.id !== s.id || rt.generation !== s.generation || rt.frozen) return note(a.id, a.type, false, '이전 세대의 메인이거나 교대 진행 중 — 상태를 바꾸지 못함');
    if (rt.processed[a.id]) return note(a.id, a.type, false, '중복 행동 ID — 다시 수행하지 않음');
    rt.processed[a.id] = note(a.id, a.type, false, PENDING); // 검사·실행·기록 사이의 중복을 막기 위해 실행 전에 남긴다
    ex.store.save();
    if (a.type === 'note') return fin(true, '기록만 함(상태 변경 없음)');
    const hold = uncertain(ex, a);
    if (hold) return fin(false, hold);
    const p = await plan(ex, a);
    if ('error' in p) return fin(false, p.error);
    let ap: Approval;
    try { ap = authorize(ex, s.id, a.type, p.target, a.sha); } catch (e) { return fin(false, (e as Error).message); }
    try {
      const ops = ex.mainOps;
      if (a.type === 'approve_task' && ops.approve) await ops.approve(p.target, String(a.sha ?? ''));
      else if (a.type === 'integrate_task' && ops.integrate) await ops.integrate(p.target);
      else if (a.type === 'assign_task' && ops.assign) await ops.assign(p.input ?? {});
      else if (a.type === 'confirm_handoff') await confirmAction(ex, a, p.target, !!ap.requires?.selfReview);
      else if (a.type === 'push_main') await pushAction(ex, s.id, a);
      else throw new UserError(`지원하지 않거나 연결되지 않은 행동(${a.type}) — 수행하지 않음`);
    } catch (e) { return fin(false, `수행 실패: ${(e as Error).message}`); }
    const bad = outcomeProblem(ex, a, p.target);
    const self = a.type === 'confirm_handoff' && ex.state.tasks[p.target]?.agent === ex.mainAgent ? ' — 자기 확인(독립 검토 아님)' : '';
    return bad ? fin(false, `수행했으나 결과가 성공이 아님 — ${bad}`) : fin(true, `${p.target} ${a.type} 처리 확인${self}`);
  } catch (e) { return note(String(a?.id ?? '?'), String(a?.type ?? '?'), false, `예기치 않은 예외: ${(e as Error).message}`); } finally { release(); }
}

/** 행동을 순서대로, 하나씩 수행한다. 결과를 장부(processed)와 세션에 기록한다. */
export async function applyActions(ex: Executor, s: MainSession, actions: MainAction[]): Promise<ActionResult[]> {
  const out: ActionResult[] = [], failedTasks = new Set<string>();
  let anyFailed = false;
  for (const a of actions) {
    const r = await runOne(ex, s, a, !!(a.taskId && failedTasks.has(a.taskId)) || (a.type === 'push_main' && anyFailed));
    try { ex.audit('main_action', { session: s.id, generation: s.generation, id: r.id, type: r.type, ok: r.ok, detail: r.detail }); } catch { /* 감사 기록 실패가 행동 결과를 바꾸지 않는다 */ }
    if (!r.ok && a.taskId) failedTasks.add(a.taskId);
    if (!r.ok && r.type !== 'note') anyFailed = true;
    out.push(r);
  }
  s.actionResults.push(...out);
  ex.store.save();
  return out;
}

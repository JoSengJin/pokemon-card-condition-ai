// 작업 상태를 읽어 의미 있는 변화만 이벤트로 등록한다(모델 호출 없음, 상태 읽기뿐).
// 다음 행동의 승인이 열려 있지 않거나(범위 밖·검증할 수 없는 조건) 멈춘 작업은 턴을 일으키지 않고 보류로 남긴다. 승인이 열리거나 한도가 풀리면 보류가 풀린다.
import { turnHold } from './approvalScope.ts';
import { pipe, register } from './pipelineState.ts';
import type { Executor, Task } from './executor.ts';

const STOPPED = ['failed', 'unknown', 'orphan_running', 'exit_observed', 'integrated_check_failed', 'integration_conflict', 'integration_refused', 'rejected'];

const pushed = (ex: Executor, id: string) => Object.values(ex.state.pushes ?? {}).some((p) => p.status === 'pushed_verified' && p.tasks.includes(id));

/** 이 작업의 현재 상태가 만드는 이벤트(없으면 null). */
function wanted(ex: Executor, t: Task): { kind: 'result_ready' | 'approved' | 'integrated' | 'blocked'; sha: string; hold?: string } | null {
  const r = t.result, v = t.verification, h = t.handoff;
  if (STOPPED.includes(t.status)) return { kind: 'blocked', sha: `${t.status}:${r?.headSha ?? t.baseSha}`, hold: `사용자 판단 필요: ${t.status}${t.statusReason ? ` — ${t.statusReason}` : ''}` };
  if (t.status === 'review_pending' && r?.headSha && v?.sha === r.headSha) {
    if (v.status !== 'passed') return v.status === 'running' ? null : { kind: 'blocked', sha: `checks_${v.status}:${r.headSha}`, hold: `작업 테스트가 통과하지 않음(${v.status}) — 통과가 아님` };
    return r.checksPassed && h && !h.cancelledAt && h.headSha === r.headSha ? { kind: 'result_ready', sha: r.headSha } : null;
  }
  if (t.status === 'approved' && t.approval) return { kind: 'approved', sha: t.approval.sha };
  if (t.status === 'integrated' && t.integration?.newHead && t.integration.postStatus !== 'failed' && !pushed(ex, t.taskId)) return { kind: 'integrated', sha: t.integration.newHead };
  return null;
}

/** 보류 사유가 해소됐는지 보고 풀 수 있는 이벤트는 대기로 되돌린다(승인이 열림, 한도가 풀림). */
function revive(ex: Executor, sid: string | undefined) {
  for (const e of Object.values(pipe(ex).events)) {
    if (e.state !== 'held' || e.kind === 'blocked') continue;
    const t = ex.state.tasks[e.taskId];
    const scope = e.reason?.startsWith('승인') && !!t && !turnHold(ex, sid, t, e.kind);
    const limit = e.reason?.startsWith('한도') && !ex.limitFor(ex.mainAgent);
    if (!scope && !limit) continue;
    e.state = 'pending'; delete e.reason;
    if (limit) e.tried = e.tried.filter((g) => g !== ex.runtime.generation);
    ex.audit('pipeline_event_revived', { key: e.key });
  }
}

export function scanEvents(ex: Executor) {
  const sid = ex.runtime.session?.id;
  revive(ex, sid);
  for (const t of Object.values(ex.state.tasks)) {
    const w = wanted(ex, t);
    if (!w) continue;
    register(ex, w.kind, t.taskId, w.sha, w.hold ?? (w.kind === 'blocked' ? undefined : turnHold(ex, sid, t, w.kind) ?? undefined));
  }
  ex.store.save();
}

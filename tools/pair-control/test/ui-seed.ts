// 연속 처리 화면 검증용 합성 상태(테스트와 수동 화면 확인이 같이 쓴다). 실제 모델·원격 호출 없음.
import { task, type Env } from './helpers.ts';

/** 인수 확인이 끝난 메인 + 성공·실패 행동이 섞인 턴 + 보류·결과 불명 이벤트 + 원격 push가 검증된 작업 하나. */
export async function seed(e: Env) {
  const now = new Date().toISOString();
  await e.ex.assign(task(e, 'task-a', { mode: 'manual', allowedFiles: ['src_a/'] }));
  await e.ex.assign(task(e, 'task-b', { mode: 'manual', allowedFiles: ['src_b/'] }));
  e.ex.runtime.session = { id: 's1', agent: 'claude', from: 'codex', generation: 2, status: 'completed', startedAt: now, limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: '', actionResults: [], ackedAt: now } as any;
  e.ex.runtime.generation = 2;
  const p = (e.ex.runtime.pipeline ??= { events: {}, turns: {}, steps: {} });
  p.turns['t1'] = { id: 't1', sessionId: 's1', generation: 2, agent: 'claude', status: 'applied', eventKeys: ['k1'], startedAt: now, lifetime: 'x', tokenHash: '', checkpointFile: '', checkpointHash: '',
    actionResults: [{ id: 'a1', type: 'confirm_handoff', ok: true, detail: 'task-a confirm_handoff 처리 확인 — 자기 확인(독립 검토 아님)', at: now }, { id: 'a2', type: 'approve_task', ok: false, detail: '승인 조건 불충족: approve_task → task-a', at: now }] };
  p.turns['t2'] = { id: 't2', sessionId: 's1', generation: 2, agent: 'claude', status: 'launched', eventKeys: ['k3'], startedAt: new Date(Date.now() + 1000).toISOString(), lifetime: e.ex.lifetime, execId: 'e', tokenHash: '', checkpointFile: '', checkpointHash: '', actionResults: [] };
  p.events['k1'] = { key: 'k1', kind: 'result_ready', taskId: 'task-a', sha: 'a'.repeat(40), at: now, state: 'applied', tried: [2] };
  p.events['k2'] = { key: 'k2', kind: 'result_ready', taskId: 'task-b', sha: 'b'.repeat(40), at: now, state: 'held', tried: [], reason: '승인 조건 미확정: confirm_handoff 승인에 검증할 수 없는 조건이 있어 사람 판단 전에는 자동 처리하지 않음' };
  p.events['k3'] = { key: 'k3', kind: 'integrated', taskId: 'task-a', sha: 'c'.repeat(40), at: now, state: 'unknown', tried: [2], reason: '턴 프로세스가 종료 기록 없이 사라짐(결과 불명) — 재시도하지 않음' };
  (e.ex.state.pushes ??= {})['p1'] = { id: 'p1', at: now, kind: 'push', remote: 'origin', remoteUrl: '', branch: 'main', preRemoteHead: 'a'.repeat(40), pushedSha: 'c'.repeat(40), commits: [], tasks: ['task-a'], command: [], status: 'pushed_verified', detail: 'ok' };
}

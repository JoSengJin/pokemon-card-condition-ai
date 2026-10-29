// 턴 종료 관찰(검증·저장)과 행동 적용의 분리 회귀: 검증된 응답은 verified로 저장되고, 적용은 연속 처리 진입점이 저장 상태를 읽어 한 번만 한다.
// 합성 상태만 쓴다(실제 CLI·모델 호출 없음).
import assert from 'node:assert/strict';
import { test } from 'node:test';
import type { MainTurn } from '../src/executor/mainTypes.ts';
import { pipelineTick } from '../src/executor/pipelineTick.ts';
import { pipe } from '../src/executor/pipelineState.ts';
import { setup, type Env } from './helpers.ts';

function owner(e: Env) {
  const s: any = { id: 'owner-sess', generation: 1, agent: 'codex', from: 'claude', status: 'idle', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: '', actionResults: [], ackedAt: new Date().toISOString() };
  e.ex.runtime.session = s; e.ex.runtime.generation = 1; e.ex.state.main = { agent: 'codex', generation: 1, since: s.startedAt };
}
function verifiedTurn(e: Env, over: Partial<MainTurn> = {}) {
  const calls: unknown[] = [];
  (e.ex as any).launchMainProcess = async (o: unknown) => { calls.push(o); return 'stub'; };
  pipe(e.ex).events.k = { key: 'k', kind: 'result_ready', taskId: 'task-a', sha: 'x', at: new Date().toISOString(), state: 'launched', tried: [1] };
  pipe(e.ex).turns.t1 = { id: 't1', sessionId: 'owner-sess', generation: 1, agent: 'codex', status: 'verified', eventKeys: ['k'], startedAt: new Date().toISOString(), lifetime: e.ex.lifetime, tokenHash: '', checkpointFile: '', checkpointHash: '', actionResults: [], pendingActions: [{ id: 'n1', type: 'note' }], ...over };
  return calls;
}

test('verified 턴은 다음 연속 처리에서 한 번만 적용되고 저장된 pendingActions는 비워진다', async () => {
  const e = setup();
  try {
    owner(e); verifiedTurn(e);
    await pipelineTick(e.ex);
    const t = pipe(e.ex).turns.t1;
    assert.equal(t.status, 'applied'); assert.deepEqual(t.actionResults.map((r) => [r.id, r.ok]), [['n1', true]]); assert.equal(t.pendingActions, undefined);
    await pipelineTick(e.ex);
    assert.equal(t.actionResults.length, 1, '두 번째 틱은 다시 적용하지 않음'); assert.equal(pipe(e.ex).events.k.state, 'applied');
  } finally { e.cleanup(); }
});

test('검증 뒤 세대가 바뀌면 이전 응답은 적용하지 않고 stale로 남긴다(행동 장부에도 남지 않음)', async () => {
  const e = setup();
  try {
    owner(e); verifiedTurn(e); e.ex.runtime.generation = 2;
    await pipelineTick(e.ex);
    const t = pipe(e.ex).turns.t1;
    assert.equal(t.status, 'stale'); assert.equal(t.actionResults.length, 0); assert.equal(t.pendingActions, undefined);
    assert.equal(e.ex.runtime.processed.n1, undefined, '이전 세대 행동 ID가 처리되지 않음'); assert.equal(pipe(e.ex).events.k.state, 'pending');
  } finally { e.cleanup(); }
});

test('교대 진행 중(frozen)에는 적용하지 않는다. 정지(stop)된 뒤에는 verified 상태로 남아 적용되지 않는다', async () => {
  const e = setup();
  try {
    owner(e); verifiedTurn(e, { lifetime: 'previous-server' }); // 이전 서버 수명의 검증된 저장 응답
    (e.ex as any).stopped = true;
    await pipelineTick(e.ex);
    assert.equal(pipe(e.ex).turns.t1.status, 'verified', '정지 뒤에는 적용하지 않고 저장 상태로 둔다');
    (e.ex as any).stopped = false; e.ex.runtime.frozen = true;
    await pipelineTick(e.ex);
    assert.equal(pipe(e.ex).turns.t1.status, 'verified', '교대 중에는 건드리지 않음');
  } finally { e.cleanup(); }
});

test('재시작 뒤: 이전 수명에서 검증만 끝난(verified) 응답은 최초 1회 적용하고, 적용 중이던(applying) 턴은 결과 불명으로 보존한다', async () => {
  const e = setup();
  try {
    owner(e); const launches = verifiedTurn(e, { lifetime: 'previous-server' });
    pipe(e.ex).turns.t2 = { ...pipe(e.ex).turns.t1, id: 't2', status: 'applying', pendingActions: undefined, eventKeys: [] };
    await pipelineTick(e.ex);
    assert.equal(pipe(e.ex).turns.t1.status, 'applied'); assert.equal(pipe(e.ex).turns.t1.actionResults.length, 1);
    assert.equal(pipe(e.ex).turns.t2.status, 'unknown', '적용 중이던 턴은 다시 적용하지 않음'); assert.equal(pipe(e.ex).turns.t2.actionResults.length, 0);
    assert.equal(launches.length, 0, '결과 불명 턴이 있으면 새 모델 턴을 시작하지 않음');
  } finally { e.cleanup(); }
});

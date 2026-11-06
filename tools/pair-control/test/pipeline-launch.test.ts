// 저장된 턴 실행 요청의 재시작 복구와 검사/실행 사이 승인 변경. fake CLI의 --help와 임시 저장소만 쓴다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { assign } from '../src/executor/taskAssign.ts';
import { grantApproval, revokeApproval } from '../src/executor/mainApprovals.ts';
import { tick } from '../src/executor/monitorTick.ts';
import { pipe } from '../src/executor/pipelineState.ts';
import { setup, task, fakeCli, type Env } from './helpers.ts';

async function queued() {
  const e = setup({ cli: fakeCli });
  await assign(e.ex, task(e, 'task-a'));
  const t = e.ex.state.tasks['task-a']; t.status = 'approved'; t.approval = { sha: t.baseSha } as any;
  const session: any = { id: 'session', generation: 1, agent: 'codex', from: 'claude', status: 'idle', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: '', actionResults: [] };
  e.ex.runtime.session = session; e.ex.runtime.generation = 1;
  const approval = grantApproval(e.ex, { basis: '합성: 저장된 턴 실행', actions: ['integrate_task'], targets: ['task-a'] });
  const key = `approved:task-a:${t.baseSha}`;
  pipe(e.ex).events[key] = { key, kind: 'approved', taskId: t.taskId, sha: t.baseSha, at: session.startedAt, state: 'pending', tried: [] };
  pipe(e.ex).launch = { sessionId: session.id, generation: 1, eventKeys: [key], stage: 'queued' };
  e.ex.store.save();
  return { e, key, approval };
}
function stub(e: Env) {
  const calls: unknown[] = [];
  e.ex.launchMainProcess = async (input) => { calls.push(input); return 'fake-execution'; };
  return calls;
}

test('저장만 된 queued 요청은 재시작 뒤 최초 한 번 실행하며 실제 턴 ID에 연결된다', async () => {
  const { e, key } = await queued(); let restarted: Env | undefined;
  try {
    restarted = e.restart(); const calls = stub(restarted);
    await tick(restarted.ex);
    assert.equal(calls.length, 1); assert.equal(pipe(restarted.ex).launch, undefined);
    const turns = Object.values(pipe(restarted.ex).turns);
    assert.equal(turns.length, 1); assert.equal(turns[0].status, 'launched');
    assert.equal(pipe(restarted.ex).events[key].turnId, turns[0].id);
    await tick(restarted.ex); assert.equal(calls.length, 1, '진행 중인 턴을 중복 실행하지 않음');
  } finally { (restarted ?? e).cleanup(); }
});

test('실행 시작 기록만 남은 요청은 재시작 뒤 결과 불명으로 남기고 재실행하지 않는다', async () => {
  const { e, key } = await queued(); let restarted: Env | undefined;
  try {
    pipe(e.ex).launch!.stage = 'launching'; e.ex.store.save();
    restarted = e.restart(); const calls = stub(restarted);
    await tick(restarted.ex);
    assert.equal(calls.length, 0); assert.equal(pipe(restarted.ex).launch, undefined);
    assert.equal(pipe(restarted.ex).events[key].state, 'unknown');
  } finally { (restarted ?? e).cleanup(); }
});

test('queued 뒤 승인 철회 또는 stop은 모델 실행을 막는다', async () => {
  const { e, key, approval } = await queued();
  try {
    const calls = stub(e);
    e.ex.stopped = true; await tick(e.ex);
    assert.equal(pipe(e.ex).launch?.stage, 'queued'); assert.equal(calls.length, 0);
    e.ex.stopped = false; revokeApproval(e.ex, approval.id);
    await tick(e.ex);
    assert.equal(calls.length, 0); assert.equal(pipe(e.ex).events[key].state, 'held');
    assert.match(pipe(e.ex).events[key].reason!, /승인 범위 밖/);
  } finally { e.cleanup(); }
});

test('실제 턴이 이미 저장됐으면 남은 launching 요청은 그 턴의 종료 상태를 덮지 않는다', async () => {
  const { e, key } = await queued();
  try {
    const calls = stub(e);
    await tick(e.ex);
    const turn = Object.values(pipe(e.ex).turns)[0];
    turn.status = 'applied'; pipe(e.ex).events[key].state = 'applied';
    pipe(e.ex).launch = { sessionId: turn.sessionId, generation: turn.generation, eventKeys: [key], stage: 'launching', lifetime: 'previous', turnId: turn.id };
    await tick(e.ex);
    assert.equal(calls.length, 1); assert.equal(turn.status, 'applied'); assert.equal(pipe(e.ex).events[key].state, 'applied');
    assert.equal(pipe(e.ex).launch, undefined);
  } finally { e.cleanup(); }
});

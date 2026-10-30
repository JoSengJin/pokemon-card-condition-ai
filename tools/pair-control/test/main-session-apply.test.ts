// 인수 확인과 행동 적용의 영속 경계 회귀. 실제 CLI나 외부 호출 없이 저장 상태만 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ackSession } from '../src/executor/mainAck.ts';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { applyTakenOver } from '../src/executor/mainSessionApply.ts';
import type { MainSession } from '../src/executor/mainTypes.ts';
import { setup } from './helpers.ts';

function launching(): MainSession {
  return { id: 'next', agent: 'claude', from: 'codex', generation: 1, status: 'launching', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: 'checkpoint.json', checkpointHash: 'hash', tokenHash: 'token', actionResults: [] };
}

test('인수 확인은 행동을 실행하지 않고 taken_over + pendingActions까지만 저장한다', () => {
  const e = setup();
  try {
    const s = launching(); e.ex.runtime.session = s; e.ex.runtime.frozen = true;
    ackSession(e.ex, s, { actions: [{ id: 'n1', type: 'note' }] });
    assert.equal(s.status, 'taken_over'); assert.equal(e.ex.runtime.frozen, false);
    assert.deepEqual(s.pendingActions?.map((a) => a.id), ['n1']);
    assert.equal(e.ex.runtime.processed.n1, undefined, '같은 종료 처리 스택에서는 행동을 시작하지 않음');
  } finally { e.cleanup(); }
});

test('다음 진입점이 저장 행동을 한 번만 적용하고, applying 재시작 상태는 재실행하지 않는다', async () => {
  const e = setup();
  try {
    const s = launching(); e.ex.runtime.session = s; e.ex.runtime.generation = 1;
    ackSession(e.ex, s, { actions: [{ id: 'n1', type: 'note' }] });
    await applyTakenOver(e.ex, s);
    assert.equal(s.status, 'applying', '첫 진입은 accepted 상태만 저장');
    await applyTakenOver(e.ex, s);
    assert.equal(s.status, 'idle'); assert.equal(s.pendingActions, undefined); assert.equal(s.actionResults.length, 1);
    await applyTakenOver(e.ex, s);
    assert.equal(s.actionResults.length, 1, '완료 상태는 다시 적용하지 않음');

    const crashed = { ...launching(), id: 'crashed', status: 'applying' as const, pendingActions: undefined, actionLifetime: 'previous-server' };
    e.ex.runtime.session = crashed;
    await applyTakenOver(e.ex, crashed);
    assert.equal(crashed.status, 'idle'); assert.match(crashed.failure ?? '', /결과 불명/);
    assert.equal(e.ex.runtime.processed.crashed, undefined, '적용 중 상태는 재실행하지 않음');
  } finally { e.cleanup(); }
});

test('accepted→authorized 사이 승인 철회는 dispatch 직전 재검사에서 실행 없이 done으로 끝난다', async () => {
  const e = setup();
  try {
    const s = launching(); e.ex.runtime.session = s; e.ex.runtime.generation = 1;
    e.ex.state.tasks.t1 = { taskId: 't1', status: 'review_pending' } as any;
    const approval = grantApproval(e.ex, { basis: '합성 승인', actions: ['approve_task'], targets: ['t1'] });
    let calls = 0; e.ex.setMainOps({ approve: async () => { calls++; } });
    ackSession(e.ex, s, { actions: [{ id: 'a1', type: 'approve_task', taskId: 't1', sha: 'a'.repeat(40) }] });
    await applyTakenOver(e.ex, s);
    assert.equal(s.actionWork?.[0].status, 'accepted');
    await applyTakenOver(e.ex, s);
    assert.equal(s.actionWork?.[0].status, 'authorized');
    approval.revokedAt = new Date().toISOString();
    await applyTakenOver(e.ex, s);
    assert.equal(calls, 0); assert.equal(s.status, 'idle');
    assert.match(s.actionResults[0].detail, /승인 범위 밖/);
  } finally { e.cleanup(); }
});

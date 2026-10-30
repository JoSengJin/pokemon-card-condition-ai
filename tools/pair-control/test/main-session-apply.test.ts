// 인수 확인과 행동 적용의 영속 경계 회귀. 실제 CLI나 외부 호출 없이 저장 상태만 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ackSession } from '../src/executor/mainAck.ts';
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
    assert.equal(s.status, 'idle'); assert.equal(s.pendingActions, undefined); assert.equal(s.actionResults.length, 1);
    await applyTakenOver(e.ex, s);
    assert.equal(s.actionResults.length, 1, '완료 상태는 다시 적용하지 않음');

    const crashed = { ...launching(), id: 'crashed', status: 'applying' as const, pendingActions: undefined };
    e.ex.runtime.session = crashed;
    await applyTakenOver(e.ex, crashed);
    assert.equal(crashed.status, 'idle'); assert.match(crashed.failure ?? '', /결과 불명/);
    assert.equal(e.ex.runtime.processed.crashed, undefined, '적용 중 상태는 재실행하지 않음');
  } finally { e.cleanup(); }
});

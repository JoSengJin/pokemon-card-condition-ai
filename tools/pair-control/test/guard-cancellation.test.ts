// 합성 저장 상태의 최초 취소·결과 불명 복구. 실제 모델·운영 프로세스를 실행하지 않는다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { queueGuardCancellation } from '../src/executor/guardCancellation.ts';
import { tick } from '../src/executor/monitorTick.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { setup } from './helpers.ts';

test('저장된 pending 취소는 재시작 뒤 최초 한 번만 전송하고 완료 상태를 보존한다', async () => {
  let e = setup();
  try {
    e.ex.runtime.limited.claude = { at: 'test', detail: '합성 공급자 한도' };
    queueGuardCancellation(e.ex, '합성 취소', 'claude');
    stop(e.ex);
    assert.equal(e.ex.state.guardCancellations![0].stage, 'pending');
    e = e.restart(); stop(e.ex);
    const request = e.ex.state.guardCancellations![0];
    assert.ok(e.ex.runtime.limited.claude, '차단 상태와 취소 요청이 함께 저장됨');
    await tick(e.ex);
    assert.equal(request.stage, 'sent');
    assert.equal(request.agent, 'claude');
    assert.equal(request.lifetime, e.ex.lifetime);
    const snapshot = JSON.stringify(request);
    await tick(e.ex);
    assert.equal(JSON.stringify(request), snapshot, '같은 취소 요청을 다시 전송하지 않음');
    e = e.restart(); stop(e.ex);
    await tick(e.ex);
    assert.equal(JSON.stringify(e.ex.state.guardCancellations![0]), snapshot);
  } finally { e.cleanup(); }
});

test('취소 dispatching 상태의 재시작은 결과 불명으로 보존하고 재전송하지 않는다', async () => {
  let e = setup();
  try {
    e.ex.state.guardCancellations = [{ at: 'test', reason: '합성', stage: 'dispatching', lifetime: e.ex.lifetime }];
    e.ex.store.save();
    e = e.restart(); stop(e.ex);
    const request = e.ex.state.guardCancellations![0], previous = request.lifetime;
    await tick(e.ex);
    assert.equal(request.stage, 'unknown');
    assert.equal(request.lifetime, previous, '새 수명으로 재전송 표시를 덮어쓰지 않음');
    await tick(e.ex);
    assert.equal(request.stage, 'unknown');
  } finally { e.cleanup(); }
});

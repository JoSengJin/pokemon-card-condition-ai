import { tick } from '../src/executor/monitorTick.ts';
// 인수 확인과 행동 적용의 영속 경계 회귀. 실제 CLI나 외부 호출 없이 저장 상태만 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { ackSession } from '../src/executor/mainAck.ts';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { applyTakenOver, finishSession } from '../src/executor/mainSessionApply.ts';
import { pipe } from '../src/executor/pipelineState.ts';
import type { MainSession } from '../src/executor/mainTypes.ts';
import { advanceActions, setup } from './helpers.ts';

function launching(): MainSession {
  return { id: 'next', agent: 'claude', from: 'codex', generation: 1, status: 'launching', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: 'checkpoint.json', checkpointHash: 'hash', tokenHash: 'token', actionResults: [] };
}

test('메인 ready 이후 exec 직전 공급자 한도가 생기면 CLI를 시작하지 않는다', async () => {
  const e = setup({ allowRealModelCalls: true, confirmedSubscriptionAuth: true });
  try {
    const s = launching();
    Object.assign(s, { launchStage: 'exec', launchLifetime: e.ex.lifetime, bundleDir: e.dir, launchPrompt: 'synthetic' });
    e.ex.runtime.session = s; e.ex.runtime.frozen = true;
    e.ex.probes.claude = { installed: true, binary: '/nonexistent/synthetic-cli', missingFlags: [] } as any;
    e.ex.runtime.limited.claude = { at: new Date().toISOString(), detail: 'ready 이후 한도' };
    await tick(e.ex, );
    assert.equal(Object.keys(e.ex.state.executions).length, 0);
    assert.equal(e.ex.runtime.session, null);
    assert.match(e.ex.runtime.history.at(-1)?.failure ?? '', /구독 사용 한도 도달 상태/);
  } finally { e.cleanup(); }
});

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
    applyTakenOver(e.ex, s);
    assert.equal(s.status, 'applying', '첫 진입은 accepted 상태만 저장');
    if (await advanceActions(e.ex, s, s)) finishSession(e.ex, s);
    assert.equal(s.status, 'idle'); assert.equal(s.pendingActions, undefined); assert.equal(s.actionResults.length, 1);
    applyTakenOver(e.ex, s);
    assert.equal(s.actionResults.length, 1, '완료 상태는 다시 적용하지 않음');

    const crashed = { ...launching(), id: 'crashed', status: 'applying' as const, pendingActions: undefined, actionLifetime: 'previous-server' };
    e.ex.runtime.session = crashed;
    applyTakenOver(e.ex, crashed);
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
    let calls = 0; (e.ex.mainOps = { approve: async () => { calls++; } });
    ackSession(e.ex, s, { actions: [{ id: 'a1', type: 'approve_task', taskId: 't1', sha: 'a'.repeat(40) }] });
    applyTakenOver(e.ex, s);
    assert.equal(s.actionWork?.[0].status, 'accepted');
    await advanceActions(e.ex, s, s);
    assert.equal(s.actionWork?.[0].status, 'authorized');
    approval.revokedAt = new Date().toISOString();
    if (await advanceActions(e.ex, s, s)) finishSession(e.ex, s);
    assert.equal(calls, 0); assert.equal(s.status, 'idle');
    assert.match(s.actionResults[0].detail, /승인 범위 밖/);
  } finally { e.cleanup(); }
});

test('push exec 진입 뒤 재시작 상태는 원격 호출 없이 결과 불명으로 끝난다', async () => {
  const e = setup();
  try {
    const s = launching(); s.status = 'applying'; e.ex.runtime.session = s; e.ex.runtime.generation = 1;
    s.actionWork = [{ action: { id: 'p-crash', type: 'push_main', target: 'main', sha: 'a'.repeat(40) }, status: 'dispatching', dispatchLifetime: 'previous-server', pushStage: 'exec', pushPlanId: 'old-plan' }];
    await advanceActions(e.ex, s, s);
    assert.equal(s.actionWork[0].status, 'done');
    assert.match(s.actionWork[0].result?.detail ?? '', /결과 불명.*재시도하지 않음/);
    assert.equal(Object.keys(e.ex.state.pushes ?? {}).length, 0);
  } finally { e.cleanup(); }
});

test('메인 실행 exec 진입 뒤 재시작 상태는 CLI 재호출 없이 결과 불명으로 보존한다', async () => {
  const e = setup();
  try {
    const s = launching();
    Object.assign(s, { launchStage: 'exec', launchLifetime: 'previous-server', bundleDir: 'saved-bundle', launchPrompt: 'saved-prompt' });
    e.ex.runtime.session = s; e.ex.runtime.frozen = true;
    let calls = 0;
    e.ex.launchMainProcess = async () => { calls++; return 'unexpected'; };
    await tick(e.ex, );
    assert.equal(calls, 0);
    assert.equal(e.ex.runtime.session, null);
    assert.equal(e.ex.runtime.frozen, false);
    assert.match(e.ex.runtime.history.at(-1)?.failure ?? '', /결과 불명.*재시도하지 않음/);
  } finally { e.cleanup(); }
});

test('종료 라우팅 중 재시작한 메인 턴은 응답을 적용하지 않고 결과 불명으로 끝낸다', async () => {
  const e = setup();
  try {
    const s = launching(); s.status = 'idle'; e.ex.runtime.session = s; e.ex.runtime.generation = 1;
    pipe(e.ex).events.k = { key: 'k', kind: 'result_ready', taskId: 'task-a', sha: 'x', at: 'x', state: 'launched', tried: [1] };
    pipe(e.ex).turns.t = { id: 't', sessionId: s.id, generation: 1, agent: s.agent, status: 'launched', eventKeys: ['k'], startedAt: 'x', lifetime: 'old', execId: 'x', tokenHash: 'x', checkpointFile: 'x', checkpointHash: 'x', actionResults: [] };
    e.ex.state.executions.x = { execId: 'x', taskId: '(main)', runId: 't', token: 'x', agent: s.agent, mode: 'real', display: [], pid: 999_999_999, pgid: 999_999_999, startedAt: 'x', status: 'exited', cancelRequested: false, observedAfterRestart: false, serverLifetime: 'old', logPath: 'missing', exitPath: 'missing', specPath: 'missing', tokens: '미측정', cost: '미측정', kind: 'main', completion: { stage: 'routing', code: 0, cancelled: false, unknown: false, lifetime: 'old' } };
    await tick(e.ex, );
    assert.equal(pipe(e.ex).turns.t.status, 'unknown');
    assert.equal(pipe(e.ex).events.k.state, 'unknown');
    assert.equal(pipe(e.ex).turns.t.actionResults.length, 0);
    assert.equal(e.ex.state.executions.x.completion?.stage, 'done');
  } finally { e.cleanup(); }
});

// 영속 실행 요청은 fake workflow 객체로만 검증한다. 실제 모델·CLI 호출 없음.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { setTimeout as delay } from 'node:timers/promises';
import type { Mastra } from '@mastra/core/mastra';
import { getExecutor, setRuntime } from '../src/runtimeCore.ts';
import { startWorkflow, type RuntimeOrigin, type WorkflowRequest } from '../src/runtimeRequests.ts';
import { workflowTick } from '../src/runtimeWorkflowTick.ts';
import { serviceTick } from '../src/runtimeServiceTick.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { setup, task, type Env } from './helpers.ts';

function manual(e: Env, start = async () => ({ status: 'success', result: { ok: true } }), beforeCreate?: () => Promise<void>) {
  stop(e.ex); e.ex.stopped = false;
  let calls = 0;
  const mastra = { getWorkflow: () => ({ createRun: async () => { calls++; await beforeCreate?.(); return { runId: 'fake-run', start, resume: start }; } }) } as unknown as Mastra;
  setRuntime(e.ex, mastra);
  return () => calls;
}

test('queued workflow는 저장 상태에서 최초 한 번 실행되고 완료 결과를 다시 실행하지 않는다', async () => {
  const e = setup();
  try {
    const calls = manual(e), waiting = startWorkflow('prepareTaskWorkflow', { goal: 'synthetic' });
    const request = Object.values(e.ex.state.workflowRequests!)[0];
    assert.equal(request.stage, 'queued');
    await workflowTick(e.ex);
    assert.deepEqual(await waiting, { runId: 'fake-run', status: 'success', result: { ok: true } });
    assert.equal(request.stage, 'done');
    await workflowTick(e.ex);
    assert.equal(calls(), 1);
  } finally { e.cleanup(); }
});

test('workflow dispatching 재시작 상태는 결과 불명으로 남고 라이브러리를 재호출하지 않는다', async () => {
  const e = setup();
  try {
    const calls = manual(e);
    const request: WorkflowRequest = { id: 'old', kind: 'start', workflow: 'pairTaskWorkflow', stage: 'dispatching', lifetime: 'previous' };
    e.ex.state.workflowRequests = { old: request }; e.ex.store.save();
    await workflowTick(e.ex); await workflowTick(e.ex);
    assert.equal(request.stage, 'unknown'); assert.equal(calls(), 0);
  } finally { e.cleanup(); }
});

test('queued 뒤 승인 철회·세대 변경·stop은 workflow 실행을 막는다', async () => {
  for (const mutation of ['revoke', 'generation', 'stop']) {
    const e = setup();
    try {
      const calls = manual(e);
      e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any; e.ex.runtime.generation = 1;
      const approval = grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: ['task-a'] });
      const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: 'task-a' };
      const waiting = startWorkflow('prepareTaskWorkflow', {}, undefined, origin);
      const rejected = assert.rejects(waiting, mutation === 'revoke' ? /승인 범위 밖/ : mutation === 'generation' ? /이전 세대/ : /정지됨/);
      if (mutation === 'revoke') approval.revokedAt = 'now';
      else if (mutation === 'generation') e.ex.runtime.generation = 2;
      else stop(e.ex);
      await workflowTick(e.ex); await rejected;
      assert.equal(calls(), 0);
    } finally { e.cleanup(); }
  }
});

test('도메인 요청도 실행 직전에 승인 철회를 검사하고 부모가 결과 불명이면 수행하지 않는다', async () => {
  const e = setup();
  try {
    manual(e);
    e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any; e.ex.runtime.generation = 1;
    const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: 'task-a' };
    e.ex.state.workflowRequests = { parent: { id: 'parent', kind: 'start', workflow: 'prepareTaskWorkflow', stage: 'dispatching', lifetime: e.ex.lifetime } };
    const requests = e.ex.state.serviceRequests = {
      denied: { id: 'denied', parentId: 'parent', service: 'assign' as const, payload: { raw: {} }, stage: 'queued' as const, origin },
      stale: { id: 'stale', parentId: 'gone', service: 'assign' as const, payload: { raw: {} }, stage: 'queued' as const },
    };
    await serviceTick(e.ex); await serviceTick(e.ex);
    assert.equal(requests.denied.stage, 'failed'); assert.match(e.ex.state.serviceRequests.denied.error!, /승인 범위 밖/);
    assert.equal(requests.stale.stage, 'failed'); assert.match(e.ex.state.serviceRequests.stale.error!, /소유 요청이 없음/);
    assert.deepEqual(e.ex.state.tasks, {});
  } finally { e.cleanup(); }
});

test('도메인 dispatching 재시작 상태는 서비스 재호출 없이 결과 불명으로 보존한다', async () => {
  const e = setup();
  try {
    manual(e);
    e.ex.state.serviceRequests = { old: { id: 'old', parentId: 'gone', service: 'assign', payload: { raw: {} }, stage: 'dispatching', lifetime: 'previous' } };
    await serviceTick(e.ex); await serviceTick(e.ex);
    assert.equal(e.ex.state.serviceRequests.old.stage, 'unknown'); assert.deepEqual(e.ex.state.tasks, {});
  } finally { e.cleanup(); }
});

test('다른 실행기를 초기화해도 진행 중 workflow의 비동기 컨텍스트는 원래 실행기를 유지한다', async () => {
  const a = setup(), b = setup();
  try {
    manual(a, async () => { await delay(30); assert.equal(getExecutor(), a.ex); return { status: 'success', result: { ok: true } }; });
    const waiting = startWorkflow('prepareTaskWorkflow', {}), running = workflowTick(a.ex);
    manual(b);
    await running; await waiting;
  } finally { a.cleanup(); b.cleanup(); }
});


test('createRun 점검 뒤 실행 직전 승인 철회는 native start를 호출하지 않는다', async () => {
  const e = setup();
  try {
    let open!: () => void, started = 0;
    const gate = new Promise<void>((resolve) => { open = resolve; });
    manual(e, async () => { started++; return { status: 'success', result: { ok: true } }; }, async () => gate);
    e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any; e.ex.runtime.generation = 1;
    const approval = grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: ['task-a'] });
    const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: 'task-a' };
    const waiting = startWorkflow('prepareTaskWorkflow', {}, undefined, origin), rejected = assert.rejects(waiting, /승인 범위 밖/);
    const running = workflowTick(e.ex);
    approval.revokedAt = 'after createRun'; open();
    await running; await rejected;
    assert.equal(started, 0);
  } finally { e.cleanup(); }
});

test('재검토 run ID와 이력은 workflow 실행 전에 영속 상태에 연결된다', async () => {
  const e = setup();
  try {
    manual(e, async () => {
      assert.equal(e.ex.state.tasks['task-a'].runId, 'fake-run');
      assert.deepEqual(e.ex.state.tasks['task-a'].runHistory, ['old-run', 'fake-run']);
      return { status: 'success', result: { ok: true } };
    });
    e.ex.state.tasks['task-a'] = { taskId: 'task-a', runId: 'old-run', runHistory: ['old-run'] } as any;
    const waiting = startWorkflow('pairTaskWorkflow', { taskId: 'task-a', reviewOnly: true }, 'task-a');
    await workflowTick(e.ex); await waiting;
  } finally { e.cleanup(); }
});

test('완료된 서비스 결과는 이후 작업 상태 변경과 공유하지 않는 저장 스냅샷이다', async () => {
  const e = setup();
  try {
    manual(e);
    e.ex.state.workflowRequests = { parent: { id: 'parent', kind: 'start', workflow: 'prepareTaskWorkflow', stage: 'dispatching', lifetime: e.ex.lifetime } };
    e.ex.state.serviceRequests = { assign: { id: 'assign', parentId: 'parent', service: 'assign', payload: { raw: task(e, 'task-a') }, stage: 'queued' } };
    await serviceTick(e.ex);
    const request = e.ex.state.serviceRequests.assign;
    assert.equal(request.stage, 'done', request.error ?? '');
    const result = request.result as { status: string };
    assert.equal(result.status, 'assigned'); assert.notEqual(result, e.ex.state.tasks['task-a']);
    e.ex.state.tasks['task-a'].status = 'blocked';
    assert.equal(result.status, 'assigned');
  } finally { e.cleanup(); }
});

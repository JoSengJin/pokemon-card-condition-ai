import assert from 'node:assert/strict';
import { test } from 'node:test';
import { assign } from '../src/executor/taskAssign.ts';
import { launch } from '../src/executor/taskLaunch.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { serviceTick } from '../src/runtimeServiceTick.ts';
import type { RuntimeOrigin } from '../src/runtimeRequests.ts';
import fs from 'node:fs';
import path from 'node:path';
import { fakeCli, waitFor, setup, task } from './helpers.ts';

test('사전 검사 대기 중 stop하면 프로세스를 시작하지 않고 예약 잠금을 해제한다', async () => {
  const e = setup();
  try {
    const t = await assign(e.ex, task(e, 'task-a'));
    const running = launch(e.ex, t.taskId, 'synthetic-run');
    stop(e.ex);
    const result = await running;
    assert.equal(result.ok, false);
    assert.deepEqual(e.ex.state.executions, {});
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`), null);
    assert.equal(e.ex.locks.holder(`worktree:${t.worktree}`), null);
    assert.equal(e.ex.locks.holder(`branch:${t.branch}`), null);
  } finally { e.cleanup(); }
});

for (const mutation of ['revoke', 'generation', 'session', 'frozen']) {
  test(`사전 검사 대기 중 ${mutation} 변경은 이전 메인의 프로세스 실행을 막는다`, async () => {
    const e = setup();
    try {
      const t = await assign(e.ex, task(e, 'task-a'));
      stop(e.ex); e.ex.stopped = false;
      e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any;
      e.ex.runtime.generation = 1;
      const approval = grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: [t.taskId] });
      const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: t.taskId };
      const running = launch(e.ex, t.taskId, 'synthetic-run', origin);
      if (mutation === 'revoke') approval.revokedAt = 'now';
      if (mutation === 'generation') e.ex.runtime.generation++;
      if (mutation === 'session') e.ex.runtime.session!.id = 'replacement';
      if (mutation === 'frozen') e.ex.runtime.frozen = true;
      const result = await running;
      assert.equal(result.ok, false);
      if (!result.ok) assert.match(result.reason, /승인 범위 밖|이전 세대/);
      assert.deepEqual(e.ex.state.executions, {});
      assert.equal(e.ex.locks.holder(`task:${t.taskId}`), null);
    } finally { e.cleanup(); }
  });
}

test('stop 상태에서는 잠금·작업 상태를 바꾸지 않고 시작을 거절한다', async () => {
  const e = setup();
  try {
    const t = await assign(e.ex, task(e, 'task-a'));
    stop(e.ex);
    const status = t.status;
    const result = await launch(e.ex, t.taskId, 'synthetic-run');
    assert.equal(result.ok, false);
    assert.equal(t.status, status);
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`), null);
    assert.deepEqual(e.ex.state.executions, {});
  } finally { e.cleanup(); }
});

for (const mutation of ['stop', 'revoke', 'limit', 'guard']) {
  test(`CLI 탐색 대기 중 ${mutation} 변경도 실행 직전에 차단한다(fake CLI만 사용)`, async () => {
    const e = setup({ allowRealModelCalls: true, confirmedSubscriptionAuth: true, cli: fakeCli });
    try {
      const marker = path.join(e.dir, 'probe-started'), invoked = path.join(e.dir, 'invoked');
      const cli = path.join(e.dir, 'delayed-codex.mjs');
      fs.writeFileSync(cli, `#!${process.execPath}\nimport fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
const args = process.argv.slice(2);
if (args.includes('--version')) { fs.writeFileSync(${JSON.stringify(marker)}, 'yes'); await delay(400); }
if (args[0] === 'exec' && !args.includes('--help')) { fs.writeFileSync(${JSON.stringify(invoked)}, 'yes'); process.exit(0); }
process.stdout.write(execFileSync(process.execPath, [${JSON.stringify(fakeCli.codex)}, ...args]));
`);
      fs.chmodSync(cli, 0o755); e.cfg.cli.codex = cli;
      const t = await assign(e.ex, task(e, 'task-b', { mode: 'real', allowedFiles: ['src_b/'] }));
      stop(e.ex); e.ex.stopped = false;
      e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any;
      e.ex.runtime.generation = 1;
      const approval = grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: [t.taskId] });
      const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: t.taskId };
      const running = launch(e.ex, t.taskId, 'synthetic-run', origin);
      await waitFor(() => fs.existsSync(marker), 'fake CLI probe marker', 10000);
      if (mutation === 'stop') stop(e.ex);
      if (mutation === 'revoke') approval.revokedAt = 'now';
      if (mutation === 'limit') e.ex.runtime.limited.codex = { at: 'now', detail: 'synthetic limit' };
      if (mutation === 'guard') e.ex.guardAlert = { detail: 'synthetic billing signal' } as any;
      const result = await running;
      assert.equal(result.ok, false);
      assert.equal(fs.existsSync(invoked), false);
      assert.deepEqual(e.ex.state.executions, {});
      assert.equal(e.ex.locks.holder(`task:${t.taskId}`), null);
    } finally { e.cleanup(); }
  });
}

test('서비스 worker는 저장된 origin을 시작 함수까지 전달해 대기 중 철회를 차단한다', async () => {
  const e = setup();
  try {
    const t = await assign(e.ex, task(e, 'task-a'));
    stop(e.ex); e.ex.stopped = false;
    e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any; e.ex.runtime.generation = 1;
    const approval = grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: [t.taskId] });
    const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: t.taskId };
    e.ex.state.workflowRequests = { parent: { id: 'parent', kind: 'start', workflow: 'pairTaskWorkflow', stage: 'dispatching', lifetime: e.ex.lifetime } };
    e.ex.state.serviceRequests = { launch: { id: 'launch', parentId: 'parent', service: 'launch', payload: { taskId: t.taskId, runId: 'synthetic-run' }, origin, stage: 'queued' } };
    const running = serviceTick(e.ex);
    approval.revokedAt = 'now';
    await running;
    const request = e.ex.state.serviceRequests.launch;
    assert.equal(request.stage, 'done');
    assert.equal((request.result as any).ok, false);
    assert.match((request.result as any).reason, /승인 범위 밖/);
    assert.deepEqual(e.ex.state.executions, {});
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`), null);
  } finally { e.cleanup(); }
});

test('변경 없는 유효 origin은 수동 작업 시작을 허용한다', async () => {
  const e = setup();
  try {
    const t = await assign(e.ex, task(e, 'task-a', { mode: 'manual' }));
    stop(e.ex); e.ex.stopped = false;
    e.ex.runtime.session = { id: 's', generation: 1, status: 'idle' } as any; e.ex.runtime.generation = 1;
    grantApproval(e.ex, { basis: 'synthetic', actions: ['assign_task'], targets: [t.taskId] });
    const origin: RuntimeOrigin = { sessionId: 's', generation: 1, lifetime: e.ex.lifetime, action: 'assign_task', target: t.taskId };
    const result = await launch(e.ex, t.taskId, 'synthetic-run', origin);
    assert.deepEqual(result, { ok: true, manual: true, execId: null });
    assert.equal(t.status, 'manual_working');
    assert.deepEqual(e.ex.state.executions, {});
  } finally { e.cleanup(); }
});

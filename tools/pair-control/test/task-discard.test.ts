import { getTask } from '../src/executor/executorLookup.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
// 작업 폐기(사유 기록·거절 흐름·보관함 이동), 끝난 작업 일괄 보관, 충돌 안내. mock 프로세스 기반, 모델 요청 없음.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { resumeStep, runInfo, startTask } from '../src/runtime.ts';
import { archiveFinished, discardTask } from '../src/executor/taskControl.ts';
import { setup, task, verify, waitFor } from './helpers.ts';

test('폐기: 사유가 필수이고, 시작 전 작업은 바로 보관함으로 가며 브랜치·기록은 그대로', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await assert.rejects(discardTask(env.ex, 'task-a', ' ', resumeStep), /폐기 사유/);
    const t = await discardTask(env.ex, 'task-a', '중복 작업이라 버림', resumeStep);
    assert.equal(t.discard!.reason, '중복 작업이라 버림');
    assert.ok(t.archivedAt);
    assert.equal(t.status, 'assigned', '상태는 그대로(기록 보존)');
  } finally { env.cleanup(); }
});

test('폐기: 승인 대기·승인됨 작업은 거절 흐름으로 끝내고 점유를 풀며 사유를 남긴다', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await startTask('task-a');
    await waitFor(() => getTask(env.ex, 'task-a').status === 'review_pending', 'review');
    assert.equal((await verify(env, 'task-a')).status, 'passed');
    const t0 = getTask(env.ex, 'task-a');
    const a = await approve(env.ex, 'task-a', t0.result!.headSha!);
    await resumeStep(t0.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    assert.equal(getTask(env.ex, 'task-a').status, 'approved');

    const t = await discardTask(env.ex, 'task-a', '방향이 바뀜', resumeStep);
    assert.equal(t.status, 'rejected');
    assert.match(t.statusReason!, /폐기: 방향이 바뀜/);
    assert.equal(t.approval, null);
    assert.ok(t.archivedAt && t.discard);
    assert.equal((await runInfo(t0.runId))?.status, 'success', '대기 중이던 workflow도 끝남');
    // 점유가 풀렸으니 같은 파일을 쓰는 다른 작업을 시작할 수 있다
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_a/'] }));
    assert.ok(!(await startTask('task-b').then(() => false, (e) => /충돌/.test(String(e)))), 'task-a 폐기 후에는 충돌하지 않음');
  } finally { env.cleanup(); }
});

test('폐기: 진행 중 작업은 거부하고 중단·확정을 먼저 안내한다', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    getTask(env.ex, 'task-a').status = 'running';
    await assert.rejects(discardTask(env.ex, 'task-a', '그만', resumeStep), /진행 중인 작업은 폐기할 수 없음\(running\)/);
    assert.equal(getTask(env.ex, 'task-a').archivedAt ?? null, null);
  } finally { env.cleanup(); }
});

test('끝난 작업 일괄 보관: 거절·결과 불명 확정과 푸시 확인된 통합 작업만, 시작 전·중단·검토 중은 그대로', async () => {
  const env = setup();
  try {
    for (const id of ['task-a', 'task-b', 'task-c']) await assign(env.ex, task(env, id, { allowedFiles: [`src_${id.slice(-1)}/`] }));
    getTask(env.ex, 'task-a').status = 'rejected';
    getTask(env.ex, 'task-b').status = 'cancelled';
    getTask(env.ex, 'task-c').status = 'integrated';
    const r0 = archiveFinished(env.ex);
    assert.deepEqual(r0.archived, ['task-a'], '푸시 기록 없는 통합 작업과 중단됨은 건드리지 않음');
    env.ex.state.pushes = { p1: { id: 'p1', status: 'pushed_verified', tasks: ['task-c'] } as any };
    assert.deepEqual(archiveFinished(env.ex).archived, ['task-c']);
    assert.equal(getTask(env.ex, 'task-b').archivedAt ?? null, null);
  } finally { env.cleanup(); }
});

test('충돌 안내: 점유 작업의 상태와 폐기 방법을 함께 알려 준다', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await startTask('task-a');
    await waitFor(() => getTask(env.ex, 'task-a').status === 'review_pending', 'review');
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_a/'] }));
    await assert.rejects(startTask('task-b'), /충돌: task-a\(files .*점유 작업 task-a\[review_pending\].*"폐기"/);
  } finally { env.cleanup(); }
});

import { getTask } from '../src/executor/executorLookup.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve, reject } from '../src/executor/taskApproval.ts';
import { recheckEnv } from '../src/executor/taskEnvironment.ts';
// 승인 취소·작업 보관. mock 프로세스 기반, 실제 모델 요청 없음.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { resumeStep, runInfo, startReview, startTask } from '../src/runtime.ts';
import { createVenv, setArchived, withdrawApproval } from '../src/executor/taskControl.ts';
import fs from 'node:fs';
import path from 'node:path';
import { invocations, setup, task, verify, waitFor, type Env } from './helpers.ts';

async function toApproved(env: Env, id: string) {
  await startTask(id);
  await waitFor(() => getTask(env.ex, id).status === 'review_pending', `${id} review`);
  assert.equal((await verify(env, id)).status, 'passed');
  const t = getTask(env.ex, id);
  const a = await approve(env.ex, id, t.result!.headSha!);
  await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
  assert.equal((await runInfo(t.runId))?.suspendedStep, 'integrate-gate');
  return getTask(env.ex, id);
}

test('승인 취소: 같은 SHA로 검토 단계 복귀, 에이전트 재실행 없음, 작업 테스트 유효, 다시 승인하면 통합 가능', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    const before = await toApproved(env, 'task-a');
    const sha = before.result!.headSha!, oldRun = before.runId!, runs = invocations(env);

    const t = await withdrawApproval(env.ex, 'task-a', resumeStep, startReview);
    assert.equal(t.status, 'review_pending');
    assert.equal(t.approval, null);
    assert.equal(t.result!.headSha, sha, '같은 SHA');
    assert.equal(invocations(env), runs, '에이전트를 다시 실행하지 않음');
    assert.equal(t.verification!.sha, sha, '같은 SHA의 작업 테스트 결과는 그대로');
    assert.equal(t.verification!.status, 'passed');
    assert.notEqual(t.runId, oldRun, '재검토 실행으로 이어받음');
    assert.equal((await runInfo(oldRun))?.status, 'success', '이전 실행은 withdraw로 끝남');
    assert.equal((await runInfo(t.runId))?.suspendedStep, 'review-gate');

    const a = await approve(env.ex, 'task-a', sha);
    await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
    await waitFor(() => getTask(env.ex, 'task-a').status === 'integrated', 'integrated');
  } finally { env.cleanup(); }
});

test('승인 취소는 승인됨 상태에서만, 보관은 진행 중·결정 남은 작업 거부·기록 유지·해제 가능', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await assert.rejects(withdrawApproval(env.ex, 'task-a', resumeStep, startReview), /승인됨 상태에서만/);
    await startTask('task-a');
    await waitFor(() => getTask(env.ex, 'task-a').status === 'review_pending', 'review');
    await assert.rejects(withdrawApproval(env.ex, 'task-a', resumeStep, startReview), /승인됨 상태에서만/);
    assert.throws(() => setArchived(env.ex, 'task-a', true), /보관할 수 없음\(review_pending\)/);

    reject(env.ex, 'task-a', '테스트 거절');
    const archived = setArchived(env.ex, 'task-a', true);
    assert.ok(archived.archivedAt);
    assert.equal(archived.status, 'rejected', '상태·기록은 그대로');
    assert.ok(getTask(env.ex, 'task-a').result, '결과 기록 유지');
    const again = env.restart();
    try {
      assert.ok(getTask(again.ex, 'task-a').archivedAt, '재시작 후에도 보관 유지');
      assert.equal(setArchived(again.ex, 'task-a', false).archivedAt, null);
    } finally { stop(again.ex); }
  } finally { env.cleanup(); }
});

test('환경 만들기: 고정 명령으로 .venv만 만들고 준비 완료, 이미 있으면·기본 checkout·진행 중이면 거부', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { env: 'python' }));
    const wt = getTask(env.ex, 'task-a').worktree;
    assert.equal(fs.existsSync(path.join(wt, '.venv')), false);
    const before = await recheckEnv(env.ex, 'task-a');
    assert.equal(before!.ready, false);
    assert.ok(before!.checks.some((c) => c.name === '자체 .venv' && !c.ok && c.detail === '없음'));

    const after = await createVenv(env.ex, 'task-a');
    assert.equal(after!.ready, true, JSON.stringify(after!.checks));
    assert.ok(fs.existsSync(path.join(wt, '.venv', 'pyvenv.cfg')));
    assert.equal(fs.existsSync(path.join(env.fixture.repo, '.venv')) && fs.lstatSync(path.join(env.fixture.repo, '.venv')).isSymbolicLink(), false, '다른 checkout 공유 없음');
    await assert.rejects(createVenv(env.ex, 'task-a'), /이미 .venv가 있음/);

    await assign(env.ex, task(env, 'task-b', { env: 'python', allowedFiles: ['src_b/'] }));
    getTask(env.ex, 'task-b').worktree = env.fixture.repo; // 기본 checkout을 가리키는 비정상 기록
    await assert.rejects(createVenv(env.ex, 'task-b'), /기본 checkout/);
    getTask(env.ex, 'task-a').status = 'running';
    await assert.rejects(createVenv(env.ex, 'task-a'), /시작 전·중단된 작업에서만/);
    getTask(env.ex, 'task-a').status = 'assigned';
  } finally { env.cleanup(); }
});

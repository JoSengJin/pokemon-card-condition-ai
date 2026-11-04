import { assign } from '../src/executor/taskAssign.ts';
import { startReviewJob } from '../src/executor/reviewStart.ts';
// 별도 리뷰 작업 연결(fake 리뷰 CLI). 모델 요청 없음.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { startTask } from '../src/runtime.ts';
import { setup, task, verify, waitFor, type Env } from './helpers.ts';

async function reviewed(env: Env, id: string, mockScenario: string) {
  await startReviewJob(env.ex, id, { mockScenario: mockScenario as any });
  return waitFor(() => { const r = env.ex.task(id).review; return r && r.status !== 'running' ? r : null; }, `${id} review`);
}

test('Claude 결과를 고정 SHA 묶음으로 Codex 리뷰 작업에 등록, 판정 3종 구분, 구현 worktree 미전달', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    await verify(env, 'task-a');
    const t = env.ex.task('task-a');
    await assert.rejects(startReviewJob(env.ex, 'task-a', { reviewer: 'claude' }), /다른 에이전트/);
    const r = await reviewed(env, 'task-a', 'approve');
    assert.equal(r.reviewer, 'codex');
    assert.equal(r.status, 'done'); assert.equal(r.verdict, 'approve'); assert.equal(r.sha, t.result!.headSha);
    for (const f of ['REVIEW_REQUEST.md', 'contract.md', 'diff.patch', 'checks.json', 'meta.json']) assert.ok(fs.existsSync(path.join(r.bundleDir, f)), f);
    const bundleText = ['REVIEW_REQUEST.md', 'meta.json', 'checks.json'].map((f) => fs.readFileSync(path.join(r.bundleDir, f), 'utf8')).join('\n');
    assert.ok(!bundleText.includes(t.worktree), '리뷰 묶음에 구현 worktree 경로 없음');
    assert.equal(JSON.parse(fs.readFileSync(path.join(r.bundleDir, 'checks.json'), 'utf8')).task_tests.status, 'passed');
    const ex = env.ex.state.executions[r.execId!];
    assert.equal(ex.kind, 'review');
    assert.ok(!ex.display.join(' ').includes(t.worktree));
    assert.equal(env.ex.task('task-a').status, 'review_pending', '리뷰 판정이 승인을 대신하지 않음');
    assert.equal((await reviewed(env, 'task-a', 'changes_requested')).verdict, 'changes_requested');
    assert.equal((await reviewed(env, 'task-a', 'insufficient_evidence')).verdict, 'insufficient_evidence');
  } finally { env.cleanup(); }
});

test('리뷰 출력 형식 오류·다른 SHA·실패·worktree 변경은 판정으로 쓰지 않음', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    const garbage = await reviewed(env, 'task-a', 'garbage');
    assert.equal(garbage.status, 'failed'); assert.equal(garbage.verdict, null); assert.match(garbage.note!, /통과/);
    assert.equal((await reviewed(env, 'task-a', 'wrong-sha')).status, 'failed');
    assert.equal((await reviewed(env, 'task-a', 'fail')).status, 'failed');
    // 리뷰 도중 구현 worktree가 바뀌면 결과 무효
    await startReviewJob(env.ex, 'task-a', { mockScenario: 'slow-approve' });
    await assert.rejects(startReviewJob(env.ex, 'task-a', { mockScenario: 'approve' }), /이미 실행 중/);
    fs.writeFileSync(path.join(env.fixture.worktrees['task-a'].path, 'src_a', 'stray.txt'), 'x');
    const moved = await waitFor(() => { const r = env.ex.task('task-a').review; return r && r.status !== 'running' ? r : null; }, 'slow');
    assert.equal(moved.status, 'failed'); assert.match(moved.note!, /worktree가 바뀜/);
    fs.rmSync(path.join(env.fixture.worktrees['task-a'].path, 'src_a', 'stray.txt'));
    // 중단
    await startReviewJob(env.ex, 'task-a', { mockScenario: 'hang' });
    assert.ok((await env.ex.cancel('task-a')).ok);
    await waitFor(() => env.ex.task('task-a').review?.status === 'cancelled', 'cancel');
    assert.equal(env.ex.locks.holder('review:task-a'), null);
  } finally { env.cleanup(); }
});

test('실제 리뷰 모드는 차단 원인과 함께 거절(모델 요청 없음)', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a'));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    await assert.rejects(startReviewJob(env.ex, 'task-a', { mode: 'real' }), /실제 codex 리뷰 차단: .*실제 모델 호출 차단/);
    assert.equal(env.ex.locks.holder('review:task-a'), null);
    assert.equal(env.ex.task('task-a').review ?? null, null);
  } finally { env.cleanup(); }
});

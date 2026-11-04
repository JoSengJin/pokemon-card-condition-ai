import { logTail } from '../src/executor/executorView.ts';
// 작업 계약 파일 커밋·불변 검사·재시도 멱등성. 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { createWorktree, planTask } from '../src/executor/prepare.ts';
import { commitContract } from '../src/executor/contractFile.ts';
import { prepareTask, startTask } from '../src/runtime.ts';
import { setup, task, waitFor } from './helpers.ts';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', a, { cwd }).toString().trim();

test('계약은 작업 브랜치에만 커밋되고 개인 경로가 없으며 실행 기준 SHA가 된다', async () => {
  const env = setup();
  try {
    const mainBefore = gitOut(env.fixture.repo, 'rev-parse', 'main');
    const t = await env.ex.assign(task(env, 'task-a', { doneCriteria: ['src_a 파일 갱신'], prompt: '긴 지시 '.repeat(500) }));
    const wt = env.fixture.worktrees['task-a'].path;
    assert.equal(gitOut(env.fixture.repo, 'rev-parse', 'main'), mainBefore, 'main 불변');
    assert.equal(t.contractSha, gitOut(wt, 'rev-parse', 'HEAD'));
    assert.equal(gitOut(wt, 'show', '--name-only', '--format=', t.contractSha), 'docs/collaboration/tasks/task-a.md');
    const text = fs.readFileSync(path.join(wt, t.contractPath), 'utf8');
    assert.ok(!text.includes(wt) && !text.includes(env.dir), '계약에 개인 절대경로 없음');
    assert.match(text, /## 완료 조건\n\n- src_a 파일 갱신/);
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    const ex = env.ex.state.executions[env.ex.task('task-a').lastExecId!];
    assert.match(logTail(env.ex, ex.execId).text, /계약 읽음: # 작업 계약: task-a/);
    assert.ok(ex.display.join(' ').length < 400, 'CLI 인자는 계약 경로만(긴 지시는 파일)');
    const r = env.ex.task('task-a').result!;
    assert.ok(r.checksPassed, JSON.stringify(r.checks));
    assert.deepEqual(r.changedFiles, ['src_a/mock-task-a.txt'], '계약 이후 변경만 Git 계약 검사 대상');
  } finally { env.cleanup(); }
});

test('에이전트가 계약 파일을 바꾸면 Git 계약 검사 실패', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a', { mockScenario: 'edit-contract' }));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    const r = env.ex.task('task-a').result!;
    assert.equal(r.checksPassed, false);
    assert.equal(r.checks.find((c) => c.name === '계약 파일 불변')?.ok, false);
    await assert.rejects(env.ex.approve('task-a', r.headSha!), /검사 실패/);
  } finally { env.cleanup(); }
});

test('준비 재시도: 등록 전 중단된 준비는 같은 worktree·계약 커밋을 재사용', async () => {
  const env = setup();
  try {
    const input = { taskId: 'retry-1', agent: 'claude', goal: '재시도', allowedFiles: ['src_b/'] };
    // 첫 시도가 worktree 생성·계약 커밋 후 등록 전에 멈춘 상황
    const p1 = await planTask(env.ex, input);
    const wt = await createWorktree(env.ex, p1.task!);
    const c1 = await commitContract(wt, p1.task!);
    const wtCount = gitOut(env.fixture.repo, 'worktree', 'list').split('\n').length;
    const p2 = await planTask(env.ex, input);
    assert.ok(p2.ok, JSON.stringify(p2.checks));
    assert.equal(p2.createWorktree, false);
    const r = await prepareTask(input);
    const t = env.ex.task(r.taskId!);
    assert.equal(t.contractSha, c1.contractSha, '같은 계약 커밋 재사용');
    assert.equal(gitOut(wt, 'rev-list', '--count', `${env.fixture.baseSha}..HEAD`), '1', '중복 커밋 없음');
    assert.equal(gitOut(env.fixture.repo, 'worktree', 'list').split('\n').length, wtCount, '중복 worktree 없음');
    // 등록 후 같은 ID는 거절
    await assert.rejects(prepareTask(input), /이미|task ID/);
  } finally { env.cleanup(); }
});

test('계약 내용이 다르면 재사용하지 않고 거절', async () => {
  const env = setup();
  try {
    const p = await planTask(env.ex, { taskId: 'diff-1', agent: 'codex', goal: '처음', allowedFiles: ['src_c/'] });
    const wt = await createWorktree(env.ex, p.task!);
    await commitContract(wt, p.task!);
    await assert.rejects(prepareTask({ taskId: 'diff-1', agent: 'codex', goal: '바뀐 목표', allowedFiles: ['src_c/'] }), /다른 내용의 계약/);
    assert.equal(env.ex.state.tasks['diff-1'], undefined);
  } finally { env.cleanup(); }
});

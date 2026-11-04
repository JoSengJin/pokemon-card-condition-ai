import { runChecks } from '../src/executor/verificationStart.ts';
import { approve as approveTask } from '../src/executor/taskApproval.ts';
// 작업 테스트(에이전트 종료 후 독립 실행)·통합 후 검사. 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { resumeStep, startReview, startTask } from '../src/runtime.ts';
import { setup, task, verify, waitFor, type Env } from './helpers.ts';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd }).toString().trim();
const nodeCheck = (id: string, code: string) => ({ id, name: id, executable: 'node', args: ['-e', code] });
const status = (env: Env, id: string) => env.ex.task(id).status;

async function toReview(env: Env, id: string) {
  await startTask(id);
  await waitFor(() => status(env, id) === 'review_pending', `${id} review`);
  return env.ex.task(id);
}
async function approve(env: Env, id: string) {
  const t = env.ex.task(id);
  const a = await approveTask(env.ex, id, t.result!.headSha!);
  await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
}
const checkExecs = (env: Env, id: string) => Object.values(env.ex.state.executions).filter((e) => e.taskId === id && e.kind === 'check');

test('CLI 종료코드 0이어도 작업 테스트가 실패하면 승인 차단, 기록에 SHA·명령·종료코드·로그·시각', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a', { checks: [nodeCheck('ok', 'console.log("fine")'), nodeCheck('bad', 'console.error("boom");process.exit(4)')] }));
    const t = await toReview(env, 'task-a');
    assert.equal(env.ex.state.executions[t.lastExecId!].exitCode, 0);
    assert.ok(t.result!.checksPassed, 'Git 계약 검사는 통과');
    const v = await verify(env, 'task-a');
    assert.equal(v.status, 'failed');
    const [ok, bad] = v.items;
    assert.equal(ok.status, 'passed'); assert.equal(bad.status, 'failed'); assert.equal(bad.exitCode, 4);
    assert.equal(bad.sha, t.result!.headSha);
    assert.deepEqual(bad.display.slice(0, 2), ['node', '-e']);
    assert.ok(bad.startedAt && bad.endedAt);
    assert.match(fs.readFileSync(bad.logPath!, 'utf8'), /boom/);
    await assert.rejects(approveTask(env.ex, 'task-a', t.result!.headSha!), /작업 테스트가 통과하지 않음\(failed\)/);
  } finally { env.cleanup(); }
});

test('검사 명령 계약: 허용 실행 파일만, 학습·실험 진입점 금지, 계약에 검사가 없으면 승인 불가', async () => {
  const env = setup();
  try {
    await assert.rejects(env.ex.assign(task(env, 'task-a', { checks: [{ id: 'sh', name: 'sh', executable: 'bash', args: ['-c', 'ls'] }] })), /checks/);
    await assert.rejects(env.ex.assign(task(env, 'task-a', { checks: [{ id: 'x', name: 'x', executable: '.venv/bin/python', args: ['-m', 'card_condition.experiment_record'] }], env: 'python' })), /학습·실험/);
    await assert.rejects(env.ex.assign(task(env, 'task-a', { checks: [{ id: 'p', name: 'p', executable: '.venv/bin/python', args: ['-V'] }] })), /python 또는 python-project/);
    await env.ex.assign(task(env, 'task-b', { allowedFiles: ['src_b/'], checks: [] }));
    await toReview(env, 'task-b');
    await assert.rejects(runChecks(env.ex, 'task-b'), /계약에 작업 테스트가 없음/);
    await assert.rejects(approveTask(env.ex, 'task-b', env.ex.task('task-b').result!.headSha!), /미실행/);
  } finally { env.cleanup(); }
});

test('코드가 바뀌면 이전 작업 테스트로 승인 불가, 계약 파일을 바꾸면 Git 계약 검사 실패', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a'));
    const t = await toReview(env, 'task-a');
    assert.equal((await verify(env, 'task-a')).status, 'passed');
    const wt = env.fixture.worktrees['task-a'].path;
    fs.appendFileSync(path.join(wt, t.contractPath), '\n추가 지시\n');
    gitOut(wt, 'commit', '-qam', 'contract edit');
    await assert.rejects(approveTask(env.ex, 'task-a', gitOut(wt, 'rev-parse', 'HEAD')), /현재 SHA·계약과 다름|현재 결과와 다름/);
    await assert.rejects(approveTask(env.ex, 'task-a', t.result!.headSha!), /현재 결과와 다름/);
    await assert.rejects(runChecks(env.ex, 'task-a'), /코드 SHA가 바뀜/);
  } finally { env.cleanup(); }
});

test('작업 테스트 중단·중복 실행 차단·재시작 시 이어서 실행하지 않음·결과 불명', async () => {
  let env = setup();
  try {
    const slow = nodeCheck('slow', 'setTimeout(()=>{}, 1500)');
    await env.ex.assign(task(env, 'task-a', { checks: [slow, nodeCheck('second', 'process.exit(0)')] }));
    await env.ex.assign(task(env, 'task-b', { allowedFiles: ['src_b/'], checks: [nodeCheck('hang', 'setInterval(()=>{},1000)')] }));
    await env.ex.assign(task(env, 'task-c', { allowedFiles: ['src_c/'], checks: [nodeCheck('hang', 'setInterval(()=>{},1000)')] }));
    for (const id of ['task-a', 'task-b', 'task-c']) await toReview(env, id);

    // 중단
    await runChecks(env.ex, 'task-b');
    await assert.rejects(runChecks(env.ex, 'task-b'), /이미 실행 중/);
    assert.ok((await env.ex.cancel('task-b')).ok);
    await waitFor(() => env.ex.task('task-b').verification?.status === 'cancelled', 'cancelled');
    assert.equal(env.ex.locks.holder('task:task-b'), null, '중단 후 잠금 해제');
    assert.equal(status(env, 'task-b'), 'review_pending', '작업 상태는 그대로');

    // 재시작: 진행 중이던 첫 검사가 끝나도 두 번째 검사를 자동 실행하지 않음
    await runChecks(env.ex, 'task-a');
    await runChecks(env.ex, 'task-c');
    await waitFor(() => checkExecs(env, 'task-a')[0], 'task-a first check started');
    const cExec = await waitFor(() => checkExecs(env, 'task-c')[0], 'task-c check started');
    env = env.restart();
    process.kill(-cExec.pgid, 'SIGKILL'); // 서버가 없는 동안 기록 없이 사라짐
    await waitFor(() => !env.ex.groupAlive(cExec.pgid), 'c gone');
    env = env.restart();
    await waitFor(() => env.ex.task('task-a').verification?.status === 'interrupted', 'interrupted', 10_000);
    const va = env.ex.task('task-a').verification!;
    assert.equal(va.items[0].status, 'passed', '종료 기록은 반영');
    assert.equal(va.items[1].status, 'not_run', '남은 검사는 실행하지 않음');
    assert.equal(checkExecs(env, 'task-a').length, 1, '자동 재실행 없음');
    await waitFor(() => env.ex.task('task-c').verification?.status === 'unknown', 'unknown');
    assert.equal(env.ex.task('task-c').verification!.items[0].status, 'unknown');
    await assert.rejects(approveTask(env.ex, 'task-a', env.ex.task('task-a').result!.headSha!), /interrupted/);
    // 사용자가 다시 실행하면 처음부터
    assert.equal((await verify(env, 'task-a')).status, 'passed');
  } finally { env.cleanup(); }
});

test('통합 후 검사: 실패는 성공으로 표시하지 않고 복구 SHA를 남김, 자동 되돌림 없음', async () => {
  const env = setup();
  try {
    const repo = env.fixture.repo;
    await env.ex.assign(task(env, 'task-a', { postChecks: [nodeCheck('post-bad', 'process.exit(2)')] }));
    await env.ex.assign(task(env, 'task-b', { allowedFiles: ['src_b/'], postChecks: [nodeCheck('post-ok', 'process.exit(0)')] }));
    await env.ex.assign(task(env, 'task-c', { allowedFiles: ['src_c/'] }));
    const before = gitOut(repo, 'rev-parse', 'HEAD');
    for (const id of ['task-a', 'task-b', 'task-c']) {
      await toReview(env, id);
      await verify(env, id);
      await approve(env, id);
      await resumeStep(env.ex.task(id).runId!, 'integrate-gate', { action: 'integrate' });
    }
    const a = env.ex.task('task-a');
    assert.equal(a.status, 'integrated_check_failed');
    assert.equal(a.integration!.preHead, before);
    assert.match(a.statusReason!, new RegExp(`통합 전 ${before}`));
    assert.match(a.statusReason!, /자동 되돌림 없음/);
    assert.equal(a.integration!.postChecks![0].exitCode, 2);
    assert.equal(env.ex.task('task-b').status, 'integrated');
    assert.equal(env.ex.task('task-b').integration!.postStatus, 'passed');
    assert.equal(env.ex.task('task-c').integration!.postStatus, 'not_run');
    assert.match(env.ex.task('task-c').statusReason!, /통합 후 검사 미지정\(미실행\)/);
    assert.equal(gitOut(repo, 'status', '--porcelain'), '', '통합 checkout 깨끗함(reset 없음)');
    assert.equal(gitOut(repo, 'rev-list', '--count', `${before}..HEAD`), '6', '세 작업의 계약+변경 커밋이 그대로 남음');
  } finally { env.cleanup(); }
});

test('통합 checkout의 .venv가 없으면 통합하지 않고 승인 유지', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a'));
    await toReview(env, 'task-a');
    await verify(env, 'task-a');
    await approve(env, 'task-a');
    fs.renameSync(path.join(env.fixture.repo, '.venv'), path.join(env.dir, 'moved-venv'));
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'approved');
    assert.match(env.ex.task('task-a').statusReason ?? '', /통합 checkout 실행 환경 미준비/);
  } finally { env.cleanup(); }
});

test('통합 거절 후 재검토하면 계약 변경이 Git 계약 검사에서 드러남', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a'));
    await toReview(env, 'task-a');
    await verify(env, 'task-a');
    await approve(env, 'task-a');
    const wt = env.fixture.worktrees['task-a'].path;
    fs.appendFileSync(path.join(wt, env.ex.task('task-a').contractPath), '\n바뀐 계약\n');
    gitOut(wt, 'commit', '-qam', 'contract edit');
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'integration_refused');
    await startReview('task-a');
    const r = env.ex.task('task-a').result!;
    assert.equal(r.checks.find((c) => c.name === '계약 파일 불변')!.ok, false);
    assert.equal(r.checksPassed, false);
  } finally { env.cleanup(); }
});

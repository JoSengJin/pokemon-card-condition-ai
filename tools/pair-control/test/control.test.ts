import { cancel } from '../src/executor/taskCancel.ts';
import { groupAlive } from '../src/executor/processIdentity.ts';
import { launch } from '../src/executor/taskLaunch.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
import { recheckEnv } from '../src/executor/taskEnvironment.ts';
import { acknowledgeUnknown, applyObservedExit } from '../src/executor/taskRecovery.ts';
import { logTail, groupsOf } from '../src/executor/executorView.ts';
// mock 프로세스 기반 검증. 실제 Codex/Claude 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { runInfo, startReview, startTask, resumeStep, discrepancy } from '../src/runtime.ts';
import { PAID_ENV_KEYS, sanitizedChildEnv } from '../src/executor/freeGuard.ts';
import { alive, invocations, setup, task, verify, waitFor, type Env } from './helpers.ts';
// @ts-ignore plain JS helper
import { makeVenv } from '../scripts/fixture-lib.mjs';

const status = (env: Env, id: string) => env.ex.task(id).status;
const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd }).toString().trim();

async function toReview(env: Env, id: string) {
  await startTask(id);
  await waitFor(() => ['review_pending', 'failed', 'blocked'].includes(status(env, id)), `${id} review`);
  return env.ex.task(id);
}

async function approveAndWait(env: Env, id: string) {
  const v = await verify(env, id);
  assert.equal(v.status, 'passed', JSON.stringify(v.items));
  const t = env.ex.task(id);
  const a = await approve(env.ex, id, t.result!.headSha!);
  await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
  return a;
}

test('독립 작업 두 개 병렬 실행 → 각각 전체 SHA로 검토 대기', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_a/'], mockScenario: 'slow-success' }));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'], mockScenario: 'slow-success' }));
    await Promise.all([startTask('task-a'), startTask('task-b')]);
    const [ea, eb] = ['task-a', 'task-b'].map((id) => env.ex.state.executions[env.ex.task(id).lastExecId!]);
    assert.equal(status(env, 'task-a'), 'running');
    assert.equal(status(env, 'task-b'), 'running');
    assert.ok(alive(ea.pid) && alive(eb.pid), '두 감독 프로세스가 동시에 살아 있음');
    assert.notEqual(ea.pid, eb.pid);
    assert.equal((await runInfo(env.ex.task('task-a').runId))?.suspendedStep, 'await-exit');
    await waitFor(() => status(env, 'task-a') === 'review_pending' && status(env, 'task-b') === 'review_pending', 'both review');
    for (const id of ['task-a', 'task-b']) {
      const r = env.ex.task(id).result!;
      assert.match(r.headSha!, /^[0-9a-f]{40}$/);
      assert.ok(r.checksPassed, JSON.stringify(r.checks));
      assert.equal(r.commits.length, 1);
      const info = await runInfo(env.ex.task(id).runId);
      assert.equal(info?.suspendedStep, 'review-gate');
      assert.equal(discrepancy(env.ex.task(id), info), null);
    }
    assert.equal(ea.tokens, '미측정');
  } finally { env.cleanup(); }
});

test('파일 소유권·API 그룹·공용 설정 충돌과 중복 시작 차단', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_a/'], mockScenario: 'hang', conflictGroups: ['api:observation'] }));
    await assign(env.ex, task(env, 'task-c', { allowedFiles: ['src_a/file.txt'] }));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'], conflictGroups: ['api:observation'] }));
    await assign(env.ex, task(env, 'task-d', { allowedFiles: ['src_c/', 'README.md'] }));
    // 동시에 두 번 시작해도 한 번만 실행
    const results = await Promise.allSettled([startTask('task-a'), startTask('task-a')]);
    await waitFor(() => invocations(env) === 1, 'one invocation');
    assert.equal(results.filter((r) => r.status === 'fulfilled').length, 1);
    const refused = results.find((r) => r.status === 'rejected') as PromiseRejectedResult;
    assert.match(refused.reason.message, /중복 실행 차단|잠금 사용 중/);
    assert.equal(status(env, 'task-a'), 'running');
    const again = await launch(env.ex, 'task-a', 'manual');
    assert.equal(again.ok, false);
    assert.match((again as any).reason, /중복 실행 차단/);

    const c = await launch(env.ex, 'task-c', 'manual');
    assert.equal(c.ok, false);
    assert.ok((c as any).conflicts.some((x: any) => x.kind === 'files' && x.otherTask === 'task-a'));
    await assert.rejects(startTask('task-c'), /충돌: task-a\(files/);
    assert.match(env.ex.task('task-c').statusReason ?? '', /시작 거절/);
    const b = await launch(env.ex, 'task-b', 'manual');
    assert.equal(b.ok, false, '파일이 달라도 API 계약 그룹이 같으면 직렬화');
    assert.ok((b as any).conflicts.some((x: any) => x.kind === 'group' && x.detail === 'api:observation'));
    assert.deepEqual(groupsOf(env.ex.task('task-d')), ['shared-config']);
    assert.equal(invocations(env), 1, '거절된 시작은 프로세스를 만들지 않음');

    // 잠금 파일은 프로세스를 넘어 원자적(O_EXCL)
    assert.equal(env.ex.locks.acquire('task:task-a', { execId: 'other' }), false);
    await cancel(env.ex, 'task-a');
    await waitFor(() => status(env, 'task-a') === 'cancelled', 'cancel');
    assert.equal(env.ex.locks.holder('task:task-a'), null, '종료 확인 후 잠금 해제');
  } finally { env.cleanup(); }
});

test('중단은 이 실행기가 만든 프로세스 그룹만 정리(손자 프로세스 포함)', async () => {
  const env = setup();
  const outsider = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { detached: true, stdio: 'ignore' });
  try {
    await assign(env.ex, task(env, 'task-a', { mockScenario: 'spawn-child' }));
    await startTask('task-a');
    const ex = env.ex.state.executions[env.ex.task('task-a').lastExecId!];
    const log = await waitFor(() => { const t = logTail(env.ex, ex.execId).text; return /grandchild pid=(\d+)/.exec(t); }, 'grandchild');
    const grandchild = Number(log[1]);
    assert.ok(alive(grandchild));
    const r = await cancel(env.ex, 'task-a');
    assert.ok(r.ok, r.reason);
    await waitFor(() => status(env, 'task-a') === 'cancelled', 'cancelled');
    await waitFor(() => !alive(grandchild) && !alive(ex.pid), 'children gone');
    assert.ok(alive(outsider.pid!), '다른 프로세스는 종료하지 않음');
    const info = await waitFor(async () => { const i = await runInfo(env.ex.task('task-a').runId); return i?.result ? i : null; }, 'run result');
    assert.equal(info.result.outcome, 'cancelled');
    assert.equal((await cancel(env.ex, 'task-a')).ok, false, '종료된 실행은 다시 중단하지 않음');
  } finally { outsider.kill('SIGKILL'); env.cleanup(); }
});

test('서버 재시작: 살아 있는 프로세스·종료된 프로세스·결과 불명을 자동 완료/재실행하지 않음', async () => {
  let env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_a/'], mockScenario: 'hang' }));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'], mockScenario: 'slow-success' }));
    await assign(env.ex, task(env, 'task-c', { allowedFiles: ['src_c/'], mockScenario: 'hang' }));
    await startTask('task-a'); await startTask('task-b'); await startTask('task-c');
    await waitFor(() => invocations(env) === 3, 'three invocations');
    const exC = env.ex.state.executions[env.ex.task('task-c').lastExecId!];
    // 서버 다운
    env = env.restart();
    process.kill(-exC.pgid, 'SIGKILL'); // 서버가 없는 동안 감독자가 기록 없이 사라짐
    await waitFor(() => !groupAlive(env.ex, exC.pgid), 'c dead');
    env = env.restart();
    assert.equal(status(env, 'task-a'), 'orphan_running');
    assert.equal(status(env, 'task-c'), 'unknown');
    await waitFor(() => status(env, 'task-b') === 'exit_observed', 'b exit observed', 20_000);
    assert.equal(env.ex.task('task-b').result ?? null, null, '재시작 후 종료는 자동으로 결과 반영하지 않음');
    assert.equal((await runInfo(env.ex.task('task-b').runId))?.suspendedStep, 'await-exit');
    assert.ok(discrepancy(env.ex.task('task-c'), await runInfo(env.ex.task('task-c').runId))?.includes('결과 불명'));
    // 중복 호출 방지
    assert.equal((await launch(env.ex, 'task-a', 'x')).ok, false);
    assert.equal((await launch(env.ex, 'task-c', 'x')).ok, false);
    assert.equal(invocations(env), 3, '재시작 후 자동 재실행 없음');
    // 사용자 조작
    await applyObservedExit(env.ex, 'task-b');
    await waitFor(() => status(env, 'task-b') === 'review_pending', 'b review');
    acknowledgeUnknown(env.ex, 'task-c');
    assert.equal(status(env, 'task-c'), 'abandoned');
    assert.equal(env.ex.locks.holder('task:task-c'), null);
    assert.ok((await cancel(env.ex, 'task-a')).ok, '재시작 전 이 실행기가 만든 프로세스는 spec 경로로 소유 확인 후 중단 가능');
    await waitFor(() => status(env, 'task-a') === 'exit_observed', 'a exit observed');
  } finally { env.cleanup(); }
});

test('승인 후 SHA·기준 브랜치가 바뀌면 통합 거절, 재검토 후 통합', async () => {
  const env = setup();
  try {
    const repo = env.fixture.repo;
    const mainBefore = gitOut(repo, 'rev-parse', 'HEAD');
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_a/'] }));
    const t = await toReview(env, 'task-a');
    await assert.rejects(approve(env.ex, 'task-a', t.result!.headSha!), /작업 테스트가 통과하지 않음\(미실행\)/, '미실행은 통과가 아님');
    await verify(env, 'task-a');
    await assert.rejects(approve(env.ex, 'task-a', 'a'.repeat(40)), /현재 결과와 다름|현재 SHA/);
    await approveAndWait(env, 'task-a');
    assert.equal(status(env, 'task-a'), 'approved');
    assert.equal((await runInfo(t.runId))?.suspendedStep, 'integrate-gate');
    // 승인 후 작업 브랜치에 커밋 추가
    const wt = env.fixture.worktrees['task-a'].path;
    fs.appendFileSync(path.join(wt, 'src_a', 'file.txt'), 'late change\n');
    gitOut(wt, 'commit', '-qam', 'late');
    await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'integration_refused');
    assert.match(env.ex.task("task-a").statusReason ?? "", /승인 무효화: 작업 브랜치 SHA 변경/);
    assert.equal(gitOut(repo, 'rev-parse', 'HEAD'), mainBefore, '거절 시 기준 브랜치 불변');
    assert.equal(env.ex.task('task-a').approval, null);

    // 재검토 → 새 SHA 승인 → 기준 브랜치 이동 → 다시 거절
    await startReview('task-a');
    assert.equal(status(env, 'task-a'), 'review_pending');
    await approveAndWait(env, 'task-a');
    fs.writeFileSync(path.join(repo, 'shared', 'file.txt'), 'main moved\n');
    gitOut(repo, 'commit', '-qam', 'main moved');
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.match(env.ex.task("task-a").statusReason ?? "", /기준 브랜치 이동/);

    // 다시 검토 → 통합 성공
    await startReview('task-a');
    const sha = (await approveAndWait(env, 'task-a')).sha;
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'integrated', env.ex.task('task-a').statusReason ?? '');
    assert.match(gitOut(repo, 'log', '-1', '--format=%B'), new RegExp(`cherry picked from commit [0-9a-f]{40}`));
    assert.equal(gitOut(repo, 'log', '-1', '--format=%B').includes(sha), true, '-x로 승인 SHA 기록');
    assert.equal(gitOut(repo, 'status', '--porcelain'), '');
  } finally { env.cleanup(); }
});

test('통합 충돌은 자동 해결하지 않고 abort, ./develop 잠금 사용 중이면 승인 유지 후 대기', async () => {
  const env = setup();
  try {
    const repo = env.fixture.repo;
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['shared/file.txt'] }));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['shared/file.txt'] }));
    await toReview(env, 'task-a');
    await approveAndWait(env, 'task-a');
    // ./develop 잠금을 다른 작업이 쥐고 있는 동안
    const holder = spawn(path.join(repo, 'develop'), ['--', 'sleep', '3'], { cwd: repo, stdio: 'ignore' });
    await new Promise((r) => setTimeout(r, 700));
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'approved', '잠금 사용 중이면 승인 유지');
    assert.match(env.ex.task("task-a").statusReason ?? "", /사용 중/);
    assert.equal((await runInfo(env.ex.task('task-a').runId))?.suspendedStep, 'integrate-gate');
    await new Promise((r) => holder.on('exit', r));
    await resumeStep(env.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-a'), 'integrated');
    const mainAfterA = gitOut(repo, 'rev-parse', 'HEAD');

    // 같은 파일을 옛 기준 SHA에서 다르게 바꾼 task-b → cherry-pick 충돌
    await toReview(env, 'task-b');
    await approveAndWait(env, 'task-b');
    await resumeStep(env.ex.task('task-b').runId!, 'integrate-gate', { action: 'integrate' });
    assert.equal(status(env, 'task-b'), 'integration_conflict', env.ex.task('task-b').statusReason ?? '');
    assert.deepEqual(env.ex.task('task-b').integration?.conflictFiles, ['shared/file.txt']);
    assert.equal(gitOut(repo, 'rev-parse', 'HEAD'), mainAfterA, '충돌 시 기준 브랜치 불변');
    assert.equal(gitOut(repo, 'status', '--porcelain'), '', 'abort 후 checkout 깨끗함');
    assert.equal(fs.existsSync(path.join(repo, '.git', 'CHERRY_PICK_HEAD')), false);
  } finally { env.cleanup(); }
});

test('실패·범위 밖 변경·결과 불명을 명확히 표시', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_a/'], mockScenario: 'fail' }));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'], mockScenario: 'touch-forbidden' }));
    await toReview(env, 'task-a');
    assert.equal(status(env, 'task-a'), 'failed');
    const ex = env.ex.state.executions[env.ex.task('task-a').lastExecId!];
    assert.equal(ex.exitCode, 3);
    const info = await waitFor(async () => { const i = await runInfo(env.ex.task('task-a').runId); return i?.result ? i : null; }, 'run result');
    assert.equal(info.result.outcome, 'failed');
    await toReview(env, 'task-b');
    const r = env.ex.task('task-b').result!;
    assert.equal(r.checksPassed, false);
    assert.deepEqual(r.outOfScope, ['outside-scope.txt']);
    await assert.rejects(approve(env.ex, 'task-b', r.headSha!), /검사 실패/);
  } finally { env.cleanup(); }
});

test('계약 검증: 금지 경로·브랜치 접두어·실험 작업·미등록/기본 checkout 차단', async () => {
  const env = setup();
  try {
    await assert.rejects(assign(env.ex, task(env, 'task-a', { allowedFiles: ['data/labels.jsonl'] })), /금지 경로/);
    await assert.rejects(assign(env.ex, task(env, 'task-a', { branch: 'codex/task-a' })), /접두어/);
    await assert.rejects(assign(env.ex, task(env, 'task-a', { requiresExperiment: true })), /기본 checkout 단일 실행 담당자/);
    await assert.rejects(assign(env.ex, task(env, 'task-a', { allowedFiles: ['src_*/'] })), /glob/);
    const mainBefore = gitOut(env.fixture.repo, 'rev-parse', 'HEAD');
    await assert.rejects(assign(env.ex, task(env, 'task-a', { taskId: 'task-x', worktree: env.fixture.repo })), /계약을 커밋할 수 없음: 기본 checkout 분리/);
    assert.equal(gitOut(env.fixture.repo, 'rev-parse', 'HEAD'), mainBefore, 'main에는 계약을 커밋하지 않음');
    assert.equal(env.ex.state.tasks['task-x'], undefined);
    assert.equal(invocations(env), 0);
  } finally { env.cleanup(); }
});

test('모델·worker 경로 작업은 worktree의 ./develop 잠금 안에서 실행', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { allowedFiles: ['card_condition/new_worker.py'], mockScenario: 'hang' }));
    const wt0 = env.fixture.worktrees['task-a'].path;
    // worktree는 만들어졌지만 ./develop이 쓸 자체 .venv가 없으면 실행 준비가 아님
    assert.equal(env.ex.task('task-a').envReadiness?.ready, false);
    await assert.rejects(startTask('task-a'), /환경: 자체 \.venv\(없음\)/);
    assert.equal(invocations(env), 0);
    assert.ok(env.ex.task('task-a').envReadiness!.fixes.some((f) => f.includes('python3 -m venv .venv')), '해결 명령 안내');
    assert.equal(fs.existsSync(path.join(wt0, '.venv')), false, '가상환경을 자동으로 만들지 않음');
    makeVenv(wt0); // 사용자가 직접 준비
    assert.equal((await recheckEnv(env.ex, 'task-a'))?.ready, true);
    await startTask('task-a');
    const ex = env.ex.state.executions[env.ex.task('task-a').lastExecId!];
    assert.deepEqual(ex.display.slice(0, 2), ['./develop', '--']);
    const wt = env.fixture.worktrees['task-a'].path;
    await waitFor(() => /pid=/.test(logTail(env.ex, ex.execId).text), 'started');
    let code = 0;
    try { execFileSync(path.join(wt, 'develop'), ['--check'], { cwd: wt, stdio: 'pipe' }); } catch (e: any) { code = e.status; }
    assert.equal(code, 1, '실행 중에는 같은 worktree의 ./develop 잠금이 사용 중');
    await cancel(env.ex, 'task-a');
    await waitFor(() => status(env, 'task-a') === 'cancelled', 'cancelled');
  } finally { env.cleanup(); }
});

test('무료 가드: 과금 신호 로그·API 키 환경변수 → 실행 중단·알림 파일·이후 시작 차단', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { mockScenario: 'paid-message' }));
    await startTask('task-a');
    await waitFor(() => env.trips.length > 0, 'trip');
    assert.match(env.trips[0].detail, /credit balance/i);
    await waitFor(() => ['cancelled'].includes(status(env, 'task-a')), 'cancelled by guard');
    assert.ok(fs.existsSync(env.ex.guard.alertFile));
    await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'] }));
    const r = await launch(env.ex, 'task-b', 'x');
    assert.equal(r.ok, false);
    assert.match((r as any).reason, /무료 가드/);

    env.ex.guard.checkEnv({ OPENAI_API_KEY: 'sk-test-not-real' } as any);
    assert.match(env.trips.at(-1)!.detail, /OPENAI_API_KEY/);
    assert.doesNotMatch(JSON.stringify(env.trips), /sk-test-not-real/, '키 값은 기록하지 않음');
    const child = sanitizedChildEnv({ PATH: '/bin', ANTHROPIC_API_KEY: 'x', OPENAI_API_KEY: 'y', SECRET_THING: 'z' } as any);
    for (const k of PAID_ENV_KEYS) assert.equal(child[k], undefined);
    assert.equal(child.SECRET_THING, undefined, '허용 목록 밖 환경변수는 자식에게 전달하지 않음');
  } finally { env.cleanup(); }
});

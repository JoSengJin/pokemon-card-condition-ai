import { approve } from '../src/executor/taskApproval.ts';
import { recheckEnv } from '../src/executor/taskEnvironment.ts';
import { recollect } from '../src/executor/taskCollect.ts';
import { finishManual } from '../src/executor/taskManual.ts';
import { startPrompt } from '../src/executor/executorPrompt.ts';
// 수동 모드(에이전트 세션에서 작업)와 시작 프롬프트. 에이전트 세션은 테스트가 worktree에 직접 커밋해 흉내낸다.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { runInfo, startTask } from '../src/runtime.ts';
import { invocations, setup, task, verify, waitFor, type Env } from './helpers.ts';
// @ts-ignore plain JS helper
import { makeVenv } from '../scripts/fixture-lib.mjs';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=session', '-c', 'user.email=s@l', ...a], { cwd }).toString().trim();
const status = (env: Env, id: string) => env.ex.task(id).status;
const sessionCommit = (env: Env, name: string, file: string, text = 'session change\n') => {
  const wt = env.fixture.worktrees[name].path;
  fs.mkdirSync(path.dirname(path.join(wt, file)), { recursive: true });
  fs.appendFileSync(path.join(wt, file), text);
  gitOut(wt, 'add', '--', file); gitOut(wt, 'commit', '-qm', `feat: ${file}`);
  return gitOut(wt, 'rev-parse', 'HEAD');
};
const manual = (env: Env, name: string, extra: Record<string, unknown> = {}) => env.ex.assign(task(env, name, { mode: 'manual', ...extra }));

test('수동 모드 전체 흐름: 프로세스 없이 소유권 유지 → 작업 완료 → Git 검사 → 작업 테스트 → 승인 대기', async () => {
  const env = setup();
  try {
    await manual(env, 'task-a');
    await startTask('task-a');
    assert.equal(status(env, 'task-a'), 'manual_working');
    assert.equal(invocations(env), 0, '도구가 에이전트 프로세스를 띄우지 않음');
    assert.equal(Object.keys(env.ex.state.executions).length, 0);
    assert.equal((await runInfo(env.ex.task('task-a').runId))?.suspendedStep, 'await-exit');
    assert.ok(env.ex.locks.holder('task:task-a'), '소유권 잠금 유지');
    // 같은 파일을 쓰는 다른 작업은 시작할 수 없음
    await env.ex.assign(task(env, 'task-b', { allowedFiles: ['src_a/file.txt'] }));
    await assert.rejects(startTask('task-b'), /충돌: task-a\(files/);
    await assert.rejects(startTask('task-a'), /중복 실행 차단|잠금 사용 중/);

    // 사용자가 에이전트 세션에서 작업(커밋)한 뒤 "작업 완료"
    const sha = sessionCommit(env, 'task-a', 'src_a/session.txt');
    await finishManual(env.ex, 'task-a');
    await waitFor(() => status(env, 'task-a') === 'review_pending', 'review');
    const t = env.ex.task('task-a');
    assert.equal(env.ex.locks.holder('task:task-a'), null, '완료 후 잠금 해제');
    assert.equal(t.result!.headSha, sha);
    assert.ok(t.result!.checksPassed, JSON.stringify(t.result!.checks));
    assert.deepEqual(t.result!.changedFiles, ['src_a/session.txt']);
    assert.equal(t.result!.checks.find((c) => c.name === '종료코드'), undefined, '프로세스가 없으므로 종료코드 검사 없음');
    assert.equal((await verify(env, 'task-a')).status, 'passed');
    assert.equal((await runInfo(t.runId))?.suspendedStep, 'review-gate');
  } finally { env.cleanup(); }
});

test('수동 모드: 허용 밖 변경·미커밋 변경은 Git 검사 실패, 다시 수집하면 새 SHA 기준으로 판단하고 이전 테스트 결과는 쓰이지 않음', async () => {
  const env = setup();
  try {
    await manual(env, 'task-a');
    await startTask('task-a');
    sessionCommit(env, 'task-a', 'outside.txt');
    fs.writeFileSync(path.join(env.fixture.worktrees['task-a'].path, 'src_a', 'wip.txt'), '미커밋');
    await finishManual(env.ex, 'task-a');
    await waitFor(() => status(env, 'task-a') === 'review_pending', 'review');
    let r = env.ex.task('task-a').result!;
    assert.equal(r.checksPassed, false);
    assert.deepEqual(r.outOfScope, ['outside.txt'], '허용 범위 안의 미커밋 파일은 범위 밖이 아니라 미커밋 검사에서 실패');
    assert.equal(r.checks.find((c) => c.name === '미커밋 변경 없음')!.ok, false);
    assert.equal(r.checks.find((c) => c.name === '허용 파일 범위')!.ok, false);
    await assert.rejects(approve(env.ex, 'task-a', r.headSha!), /Git 계약 검사 실패/);

    // 정리하고 허용 범위 안 커밋만 남긴 뒤 다시 수집
    const wt = env.fixture.worktrees['task-a'].path;
    fs.rmSync(path.join(wt, 'src_a', 'wip.txt'));
    gitOut(wt, 'reset', '-q', '--hard', env.ex.task('task-a').contractSha);
    const sha2 = sessionCommit(env, 'task-a', 'src_a/ok.txt');
    await recollect(env.ex, 'task-a');
    r = env.ex.task('task-a').result!;
    assert.ok(r.checksPassed, JSON.stringify(r.checks));
    assert.equal(r.headSha, sha2);
    await verify(env, 'task-a');
    // 커밋을 더 하면 이전 작업 테스트로 승인할 수 없음
    const sha3 = sessionCommit(env, 'task-a', 'src_a/more.txt');
    await recollect(env.ex, 'task-a');
    assert.equal(env.ex.task('task-a').result!.headSha, sha3);
    await assert.rejects(approve(env.ex, 'task-a', sha3), /작업 테스트가 통과하지 않음|현재 SHA·계약과 다름/);
  } finally { env.cleanup(); }
});

test('수동 모드: 취소는 잠금을 풀고 workflow를 끝냄, 서버 재시작 후에도 자동 완료·재실행 없음', async () => {
  let env = setup();
  try {
    await manual(env, 'task-a');
    await manual(env, 'task-b', { allowedFiles: ['src_b/'] });
    await startTask('task-a'); await startTask('task-b');
    env = env.restart();
    assert.equal(status(env, 'task-a'), 'manual_working', '재시작해도 수동 작업 상태 유지');
    assert.ok(env.ex.locks.holder('task:task-a'));
    assert.equal(invocations(env), 0);
    await assert.rejects(startTask('task-a'), /중복 실행 차단|잠금 사용 중/);
    assert.equal((await runInfo(env.ex.task('task-a').runId))?.suspendedStep, 'await-exit', '재시작 후에도 Mastra 대기 상태 유지');

    const r = await env.ex.cancel('task-a');
    assert.ok(r.ok, r.reason);
    assert.equal(status(env, 'task-a'), 'cancelled');
    assert.equal(env.ex.locks.holder('task:task-a'), null);
    const info = await waitFor(async () => { const i = await runInfo(env.ex.task('task-a').runId); return i?.result ? i : null; }, 'run result');
    assert.equal(info.result.outcome, 'cancelled');
    assert.equal(env.ex.task('task-a').result ?? null, null, '취소는 결과를 수집하지 않음');
    await startTask('task-a'); // 취소 후 다시 시작 가능
    assert.equal(status(env, 'task-a'), 'manual_working');
    // 완료를 두 번 누르거나 작업 중이 아닐 때는 거절
    await assert.rejects(finishManual(env.ex, 'task-c' as any), /task 없음/);
    await finishManual(env.ex, 'task-b');
    await waitFor(() => status(env, 'task-b') === 'review_pending', 'b review');
    await assert.rejects(finishManual(env.ex, 'task-b'), /수동 작업 중이 아님/);
  } finally { env.cleanup(); }
});

test('수동 모드: ./develop 경로 작업은 실행 준비(.venv) 전에는 시작하지 않음', async () => {
  const env = setup();
  try {
    await manual(env, 'task-a', { allowedFiles: ['card_condition/new_worker.py'] });
    await assert.rejects(startTask('task-a'), /환경: 자체 \.venv\(없음\)/);
    makeVenv(env.fixture.worktrees['task-a'].path);
    await recheckEnv(env.ex, 'task-a');
    await startTask('task-a');
    assert.equal(status(env, 'task-a'), 'manual_working');
  } finally { env.cleanup(); }
});

test('시작 프롬프트: 작업 위치·브랜치·시작 HEAD·읽을 문서·허용 파일·검사·금지·인계 형식, 계약에는 경로를 남기지 않음', async () => {
  const env = setup();
  try {
    const t = await manual(env, 'task-a', { doneCriteria: ['src_a 결과 파일 추가'], goal: '시작 프롬프트 확인', prompt: '상세 지시 본문' });
    const wt = env.fixture.worktrees['task-a'].path;
    const p = await startPrompt(env.ex, 'task-a', { unattended: true, extraDocs: ['README.md'] });
    assert.equal(p.head, gitOut(wt, 'rev-parse', 'HEAD'));
    assert.ok(p.text.startsWith(`작업 위치:\n${t.worktree}\n`));
    for (const needle of [`브랜치: ${t.branch}`, `시작 HEAD: ${p.head}`, `기준 SHA: ${t.baseSha}`, 'AGENTS.md와 PAIR_CODING.md', t.contractPath, '및 README.md',
      '목표:\n시작 프롬프트 확인', '- src_a 결과 파일 추가', '허용 파일 1개만 변경하세요:', '- src_a/', '검사 (에이전트 종료 후', 'git diff --check',
      '사용자는 자리에 없습니다. 사람 정답을 추정하거나 재요청하지 마세요.', '금지:', 'push', 'main 통합과 push는 Codex가 담당', '상세 지시는 계약 파일']) {
      assert.ok(p.text.includes(needle), `없음: ${needle}`);
    }
    assert.ok(!p.text.includes('./develop'), 'develop 경로 작업이 아니면 안내하지 않음');
    assert.ok(!(await startPrompt(env.ex, 'task-a')).text.includes('자리에 없습니다'), '무인 문구는 옵션');
    assert.ok(!fs.readFileSync(path.join(wt, t.contractPath), 'utf8').includes(wt), '계약 파일에는 로컬 경로 없음');
    await assert.rejects(startPrompt(env.ex, 'task-a', { extraDocs: ['nope/missing.md'] }), /시작 HEAD에 없는 문서/);
    await assert.rejects(startPrompt(env.ex, 'task-a', { extraDocs: ['../etc/passwd'] }), /올바르지 않음/);
    await assert.rejects(startPrompt(env.ex, 'task-a', { extraDocs: ['/etc/passwd'] }), /올바르지 않음/);
    const dev = await manual(env, 'task-b', { allowedFiles: ['card_condition/x.py'] });
    assert.ok((await startPrompt(env.ex, dev.taskId)).text.includes('`./develop -- <수정 명령>`'));
  } finally { env.cleanup(); }
});

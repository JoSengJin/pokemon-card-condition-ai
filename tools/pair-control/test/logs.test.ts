// 실시간 로그: 줄 단위 비밀 가림·즉시 기록·시간 제한, 통합 후 검사 실행 중 로그, 수동 모드 활동. 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { resumeStep, startTask } from '../src/runtime.ts';
import { lineWriter, runLogged, tailFile } from '../src/executor/logstream.ts';
import { activityOf, tailPostLog } from '../src/executor/taskControl.ts';
import { fakeSecret, setup, task, verify, waitFor } from './helpers.ts';

const redact = (s: string) => s.replace(/sk-[A-Za-z0-9_-]{16,}/g, '[REDACTED]');
const tmpLog = () => path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'pair-log-')), 'x.log');
const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd }).toString().trim();

test('줄 단위 가림: 비밀이 청크 경계에 걸려도 새지 않고, 끝나지 않은 줄은 end에서 기록', () => {
  const log = tmpLog(), w = lineWriter(log, redact), secret = fakeSecret('chunk');
  fs.writeFileSync(log, ''); // runLogged가 먼저 만드는 빈 파일
  w.push('토큰 ' + secret.slice(0, 9));
  assert.equal(fs.readFileSync(log, 'utf8'), '', '완성되지 않은 줄은 아직 쓰지 않음');
  w.push(secret.slice(9) + ' 끝\n다음 줄 ' + secret);
  assert.equal(fs.readFileSync(log, 'utf8'), '토큰 [REDACTED] 끝\n');
  w.end();
  const all = fs.readFileSync(log, 'utf8');
  assert.equal(all, '토큰 [REDACTED] 끝\n다음 줄 [REDACTED]');
  assert.ok(!all.includes(secret.slice(3)));
  const bytes = Buffer.from(all);
  assert.deepEqual(tailFile(log, 5), { text: bytes.subarray(5).toString(), next: bytes.length }, '이어 읽기(바이트 위치)');
  assert.deepEqual(tailFile(path.join(os.tmpdir(), 'no-such-log'), 7), { text: '', next: 7 }, '파일이 없으면 빈 결과');
});

test('실행하면서 즉시 기록, 시간 제한이면 종료, 실행 실패도 로그에 남김', async () => {
  const log = tmpLog();
  const done = runLogged(process.execPath, ['-e', 'console.log("first");setTimeout(()=>console.log("second"),900)'], os.tmpdir(), 10_000, process.env, log, redact);
  await waitFor(() => tailFile(log).text.includes('first'), '첫 줄이 먼저 기록');
  assert.ok(!tailFile(log).text.includes('second'), '프로세스가 끝나기 전에 첫 줄이 보임');
  const r = await done;
  assert.equal(r.code, 0);
  assert.equal(tailFile(log).text, 'first\nsecond\n');

  const t = await runLogged(process.execPath, ['-e', 'console.log("stuck");setInterval(()=>{},1000)'], os.tmpdir(), 500, process.env, tmpLog(), redact);
  assert.equal(t.timedOut, true);
  const missing = tmpLog();
  const bad = await runLogged('/no/such/command', [], os.tmpdir(), 5_000, process.env, missing, redact);
  assert.equal(bad.code, 127);
  assert.match(tailFile(missing).text, /실행 실패/);
});

test('통합 후 검사: 실행 중에 로그가 먼저 보이고, 끝나면 완성·상태 반영, 비밀은 가려짐', async () => {
  const env = setup();
  try {
    const secret = fakeSecret('post');
    const code = `console.log("post-start");console.log("key ${secret}");setTimeout(()=>{console.log("post-end")},1500)`;
    await env.ex.assign(task(env, 'task-a', { postChecks: [{ id: 'slow', name: '느린 검사', executable: 'node', args: ['-e', code] }] }));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    await verify(env, 'task-a');
    const t = env.ex.task('task-a');
    const a = await env.ex.approve('task-a', t.result!.headSha!);
    await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    const integrating = resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });

    const live = await waitFor(() => { try { const r = tailPostLog(env.ex, 'task-a', 'slow', 0); return r.text.includes('post-start') ? r : null; } catch { return null; } }, '실행 중 로그');
    assert.equal(env.ex.task('task-a').status, 'integrating', '아직 통합 후 검사가 도는 중');
    assert.equal(env.ex.task('task-a').integration!.postStatus, 'running');
    assert.equal(env.ex.task('task-a').integration!.postChecks![0].status, 'running');
    assert.ok(!live.text.includes('post-end'));
    assert.ok(live.text.includes('[REDACTED]') && !live.text.includes(secret), '비밀은 가려져 기록');

    await integrating;
    const done = env.ex.task('task-a');
    assert.equal(done.status, 'integrated');
    assert.equal(done.integration!.postStatus, 'passed');
    assert.equal(done.integration!.postChecks![0].status, 'passed');
    const full = tailPostLog(env.ex, 'task-a', 'slow', 0);
    assert.match(full.text, /post-start[\s\S]*post-end/);
    assert.equal(tailPostLog(env.ex, 'task-a', 'slow', full.next).text, '', '더 이을 내용 없음');
    assert.throws(() => tailPostLog(env.ex, 'task-a', 'nope', 0), /통합 후 검사 로그 없음/);
  } finally { env.cleanup(); }
});

test('활동: 새 커밋·변경 파일·미커밋·범위 밖 변경을 읽기만 해서 보여 줌', async () => {
  const env = setup();
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'manual' }));
    const wt = env.ex.task('task-a').worktree;
    const empty = await activityOf(env.ex, 'task-a');
    assert.equal(empty.commits.length, 0, '계약 커밋 위의 작업은 아직 없음');
    assert.deepEqual(empty.dirty, []);

    fs.mkdirSync(path.join(wt, 'src_a'), { recursive: true });
    fs.writeFileSync(path.join(wt, 'src_a', 'new.txt'), 'x');
    fs.writeFileSync(path.join(wt, 'outside.txt'), 'y');
    gitOut(wt, 'add', 'src_a/new.txt');
    gitOut(wt, 'commit', '-m', 'feat: 새 파일');
    const a = await activityOf(env.ex, 'task-a');
    assert.equal(a.commits.length, 1);
    assert.equal(a.commits[0].subject, 'feat: 새 파일');
    assert.deepEqual(a.changed.filter((f) => f.startsWith('src_a')), ['src_a/new.txt']);
    assert.deepEqual(a.dirty, ['outside.txt'], '미커밋 파일');
    assert.deepEqual(a.outOfScope, ['outside.txt'], '허용 범위 밖');
    assert.equal(gitOut(wt, 'status', '--porcelain'), '?? outside.txt', '읽기만 함(상태 변화 없음)');
  } finally { env.cleanup(); }
});

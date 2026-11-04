import { finishManual } from '../src/executor/taskManual.ts';
import { handoffToMain, handoffToMainAuto } from '../src/executor/handoffCreate.ts';
import { confirmHandoff } from '../src/executor/handoffRecords.ts';
// Codex 과금 가드(설정·로그인 방식)와 메인 인계 자동 확인. 가짜 codex만 쓰며 모델 요청·네트워크는 없다.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { probe, realReadiness } from '../src/executor/adapters.ts';
import { codexLoginIsChatgpt, scanCodexConfig } from '../src/executor/nocharge.ts';
import { startTask } from '../src/runtime.ts';
import { fakeCli, setup, task, verify, waitFor, type Env } from './helpers.ts';

const real = { allowRealModelCalls: true, confirmedSubscriptionAuth: true, cli: fakeCli };

function codexHome(toml: string) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-home-'));
  fs.writeFileSync(path.join(dir, 'config.toml'), toml);
  return { env: { CODEX_HOME: dir } as NodeJS.ProcessEnv, dir };
}

test('Codex 설정 가드: API 로그인 강제·다른 공급자·기본 엔드포인트 변경은 막고, 표 아래 키와 설정 없음은 통과', () => {
  assert.deepEqual(scanCodexConfig({ env: { CODEX_HOME: '/nonexistent-codex-home' } }), []);
  const ok = codexHome('model = "gpt-5"\nforced_login_method = "chatgpt" # 구독만\n[model_providers.x]\nenv_key = "X_KEY"\nforced_login_method = "api"\n');
  assert.deepEqual(scanCodexConfig({ env: ok.env }), []);
  const api = codexHome('forced_login_method = "api"\n');
  assert.equal(scanCodexConfig({ env: api.env })[0].code, 'settings_login_method');
  const prov = codexHome('model_provider = "azure"\nopenai_base_url = "https://x.example"\n');
  assert.deepEqual(scanCodexConfig({ env: prov.env }).map((r) => r.code), ['settings_api_key', 'settings_api_key']);
  for (const h of [ok, api, prov]) fs.rmSync(h.dir, { recursive: true, force: true });
});

test('codex login status: ChatGPT 로그인만 통과, API 키·로그아웃·출력 없음은 차단', async () => {
  assert.ok(codexLoginIsChatgpt('Logged in using ChatGPT'));
  assert.ok(!codexLoginIsChatgpt('Logged in using an API key'));
  assert.ok(!codexLoginIsChatgpt('Not logged in'));
  assert.ok(!codexLoginIsChatgpt(undefined));
  const env = setup(real);
  try {
    const ok = await probe('codex', env.cfg);
    assert.equal(ok.loginStatus, 'Logged in using ChatGPT');
    assert.ok(!realReadiness('codex', ok, env.cfg).blockers.some((b) => b.code === 'login_not_chatgpt'));
    process.env.FAKE_CODEX_LOGIN = 'Logged in using an API key';
    const api = await probe('codex', env.cfg);
    const rr = realReadiness('codex', api, env.cfg);
    assert.ok(rr.blockers.some((b) => b.code === 'login_not_chatgpt') && !rr.available);
  } finally { delete process.env.FAKE_CODEX_LOGIN; env.cleanup(); }
});

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=session', '-c', 'user.email=s@l', ...a], { cwd }).toString().trim();
async function readyForHandoff(env: Env, name: string) {
  await env.ex.assign(task(env, name, { mode: 'manual' }));
  await startTask(name);
  const wt = env.fixture.worktrees[name].path;
  fs.mkdirSync(path.join(wt, 'src_a'), { recursive: true });
  fs.appendFileSync(path.join(wt, 'src_a/work.txt'), 'change\n');
  gitOut(wt, 'add', '--', 'src_a/work.txt'); gitOut(wt, 'commit', '-qm', 'feat: work');
  await finishManual(env.ex, name);
  await waitFor(() => env.ex.task(name).status === 'review_pending', `${name} review`);
  await verify(env, name);
}

test('인계 자동 확인: 가드를 통과하면 별도 codex 리뷰가 approve일 때만 자동 확인으로 기록(승인은 그대로 사람)', async () => {
  const env = setup(real);
  try {
    await readyForHandoff(env, 'task-a');
    const r = await handoffToMainAuto(env.ex, 'task-a');
    assert.match(r.autoNote!, /자동 확인 시작/);
    await waitFor(() => !!env.ex.task('task-a').handoff?.confirmedAt, '자동 확인');
    const h = env.ex.task('task-a').handoff!;
    assert.equal(h.auto, true);
    assert.match(h.note!, /대화 중인 메인 세션의 확인이 아님/);
    assert.equal(env.ex.task('task-a').approval, null, '승인은 대신하지 않음');
    assert.equal(env.ex.task('task-a').status, 'review_pending');
  } finally { env.cleanup(); }
});

test('인계 자동 확인: changes_requested면 확인하지 않고 사람 차례로 남김', async () => {
  const env = setup(real);
  const flag = path.join(path.dirname(fakeCli.codex), '.fake-verdict');
  fs.writeFileSync(flag, 'changes_requested');
  try {
    await readyForHandoff(env, 'task-a');
    await handoffToMainAuto(env.ex, 'task-a');
    await waitFor(() => env.ex.task('task-a').review?.status === 'done', '리뷰 종료');
    assert.equal(env.ex.task('task-a').review!.verdict, 'changes_requested');
    assert.equal(env.ex.task('task-a').handoff!.confirmedAt, undefined);
  } finally { fs.rmSync(flag, { force: true }); env.cleanup(); }
});

test('인계 자동 확인: 과금 가드가 막으면 인계만 하고 사유를 알리며 모델을 실행하지 않음', async () => {
  const env = setup(); // 실제 모델 호출 차단 기본값
  try {
    await readyForHandoff(env, 'task-a');
    const r = await handoffToMainAuto(env.ex, 'task-a');
    assert.match(r.autoNote!, /^자동 확인 안 함: .*실제 모델 호출 차단/);
    assert.ok(env.ex.task('task-a').handoff && !env.ex.task('task-a').handoff!.confirmedAt);
    assert.equal(env.ex.task('task-a').review, null);
  } finally { env.cleanup(); }
});

test('자동 확인이 approve가 아니면 인계는 확인되지 않고 결과가 남으며, 화면 승인은 메인 확인 전에는 거부된다', async () => {
  const env = setup(real);
  const flag = path.join(path.dirname(fakeCli.codex), '.fake-verdict');
  fs.writeFileSync(flag, 'insufficient_evidence');
  try {
    await readyForHandoff(env, 'task-a');
    const sha = env.ex.task('task-a').result!.headSha!;
    await assert.rejects(env.ex.approve('task-a', sha, { requireHandoff: true }), /메인 인계가 끝나지 않음/);
    await handoffToMainAuto(env.ex, 'task-a');
    await waitFor(() => env.ex.task('task-a').review?.status === 'done', '리뷰 종료');
    const h = env.ex.task('task-a').handoff!;
    assert.equal(h.confirmedAt, undefined, 'approve가 아니면 자동 확인하지 않음');
    assert.equal(h.autoResult!.verdict, 'insufficient_evidence');
    assert.match(h.autoResult!.summary!, /fake codex review/);
    await assert.rejects(env.ex.approve('task-a', sha, { requireHandoff: true }), /메인 확인이 끝나지 않음/);
    confirmHandoff(env.ex, 'task-a', '사람이 결과를 보고 확인');
    const a = await env.ex.approve('task-a', sha, { requireHandoff: true });
    assert.equal(a.sha, sha);
    assert.ok(a.mainConfirmedAt, '확인 완료 기록이 승인에 남음');
  } finally { fs.rmSync(flag, { force: true }); env.cleanup(); }
});

test('승인 전제조건: 리뷰가 실행 중이면 승인할 수 없다', async () => {
  const env = setup(real);
  try {
    await readyForHandoff(env, 'task-a');
    const t = env.ex.task('task-a'), sha = t.result!.headSha!;
    await handoffToMain(env.ex, 'task-a');
    confirmHandoff(env.ex, 'task-a');
    t.review = { reviewId: 'r', reviewer: 'codex', mode: 'real', sha, contractHash: t.contractHash, bundleDir: '', worktreeFingerprint: '', status: 'running', startedAt: 'x' };
    await assert.rejects(env.ex.approve('task-a', sha, { requireHandoff: true }), /리뷰가 실행 중/);
  } finally { env.cleanup(); }
});

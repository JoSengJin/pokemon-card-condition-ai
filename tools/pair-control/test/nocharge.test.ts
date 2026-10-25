// 실제 CLI 경로의 무과금 조건. 가짜 claude/codex 실행 파일만 사용하며 모델 요청·설치·로그인은 없다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { realPlan, realReadiness, probe, CLAUDE_ALLOWED_TOOLS } from '../src/executor/adapters.ts';
import { scanArgs, scanClaudeSettings } from '../src/executor/nocharge.ts';
import { startTask } from '../src/runtime.ts';
import { fakeCli, fakeSecret, setup, task, waitFor, type Env } from './helpers.ts';

const real = { allowRealModelCalls: true, confirmedSubscriptionAuth: true, cli: fakeCli };
const codes = (r: { blockers: { code: string }[] }) => r.blockers.map((b) => b.code);
const writeSettings = (env: Env, dir: string, json: unknown) => {
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'settings.json'), typeof json === 'string' ? json : JSON.stringify(json));
};
const withEnv = async (k: string, v: string, fn: () => Promise<void>) => {
  const prev = process.env[k]; process.env[k] = v;
  try { await fn(); } finally { if (prev === undefined) delete process.env[k]; else process.env[k] = prev; }
};

test('차단 원인과 해결 조건: 기본값은 호출 차단·구독 미확인, 둘 다 켜야 실제 모드 가능', async () => {
  const env = setup({ cli: fakeCli });
  try {
    await env.ex.refreshProbes();
    const r0 = realReadiness('claude', env.ex.probes.claude, env.cfg);
    assert.deepEqual(codes(r0), ['real_calls_disabled', 'subscription_unconfirmed']);
    assert.ok(r0.blockers.every((b) => b.fix.length > 5));
    const ok = realReadiness('claude', env.ex.probes.claude, { ...env.cfg, ...real });
    assert.equal(ok.available, true);
    const none = realReadiness('codex', await probe('codex', { ...env.cfg, cli: { codex: '/nonexistent/codex' } }), env.cfg);
    assert.ok(codes(none).includes('cli_error') || codes(none).includes('cli_missing'));
  } finally { env.cleanup(); }
});

test('Claude 설정: apiKeyHelper·env의 API 키 이름·claudeai 아닌 로그인 방식·읽을 수 없는 파일은 차단, 값은 기록하지 않음', async () => {
  const env = setup(real);
  try {
    const userDir = path.join(env.cfg.homeDir!, '.claude');
    assert.deepEqual(scanClaudeSettings({ home: env.cfg.homeDir }), [], '설정 없음 → 통과');
    writeSettings(env, userDir, { forceLoginMethod: 'claudeai', theme: 'dark' });
    assert.deepEqual(scanClaudeSettings({ home: env.cfg.homeDir }), [], '구독 로그인 강제는 통과');

    writeSettings(env, userDir, { apiKeyHelper: `/bin/echo ${fakeSecret('helper')}` });
    let risks = scanClaudeSettings({ home: env.cfg.homeDir });
    assert.deepEqual(risks.map((r) => r.code), ['settings_api_key']);
    assert.match(risks[0].message, /~\/\.claude\/settings\.json/, '홈 경로는 ~로 줄여 표시');

    writeSettings(env, userDir, { env: { ANTHROPIC_API_KEY: fakeSecret('envval'), FOO: 'bar' } });
    risks = scanClaudeSettings({ home: env.cfg.homeDir });
    assert.deepEqual(risks.map((r) => r.code), ['settings_api_key']);
    assert.match(risks[0].message, /ANTHROPIC_API_KEY/);

    writeSettings(env, userDir, { forceLoginMethod: 'console' });
    assert.deepEqual(scanClaudeSettings({ home: env.cfg.homeDir }).map((r) => r.code), ['settings_login_method']);

    writeSettings(env, userDir, '{ not json');
    assert.deepEqual(scanClaudeSettings({ home: env.cfg.homeDir }).map((r) => r.code), ['settings_unreadable']);

    writeSettings(env, userDir, { apiKeyHelper: 'x', env: { OPENAI_API_KEY: fakeSecret('zzzz') } });
    await env.ex.refreshProbes();
    const rr = realReadiness('claude', env.ex.probes.claude, env.cfg);
    assert.ok(!rr.available);
    for (const tag of ['helper', 'envval', 'zzzz']) assert.ok(!JSON.stringify(rr).includes(fakeSecret(tag)), `설정의 값(${tag})은 어디에도 나오지 않음`);
    assert.match(JSON.stringify(rr), /OPENAI_API_KEY/, '키 이름은 알려 줌');
    const codexRr = realReadiness('codex', env.ex.probes.codex, env.cfg);
    assert.ok(!codes(codexRr).includes('settings_api_key'), 'Claude 설정은 Codex에 적용하지 않음');
  } finally { env.cleanup(); }
});

test('API 키 환경변수가 있으면 실제 실행 시작 거부, 프로젝트 설정(.claude)의 키도 거부, 자식에게 전달하지 않음', async () => {
  const env = setup(real);
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'real', goal: 'ok' }));
    const antKey = fakeSecret('ant');
    await withEnv('ANTHROPIC_API_KEY', antKey, async () => {
      await assert.rejects(startTask('task-a'), /무과금: paid_env/);
      assert.ok(!(env.ex.task('task-a').statusReason ?? '').includes(antKey), '환경변수 값은 사유에 나오지 않음');
      assert.match(env.ex.task('task-a').statusReason ?? '', /ANTHROPIC_API_KEY/);
      await env.ex.refreshProbes();
      assert.ok(codes(realReadiness('claude', env.ex.probes.claude, env.cfg)).includes('paid_env'));
    });
    // 프로젝트 설정
    writeSettings(env, path.join(env.fixture.worktrees['task-a'].path, '.claude'), { apiKeyHelper: 'helper.sh' });
    await assert.rejects(startTask('task-a'), /무과금: settings_api_key/);
    fs.rmSync(path.join(env.fixture.worktrees['task-a'].path, '.claude'), { recursive: true });
    // 해결하면 시작 가능, 자식 프로세스는 키 없이 실행
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    const ex = env.ex.state.executions[env.ex.task('task-a').lastExecId!];
    const log = env.ex.logTail(ex.execId).text;
    assert.match(log, /ANTHROPIC_API_KEY: absent OPENAI_API_KEY: absent/);
  } finally { env.cleanup(); }
});

test('가짜 claude로 실제 어댑터 경로: 문서 옵션만 사용, --bare 없음, 허용 도구 제한, 계약 경로만 전달', async () => {
  const env = setup(real);
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'real', goal: '실제 경로 확인', prompt: '긴 지시 '.repeat(800) }));
    await startTask('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    const t = env.ex.task('task-a');
    const ex = env.ex.state.executions[t.lastExecId!];
    const log = env.ex.logTail(ex.execId).text;
    assert.match(log, /args: --print --permission-mode acceptEdits --allowedTools /);
    assert.ok(!/--bare|--max-budget-usd|--betas/.test(log));
    assert.ok(log.includes(CLAUDE_ALLOWED_TOOLS[0]) && log.includes('Bash(git commit *)'));
    assert.doesNotMatch(log, /Bash\(\*\)|Bash,/, '일반 Bash는 허용하지 않음');
    assert.ok(ex.display.join(' ').length < 400, '긴 지시는 CLI 인자가 아니라 계약 파일');
    assert.ok(t.result!.checksPassed, JSON.stringify(t.result!.checks));
    assert.equal(ex.mode, 'real');
    assert.equal(ex.tokens, '미측정');
  } finally { env.cleanup(); }
});

test('금지 옵션 검사와 계획 거절 조건', async () => {
  assert.deepEqual(scanArgs(['--print', '--permission-mode', 'acceptEdits']), []);
  assert.deepEqual(scanArgs(['--bare', '-p', 'x']).map((r) => r.code), ['forbidden_flag']);
  assert.equal(scanArgs(['--max-budget-usd=5', '--betas', 'x'])[0].code, 'forbidden_flag');
  const env = setup({ ...real });
  try {
    await env.ex.refreshProbes();
    const t = await env.ex.assign(task(env, 'task-a', { mode: 'real' }));
    const plan = realPlan(t, env.ex.probes.claude!, env.cfg);
    assert.ok(!('refused' in plan));
    assert.deepEqual(scanArgs((plan as any).args), []);
    assert.ok('refused' in realPlan(t, env.ex.probes.claude!, { ...env.cfg, confirmedSubscriptionAuth: false }));
    assert.ok('refused' in realPlan(t, env.ex.probes.claude!, { ...env.cfg, allowRealModelCalls: false }));
    assert.ok('refused' in realPlan(t, { ...env.ex.probes.claude!, missingFlags: ['--allowedTools'] }, env.cfg));
  } finally { env.cleanup(); }
});

test('한도 도달은 정지: 서비스는 유지, 실제 실행 시작 거부, mock은 계속, 해제는 사용자 확인으로만', async () => {
  let env = setup(real);
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'real', goal: '[fake:limit] 한도 흉내' }));
    await env.ex.assign(task(env, 'task-b', { mode: 'real', allowedFiles: ['src_b/'], goal: 'ok' }));
    await env.ex.assign(task(env, 'task-c', { allowedFiles: ['src_c/'], mode: 'mock' }));
    await startTask('task-a');
    await waitFor(() => env.ex.limit !== null, 'limit');
    assert.match(env.ex.limit!.detail, /한도 도달/);
    assert.equal(env.trips.length, 0, '"extra usage" 권유 문구가 섞여도 서비스를 끄지 않음');
    await waitFor(() => env.ex.task('task-a').status === 'failed', 'failed');
    await assert.rejects(startTask('task-b'), /구독 한도/);
    await env.ex.refreshProbes();
    assert.ok(codes(realReadiness('claude', env.ex.probes.claude, env.cfg, { limit: env.ex.limit })).includes('limit_hit'));
    await startTask('task-c'); // mock은 한도와 무관
    await waitFor(() => env.ex.task('task-c').status === 'review_pending', 'mock review');
    env = env.restart();
    assert.ok(env.ex.limit, '한도 상태는 재시작 후에도 유지');
    env.ex.clearLimit();
    await startTask('task-b');
    await waitFor(() => env.ex.task('task-b').status === 'review_pending', 'b review');
    assert.throws(() => env.ex.clearLimit(), /한도 도달 상태가 아님/);
  } finally { env.cleanup(); }
});

test('확실한 과금 문구(credit balance)는 한도 문구와 달리 서비스 종료 신호', async () => {
  const env = setup(real);
  try {
    await env.ex.assign(task(env, 'task-a', { mode: 'real', goal: '[fake:paid] 과금 흉내' }));
    await startTask('task-a');
    await waitFor(() => env.trips.length > 0, 'trip');
    assert.match(env.trips[0].detail, /credit balance/i);
    assert.equal(env.ex.limit, null);
  } finally { env.cleanup(); }
});

test('가짜 codex로 실제 어댑터 경로: exec --cd --sandbox, API 키 미전달, 한도 정지', async () => {
  const env = setup(real);
  try {
    await env.ex.assign(task(env, 'task-b', { mode: 'real', allowedFiles: ['src_b/'], goal: '코덱스 경로' }));
    await withEnv('OPENAI_API_KEY', fakeSecret('openai'), async () => {
      await assert.rejects(startTask('task-b'), /무과금: paid_env/);
    });
    await startTask('task-b');
    await waitFor(() => env.ex.task('task-b').status === 'review_pending', 'review');
    const ex = env.ex.state.executions[env.ex.task('task-b').lastExecId!];
    const log = env.ex.logTail(ex.execId).text;
    assert.match(log, /args: exec --cd .* --sandbox workspace-write/);
    assert.match(log, /OPENAI_API_KEY: absent CODEX_API_KEY: absent/);
    assert.ok(env.ex.task('task-b').result!.checksPassed);
    await env.ex.assign(task(env, 'task-d', { mode: 'real', allowedFiles: ['src_c/'], goal: '[fake:limit] x' }));
    await startTask('task-d');
    await waitFor(() => env.ex.limit !== null, 'codex limit');
  } finally { env.cleanup(); }
});

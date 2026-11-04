import { assign } from '../src/executor/taskAssign.ts';
// 스트리밍(JSONL) 출력과 무과금 가드. 모델 요청 없음(mock 에이전트·샘플 이벤트만).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { realPlan, type Probe } from '../src/executor/adapters.ts';
import { FreeGuard } from '../src/executor/freeGuard.ts';
import { eventSignal, scanOutput } from '../src/executor/streamGuard.ts';
import { startTask } from '../src/runtime.ts';
import { setup, task, waitFor, type Env } from './helpers.ts';

function guard() {
  const trips: any[] = [], limits: any[] = [];
  const g = new FreeGuard(fs.mkdtempSync(path.join(os.tmpdir(), 'pair-guard-')), (a) => trips.push(a), (a) => limits.push(a));
  return { g, trips, limits };
}
const line = (o: unknown) => JSON.stringify(o);

test('이벤트 신호: API 키 인증·결제 오류·오류 결과·한도만 신호, 내용 이벤트는 신호 아님', () => {
  assert.equal(eventSignal({ type: 'system', subtype: 'init', apiKeySource: 'none' }), null);
  assert.equal(eventSignal({ type: 'system', subtype: 'init', apiKeySource: 'oauth' }), null, '알 수 없는 값은 종료하지 않음');
  for (const src of ['user', 'project', 'org', 'temporary']) assert.match((eventSignal({ type: 'system', subtype: 'init', apiKeySource: src }) as any).trip, new RegExp(`apiKeySource=${src}`));
  assert.ok((eventSignal({ type: 'assistant', error: 'billing_error' }) as any).trip);
  assert.match((eventSignal({ type: 'assistant', error: 'rate_limit' }) as any).scan, /limit reached/);
  assert.match((eventSignal({ type: 'result', is_error: true, result: 'Credit balance is too low' }) as any).scan, /Credit balance/);
  assert.equal(eventSignal({ type: 'result', is_error: false, result: 'credit balance 와 billing 이 문서에 나옴' }), null);
  assert.equal(eventSignal({ type: 'user', message: { content: [{ type: 'tool_result', content: 'credit balance billing payment required' }] } }), null);
  assert.equal(eventSignal({ type: 'item.completed', item: { type: 'command_execution', aggregated_output: 'credit balance' } }), null);
  assert.match((eventSignal({ type: 'turn.failed', error: { message: 'usage limit reached' } }) as any).scan, /usage limit reached/);
  assert.match((eventSignal({ type: 'error', message: 'Your credit balance is too low' }) as any).scan, /credit balance/);
});

test('스캔: 내용 이벤트가 과금 문구를 담아도 종료하지 않고, 진짜 신호와 일반 글은 그대로 처리', () => {
  const { g, trips, limits } = guard();
  scanOutput(g, [
    line({ type: 'system', subtype: 'init', apiKeySource: 'none' }),
    line({ type: 'assistant', message: { content: [{ type: 'text', text: 'billing 과 credit balance 를 읽는 중' }] } }),
    line({ type: 'user', message: { content: [{ type: 'tool_result', content: 'const x = /credit balance/i; // extra usage' }] } }),
    line({ type: 'result', is_error: false, result: 'billing 문서' }),
    '[mock] 일반 로그 한 줄',
  ].join('\n'), 'exec:t');
  assert.equal(trips.length + limits.length, 0, '오탐 없음');

  scanOutput(g, line({ type: 'system', subtype: 'init', apiKeySource: 'user' }), 'exec:t');
  assert.equal(trips.length, 1);
  assert.equal(trips[0].reason, 'paid_stream');
  assert.match(trips[0].detail, /apiKeySource=user/);
  assert.equal(g.pending()!.reason, 'paid_stream', '알림 파일이 남아 재시작 거부');

  const b = guard();
  scanOutput(b.g, 'Your credit balance is too low to continue.', 'exec:t');
  assert.equal(b.trips.length, 1, '텍스트 줄은 지금처럼 글 전체 검사');
  const l = guard();
  scanOutput(l.g, line({ type: 'result', is_error: true, result: 'Claude usage limit reached|1700000000' }), 'exec:t');
  assert.equal(l.limits.length, 1, '한도는 정지(서비스는 유지)');
  assert.equal(l.trips.length, 0);
  const bad = guard();
  scanOutput(bad.g, '{ "type": 이게 깨진 JSON 인데 credit balance', 'exec:t');
  assert.equal(bad.trips.length, 1, 'JSON이 아니면 일반 글로 검사');
});

test('읽는 중간에 잘린 JSON 줄은 다음 주기에 이어 읽어 조각이 일반 글로 검사되지 않음', () => {
  const env = setup();
  try {
    const log = path.join(env.dir, 'cut.log');
    const ex: any = env.ex;
    const rec: any = { execId: 'cut-1', logPath: log };
    const head = '{"type":"user","message":{"content":[{"type":"tool_result","content":"credit bal';
    fs.writeFileSync(log, line({ type: 'system', subtype: 'init', apiKeySource: 'none' }) + '\n' + head);
    ex.readNewLog(rec);
    assert.equal(env.trips.length, 0, '잘린 조각은 검사하지 않고 보류');
    fs.appendFileSync(log, 'ance is too low"}]}}\n');
    ex.readNewLog(rec);
    assert.equal(env.trips.length, 0, '이어 읽으면 내용 이벤트라 신호 아님');
    fs.writeFileSync(log, 'Your credit balance is too low to continue.');
    ex.logOffsets.set('cut-1', 0);
    ex.readNewLog(rec);
    assert.equal(env.trips.length, 1, '줄바꿈 없는 일반 텍스트는 바로 검사(기존 동작)');
  } finally { env.cleanup(); }
});

async function runStream(env: Env, scenario: string) {
  await assign(env.ex, task(env, 'task-a', { mockScenario: scenario }));
  await startTask('task-a');
}

test('mock 스트림 실행: 이벤트 줄이 로그에 남고 과금 문구를 담은 내용 이벤트에도 종료하지 않음', async () => {
  for (const scenario of ['stream', 'stream-quote']) {
    const env = setup();
    try {
      await runStream(env, scenario);
      await waitFor(() => env.ex.task('task-a').status === 'review_pending', `${scenario} review`);
      const t = env.ex.task('task-a');
      const log = fs.readFileSync(env.ex.state.executions[t.lastExecId!].logPath, 'utf8');
      assert.match(log, /"type":"system","subtype":"init"/);
      assert.ok(log.split('\n').filter((l) => l.startsWith('{')).every((l) => JSON.parse(l).type), '이벤트 줄은 모두 JSON');
      assert.equal(env.trips.length, 0, `${scenario}: 오탐 없음`);
      assert.equal(t.result!.checksPassed, true);
    } finally { env.cleanup(); }
  }
});

test('mock: API 키 인증 이벤트·결제 오류 이벤트는 서비스 종료 신호와 알림 파일을 남김', async () => {
  for (const [scenario, detail] of [['stream-api-key', /apiKeySource=user/], ['stream-error-event', /결제·크레딧 오류/]] as const) {
    const env = setup();
    try {
      await runStream(env, scenario);
      await waitFor(() => env.trips.length > 0, `${scenario} trip`);
      assert.equal(env.trips[0].reason, 'paid_stream');
      assert.match(env.trips[0].detail, detail);
      assert.equal(env.ex.guard.pending()!.reason, 'paid_stream');
    } finally { env.cleanup(); }
  }
});

test('실제 CLI 계획: 옵션이 확인되고 설정이 켜져 있을 때만 줄 단위 출력 옵션을 붙이고, 금지 옵션 검사는 그대로', () => {
  const env = setup();
  try {
    const cfg = { ...env.cfg, allowRealModelCalls: true, confirmedSubscriptionAuth: true };
    const mk = (agent: 'claude' | 'codex', stream: boolean): Probe => ({ agent, installed: true, binary: `/x/${agent}`, version: '1', verifiedFlags: [], missingFlags: [], note: '', checkedAt: '', stream });
    const t = (agent: 'claude' | 'codex') => ({ ...task(env, 'task-a'), agent }) as any;
    const on = (agent: 'claude' | 'codex', cfgX = cfg, st = true) => realPlan(t(agent), mk(agent, st), cfgX as any) as any;
    assert.ok(on('claude').args.includes('--output-format=stream-json') && on('claude').args.includes('--verbose'));
    assert.ok(on('codex').args.includes('--json') && on('codex').args[0] === 'exec');
    for (const off of [on('claude', { ...cfg, streamOutput: false }), on('claude', cfg, false), on('codex', { ...cfg, streamOutput: false }), on('codex', cfg, false)]) {
      assert.ok(!off.args.includes('--json') && !off.args.includes('--verbose') && !off.args.some((a: string) => a.startsWith('--output-format')), '옵션이 없으면 텍스트 모드');
    }
    assert.ok(on('claude').display.includes('--output-format=stream-json') && on('claude').display.at(-1) === '<prompt>');
    assert.equal(on('claude', { ...cfg, allowRealModelCalls: false }).refused !== undefined, true, '실제 호출 승인이 없으면 여전히 거부');
  } finally { env.cleanup(); }
});

import { getTask, limitOf } from '../src/executor/executorLookup.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { finishManual } from '../src/executor/taskManual.ts';
// 교대 후 연속 페어코딩: 새 메인이 인수 뒤 도착하는 구현 결과를 받아 검사→검토→통합→합성 원격 push까지 이어 처리하는지 확인한다.
// 가짜 CLI·합성 bare 원격만 쓰며 실제 Codex/Claude 호출·실제 push는 없다(합성 계약/회귀 검사이지 실제 CLI 검증이 아니다).
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { clearAgentLimit, handoverMain } from '../src/executor/mainHandover.ts';
import { handoverAfterLimit } from '../src/executor/mainLimit.ts';
import { pipelineTick } from '../src/executor/pipelineTick.ts';
import { pipe, register } from '../src/executor/pipelineState.ts';
import { pipelineView } from '../src/executor/pipelineView.ts';
import { startTask } from '../src/runtime.ts';
import { applyActions, fakeCli, setup, task, waitFor, type Env } from './helpers.ts';

const real = { allowRealModelCalls: true, confirmedSubscriptionAuth: true, cli: fakeCli };
const dir = path.dirname(fakeCli.codex);
const flag = path.join(dir, '.fake-takeover'), turnLog = path.join(dir, '.fake-turn-log');
const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd, stdio: 'pipe' }).toString().trim();
const script = (turn: Record<string, unknown> = {}, actions: unknown[] = []) => fs.writeFileSync(flag, JSON.stringify({ actions, turn }));
const turns = () => (fs.existsSync(turnLog) ? fs.readFileSync(turnLog, 'utf8').trim().split('\n').filter(Boolean).map((l) => JSON.parse(l)) : []);
const clean = () => { fs.rmSync(flag, { force: true }); fs.rmSync(turnLog, { force: true }); };
const originHead = (env: Env) => git(env.fixture.origin, 'rev-parse', 'refs/heads/main');
const ALL = ['assign_task', 'confirm_handoff', 'approve_task', 'integrate_task', 'push_main'];
const grant = (env: Env, actions = ALL, extra: Record<string, unknown> = {}) => grantApproval(env.ex, { basis: '합성 승인: 개발·통합·일반 push 범위(테스트)', actions, targets: '*', ...extra });
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const T = 90_000;

async function withEnv(fn: (env: Env) => Promise<void>, over = {}) {
  clean();
  const env = setup({ ...real, ...over });
  try { await fn(env); } catch (e) {
    if (process.env.PIPE_DEBUG) { // 실패 원인 진단용(상태·이벤트·턴·감사 기록 끝부분)
      const rt = env.ex.runtime, ev = path.join(env.cfg.stateDir, 'events.jsonl');
      console.error(JSON.stringify({ main: env.ex.mainAgent, gen: rt.generation, session: rt.session && [rt.session.agent, rt.session.status], failures: rt.failures, limited: rt.limited, events: Object.values(pipe(env.ex).events).map((x) => [x.key.slice(0, 24), x.state, x.reason]), turns: Object.values(pipe(env.ex).turns).map((t) => [t.agent, t.generation, t.status, t.failure]), tasks: Object.values(env.ex.state.tasks).map((t) => [t.taskId, t.status, t.statusReason]) }, null, 1));
      console.error(fs.existsSync(ev) ? fs.readFileSync(ev, 'utf8').trim().split('\n').slice(-25).join('\n') : '');
    }
    throw e;
  } finally { clean(); env.cleanup(); }
}

/** 교대가 끝날 때까지(성공이면 completed/idle) 기다린다. */
const taken = (env: Env) => waitFor(() => { const s = env.ex.runtime.session; return s && ['completed', 'idle'].includes(s.status) ? s : null; }, '인수 완료');
const as = (env: Env, agent: 'codex' | 'claude') => { env.ex.state.main = { agent, since: 'x', generation: 0 }; env.ex.runtime.generation = 0; };

/** 수동 모드 작업이 커밋 하나로 끝나 검토 대기가 되게 한다(사용자가 에이전트 세션에서 작업을 마친 것을 흉내). */
async function manualResult(env: Env, name: string, dirName: string, extra: Record<string, unknown> = {}, content = 'change\n') {
  await assign(env.ex, task(env, name, { mode: 'manual', allowedFiles: [`${dirName}/`], ...extra }));
  await startTask(name);
  const wt = env.fixture.worktrees[name].path;
  fs.appendFileSync(path.join(wt, dirName, 'work.txt'), content);
  git(wt, 'add', '--', `${dirName}/work.txt`); git(wt, 'commit', '-qm', `feat: ${name}`);
  await finishManual(env.ex, name);
  await waitFor(() => getTask(env.ex, name).status === 'review_pending', `${name} review`);
}

const pushedFor = (env: Env, id: string) => Object.values(env.ex.state.pushes ?? {}).find((p) => p.status === 'pushed_verified' && p.tasks.includes(id));
/** 사용자 개입 없이 합성 원격까지 push됐는지 기다리고 근거를 확인한다. */
async function expectPushed(env: Env, id: string) {
  const rec = await waitFor(() => pushedFor(env, id), `${id} push`, T);
  assert.equal(originHead(env), git(env.fixture.repo, 'rev-parse', 'HEAD'), '합성 원격 = 통합 checkout HEAD');
  assert.equal(originHead(env), rec.pushedSha);
  assert.ok(!rec.command.some((a) => /force|^\+|-f$/.test(a)), 'force 없음');
  assert.equal(getTask(env.ex, id).status, 'integrated');
  assert.equal(getTask(env.ex, id).integration?.postStatus === 'failed', false);
  return rec;
}

// ---------- 1~3. 정상 연속 흐름 ----------
for (const [from, to, name, dirName] of [['codex', 'claude', 'task-d', 'src_b'], ['claude', 'codex', 'task-c', 'src_c']] as const) {
  test(`${from}→${to} 교대 후 도착한 구현 결과를 새 메인이 검사·검토·통합·합성 원격 push까지 처리한다(재승인·복사 없음)`, { timeout: 180_000 }, async () => withEnv(async (env) => {
    as(env, from);
    // 구현 에이전트(${name})는 교대 시점에 실행 중이며 중단되지 않는다.
    await assign(env.ex, task(env, name, { mode: 'mock', mockScenario: 'slow-success', allowedFiles: [`${dirName}/`] }));
    await startTask(name);
    await waitFor(() => getTask(env.ex, name).status === 'running', 'running');
    grant(env);
    script();
    await handoverMain(env.ex, to);
    const s = await taken(env);
    assert.equal(env.ex.mainAgent, to);
    assert.ok(['running', 'collecting', 'review_pending'].includes(getTask(env.ex, name).status), '교대 때 구현을 중단하지 않음');

    await expectPushed(env, name); // 이후 단계는 이 테스트가 호출하지 않는다: 검사·인계·확인·승인·통합·push 모두 파이프라인이 수행
    const ag = Object.values(env.ex.state.executions).find((e) => e.taskId === name && (e.kind ?? 'agent') === 'agent')!;
    assert.equal(ag.cancelRequested, false);
    const ts = Object.values(pipe(env.ex).turns);
    assert.equal(ts.length, 2, 'result_ready 턴 1회 + integrated 턴 1회');
    assert.ok(ts.every((t) => t.status === 'applied' && t.agent === to && t.sessionId === s.id && t.generation === 1));
    assert.deepEqual(ts.flatMap((t) => t.actionResults.map((r) => [r.type, r.ok])), [['confirm_handoff', true], ['approve_task', true], ['integrate_task', true], ['push_main', true]]);
    assert.equal(turns().length, 2, '모델 턴은 이벤트당 정확히 한 번');
    assert.ok(Object.values(pipe(env.ex).events).every((e) => e.state === 'applied'));
    assert.match(getTask(env.ex, name).handoff!.note ?? '', /합성 검토/);

    // 입력 묶음: 이전 기억 없음 명시, 승인된 행동 종류, 변경 파일·diff 파일 제공, diff 해시 원문은 주지 않음
    const t1 = ts[0], bundle = path.join(env.cfg.stateDir, 'main-sessions', t1.id);
    const req = fs.readFileSync(path.join(bundle, 'TURN_REQUEST.md'), 'utf8'), ev = fs.readFileSync(path.join(bundle, 'EVENTS.json'), 'utf8');
    assert.match(req, /이전 대화 기억은 없습니다/); assert.match(req, /push_main/);
    const diffText = fs.readFileSync(path.join(bundle, 'diffs', `${name}.diff`), 'utf8');
    assert.ok(diffText.includes('work') || diffText.includes('fake'));
    assert.ok(!/[0-9a-f]{64}/.test(ev), 'EVENTS.json에 diff 해시를 미리 주지 않음');

    const v = pipelineView(env.ex);
    assert.equal(v.takeoverDone, true);
    assert.equal(v.tasks.find((x) => x.taskId === name)!.pipelineDone, true, 'push 검증된 작업만 파이프라인 완료');
    await sleep(1500);
    assert.equal(turns().length, 2, '완료 뒤 추가 모델 호출(폴링) 없음');
    assert.equal(Object.values(env.ex.state.pushes ?? {}).length, 1, 'push는 한 번');
  }));
}

test('새 작업 준비→구현 시작→결과 수집→검사·검토→통합→통합 후 검사→합성 원격 push: 교대 직후 배정 행동 하나로 시작된다', { timeout: 180_000 }, async () => withEnv(async (env) => {
  grant(env);
  script({}, [{ id: 'as1', type: 'assign_task', taskId: 'task-n', input: { agent: 'codex', mode: 'mock', mockScenario: 'success', goal: '합성 연속 작업', allowedFiles: ['src_b/work.txt'], env: 'none',
    checks: [{ id: 'ws', name: '공백 오류 검사', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'] }],
    postChecks: [{ id: 'post', name: '통합 후 HEAD 확인', executable: 'git', args: ['rev-parse', '--verify', 'HEAD'], cwd: '.' }] } }]);
  const base = originHead(env);
  await handoverMain(env.ex, 'claude');
  const s = await taken(env);
  assert.equal(s.actionResults[0].ok, true, s.actionResults[0].detail);
  assert.notEqual(getTask(env.ex, 'task-n').status, 'assigned', '배정만 하고 멈추지 않고 구현을 시작');
  await expectPushed(env, 'task-n');
  assert.notEqual(originHead(env), base);
  assert.equal(getTask(env.ex, 'task-n').integration?.postStatus, 'passed', '통합 후 검사 통과 뒤에만 push');
}));

// ---------- 4. 차단 ----------
test('승인 범위 밖 작업은 자동 검사·인계·턴 모두 하지 않고 보류한다. 범위가 덮이면 풀린다', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-d', 'src_a'); await manualResult(env, 'task-b', 'src_b'); // 둘 다 codex 구현 → 메인 claude는 독립
  grantApproval(env.ex, { basis: 'task-b만 승인', actions: ALL.filter((a) => a !== 'push_main'), targets: ['task-b'] });
  grantApproval(env.ex, { basis: '브랜치 main 일반 push 승인', actions: ['push_main'], targets: ['main'] }); // push 대상은 작업이 아니라 브랜치
  script();
  await handoverMain(env.ex, 'claude'); await taken(env);
  await expectPushed(env, 'task-b');
  const a = getTask(env.ex, 'task-d');
  assert.equal(a.status, 'review_pending'); assert.equal(a.verification ?? null, null, '검사도 시작하지 않음'); assert.equal(a.handoff ?? null, null);
  const held = Object.values(pipe(env.ex).events).filter((e) => e.taskId === 'task-d');
  assert.ok(held.length === 0 || held.every((e) => e.state === 'held'));
  assert.equal(turns().length, 2, 'task-d는 모델 턴을 일으키지 않음(task-b의 턴 2회뿐)');
  // 승인을 새로 기록(사용자의 새 승인)하면 그때부터 task-d도 같은 경로로 진행된다
  grantApproval(env.ex, { basis: 'task-d 승인 추가', actions: ALL.filter((x) => x !== 'push_main'), targets: ['task-d'] });
  await expectPushed(env, 'task-d');
  assert.equal(turns().length, 4);
}));

test('특정 세션에 묶인 승인은 새 메인이 승계하지 않는다: 이름만 바꾼 권한 승계 없음(검사·턴 없음)', { timeout: 60_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-b', 'src_b');
  grantApproval(env.ex, { basis: '이전 메인 세션에만 묶인 승인', actions: ALL, targets: '*', boundSessionId: 'previous-main-session' });
  script();
  await handoverMain(env.ex, 'claude'); await taken(env);
  await sleep(2000);
  assert.equal(getTask(env.ex, 'task-b').verification ?? null, null); assert.equal(turns().length, 0);
  assert.equal(Object.keys(env.ex.state.pushes ?? {}).length, 0);
}));

test('자유 문장 조건뿐인 승인: 검사·인계·모델 턴을 모두 시작하지 않고 사람 판단을 기다린다(조건을 풀거나 지우지 않음)', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-b', 'src_b');
  grant(env, ['prepare_checks', 'confirm_handoff', 'approve_task', 'integrate_task', 'push_main'], { conditions: '사용자 구두 확인 필요' });
  script();
  await handoverMain(env.ex, 'claude'); await taken(env);
  await sleep(2500);
  assert.equal(turns().length, 0, '모델 턴 0회'); assert.equal(Object.keys(pipe(env.ex).steps).length, 0, '자동 검사·인계 0회');
  assert.equal(getTask(env.ex, 'task-b').verification ?? null, null); assert.equal(getTask(env.ex, 'task-b').handoff ?? null, null);
  assert.equal(getTask(env.ex, 'task-b').status, 'review_pending');
  assert.ok(pipelineView(env.ex).heldReasons.some((h) => /승인 조건 미확정/.test(h.reason)), '보류 사유가 화면 요약에 남음');
  assert.equal(originHead(env), env.fixture.baseSha); assert.equal(Object.keys(env.ex.state.pushes ?? {}).length, 0);
}));

test('작업 테스트 실패: 인계·턴 없이 해당 작업에서 멈추고 사용자 판단 필요로 남는다(통과로 취급하지 않음)', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-b', 'src_b', {}, 'trailing space   \n');
  grant(env);
  script();
  await handoverMain(env.ex, 'claude'); await taken(env);
  await waitFor(() => Object.values(pipe(env.ex).events).find((e) => e.kind === 'blocked'), '차단 이벤트', T);
  const a = getTask(env.ex, 'task-b');
  assert.equal(a.verification?.status, 'failed'); assert.equal(a.handoff ?? null, null);
  assert.match(Object.values(pipe(env.ex).events).find((e) => e.kind === 'blocked')!.reason!, /통과하지 않음\(failed\)/);
  await sleep(1200);
  assert.equal(turns().length, 0); assert.equal(getTask(env.ex, 'task-b').status, 'review_pending');
}));

test('통합 후 검사 실패: 통합 행동은 실패로 남고 push 단계로 넘어가지 않는다', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-b', 'src_b', { postChecks: [{ id: 'bad', name: '항상 실패', executable: 'git', args: ['rev-parse', '--verify', 'refs/heads/없는-브랜치'], cwd: '.' }] });
  grant(env);
  script();
  await handoverMain(env.ex, 'claude'); await taken(env);
  const t = await waitFor(() => Object.values(pipe(env.ex).turns).find((x) => x.status === 'applied'), '턴 적용', T);
  assert.equal(t.actionResults.find((r) => r.type === 'integrate_task')!.ok, false);
  assert.equal(getTask(env.ex, 'task-b').status, 'integrated_check_failed');
  await sleep(1500);
  assert.equal(turns().length, 1, 'push 턴이 생기지 않음'); assert.equal(originHead(env), env.fixture.baseSha);
  assert.ok(Object.values(pipe(env.ex).events).some((e) => e.kind === 'blocked' && e.state === 'held'));
}));

test('구현 에이전트=메인: selfReview를 명시한 승인이 없으면 확인이 거부되고, 명시하면 진행한다', { timeout: 180_000 }, async () => {
  await withEnv(async (env) => {
    as(env, 'codex');
    await manualResult(env, 'task-a', 'src_a'); // 구현 담당 claude = 새 메인
    grant(env); script({ forceConfirm: true });
    await handoverMain(env.ex, 'claude'); await taken(env);
    const t = await waitFor(() => Object.values(pipe(env.ex).turns).find((x) => x.status === 'applied'), '턴 적용', T);
    assert.match(t.actionResults[0].detail, /독립 확인이 아님.*selfReview/);
    assert.equal(getTask(env.ex, 'task-a').status, 'review_pending'); assert.equal(getTask(env.ex, 'task-a').handoff?.confirmedAt, undefined);
    assert.throws(() => grantApproval(env.ex, { basis: 'x', actions: ['confirm_handoff', 'approve_task'], requires: { selfReview: true } }), /confirm_handoff 단독/);
  });
  await withEnv(async (env) => {
    as(env, 'codex');
    await manualResult(env, 'task-a', 'src_a');
    grant(env, ['approve_task', 'integrate_task', 'push_main']);
    grantApproval(env.ex, { basis: '사용자가 자기 확인을 명시 허용(합성)', actions: ['confirm_handoff'], targets: '*', requires: { selfReview: true } });
    script({ forceConfirm: true });
    await handoverMain(env.ex, 'claude'); await taken(env);
    await expectPushed(env, 'task-a');
    assert.match(getTask(env.ex, 'task-a').handoff!.note!, /^\[자기 확인 — 독립 확인 아님\]/);
  });
});

test('push 승인이 장부에 없거나 diff 해시가 틀리면 해당 단계만 막힌다(원격 불변)', { timeout: 180_000 }, async () => {
  await withEnv(async (env) => {
    as(env, 'claude');
    await manualResult(env, 'task-a', 'src_a'); // claude 구현, 메인 codex → 독립
    grant(env, ['confirm_handoff', 'approve_task', 'integrate_task']); // push_main 없음
    script();
    await handoverMain(env.ex, 'codex'); await taken(env);
    const held = await waitFor(() => Object.values(pipe(env.ex).events).find((e) => e.kind === 'integrated' && e.state === 'held'), 'push 승인 없는 통합 이벤트 보류', T);
    assert.match(held.reason!, /승인 범위 밖: push_main/);
    assert.equal(turns().length, 1, 'push_main 승인이 없으면 push 턴을 시작하지 않음(결과 도착 턴 1회뿐)');
    assert.equal(originHead(env), env.fixture.baseSha); assert.equal(getTask(env.ex, 'task-a').status, 'integrated');
    assert.equal(pipelineView(env.ex).tasks[0].pipelineDone, false, '통합만으로 파이프라인 완료 표시 안 함');
  });
  await withEnv(async (env) => {
    as(env, 'claude');
    await manualResult(env, 'task-a', 'src_a');
    grant(env); script({ badDiffHash: true });
    await handoverMain(env.ex, 'codex'); await taken(env);
    const t = await waitFor(() => Object.values(pipe(env.ex).turns).find((x) => x.status === 'applied'), '턴 적용', T);
    assert.match(t.actionResults[0].detail, /diff 해시가 도구 계산값과 다름/);
    assert.equal(getTask(env.ex, 'task-a').status, 'review_pending'); assert.equal(originHead(env), env.fixture.baseSha);
  });
});

// ---------- 5. 지연·중복·재교대 ----------
test('실행 중 재교대: 이전 세대 턴의 늦은 응답은 상태를 바꾸지 못하고, 새 메인이 같은 이벤트를 한 번 다시 판단한다', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'claude');
  await manualResult(env, 'task-c', 'src_c'); // claude 구현
  grant(env); script({ delayMs: 3500 });
  await handoverMain(env.ex, 'codex'); await taken(env);
  await waitFor(() => turns().length === 1, '첫 턴 시작', T);
  const first = Object.values(pipe(env.ex).turns)[0];
  script({ forceConfirm: true }); // 새 세대의 턴은 즉시 응답
  const r = await handoverAfterLimit(env.ex, 'claude', [], '합성: 턴 진행 중 재교대');
  assert.equal(r.status, 'launching');
  await waitFor(() => pipe(env.ex).turns[first.id].status === 'stale', '늦은 응답 거부', T);
  assert.equal(getTask(env.ex, 'task-c').status, 'review_pending', '늦은 응답의 행동은 수행되지 않음');
  assert.equal(getTask(env.ex, 'task-c').handoff?.confirmedAt, undefined);
  const second = await waitFor(() => Object.values(pipe(env.ex).turns).find((t) => t.generation === 2 && t.status === 'applied'), '새 세대 턴', T);
  assert.match(second.actionResults[0].detail, /독립 확인이 아님/, '새 메인=구현 에이전트라 selfReview 없이는 막힘');
  assert.equal(turns().length, 2, '이벤트마다 세대당 턴 한 번');
}));

test('중복 이벤트·겹친 틱: 같은 이벤트는 한 번만 등록되고 겹쳐 호출돼도 턴은 한 번만 시작된다', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'codex');
  await manualResult(env, 'task-a', 'src_a');
  grant(env, ['confirm_handoff']); script({ mode: 'none', delayMs: 800 });
  await handoverMain(env.ex, 'claude'); await taken(env);
  const sha = getTask(env.ex, 'task-a').result!.headSha!;
  await waitFor(() => pipe(env.ex).events[`result_ready:task-a:${sha}`], '이벤트 등록', T);
  assert.equal(register(env.ex, 'result_ready', 'task-a', sha), false, '이미 등록된 이벤트(또는 같은 키)는 새로 만들지 않음');
  await Promise.all([pipelineTick(env.ex), pipelineTick(env.ex), pipelineTick(env.ex)]);
  await sleep(2500);
  assert.equal(turns().length, 1);
  assert.equal(Object.keys(pipe(env.ex).steps).filter((k) => k.startsWith('checks:')).length, 1, '검사는 SHA당 한 번');
}));

// ---------- 6. 한도 ----------
test('한쪽 한도: 턴이 한도로 끝나면 그 에이전트를 기록하고 상대 메인으로 기존 한도 교대를 연결해, 새 세대에서 이어 완료한다', { timeout: 180_000 }, async () => withEnv(async (env) => {
  as(env, 'claude');
  await manualResult(env, 'task-c', 'src_c'); // claude 구현 → 최종 메인 claude의 자기 확인을 명시 허용
  grant(env, ['approve_task', 'integrate_task', 'push_main']);
  grantApproval(env.ex, { basis: '사용자가 자기 확인을 명시 허용(합성)', actions: ['confirm_handoff'], targets: '*', requires: { selfReview: true } });
  script({ mode: 'limit' });
  await handoverMain(env.ex, 'codex'); await taken(env);
  await waitFor(() => turns().length === 1, '첫 턴', T);
  script({ forceConfirm: true }); // 다음 턴은 정상
  await waitFor(() => env.ex.runtime.generation === 2 && env.ex.mainAgent === 'claude', '한도 교대', T);
  assert.ok(env.ex.runtime.limited.codex, '한도에 닿은 에이전트가 기록됨');
  assert.equal(limitOf(env.ex), null, '메인이 낸 한도가 전체 한도로 번지지 않음');
  await expectPushed(env, 'task-c');
  const ts = Object.values(pipe(env.ex).turns);
  assert.equal(ts[0].status, 'limited');
  assert.ok(ts[0].limitHandledAt, '종료 관찰과 분리된 다음 틱이 한도 교대를 한 번만 시작한 기록');
  assert.ok(ts.slice(1).every((t) => t.generation === 2 && t.agent === 'claude'));
  assert.equal(turns().length, 3, '한도 턴 1 + 새 세대 턴 2(result_ready·integrated)');
}));

test('양쪽 한도: 의존 이벤트를 보류하고 복구 지점을 남기며 재시도하지 않는다. 한도가 풀렸음을 확인하면 한 번 이어간다', { timeout: 180_000 }, async () => withEnv(async (env) => {
  as(env, 'claude');
  await manualResult(env, 'task-c', 'src_c');
  grant(env);
  script();
  await handoverMain(env.ex, 'codex'); await taken(env);
  script({ mode: 'limit', delayMs: 300 });
  env.ex.runtime.limited.claude = { at: new Date().toISOString(), detail: '합성: claude 한도' };
  await waitFor(() => Object.values(pipe(env.ex).events).find((e) => e.state === 'held' && /^한도/.test(e.reason ?? '')), '보류', T);
  assert.equal(env.ex.mainAgent, 'codex'); assert.equal(env.ex.runtime.frozen, false);
  await waitFor(() => fs.readdirSync(path.join(env.cfg.stateDir, 'main-checkpoints')).some((f) => f.endsWith('both-limited.json')), '복구 지점 보존', T);
  await sleep(1500);
  assert.equal(turns().length, 1, '자동 재시도 없음');
  assert.equal(getTask(env.ex, 'task-c').status, 'review_pending');
  // 사용자가 두 에이전트의 한도가 풀렸음을 확인하면 보류가 풀리고 한 번 이어간다
  script();
  clearAgentLimit(env.ex, 'codex'); clearAgentLimit(env.ex, 'claude');
  await expectPushed(env, 'task-c');
}));

// ---------- 7. 결과 불명·재시작 ----------
test('서버 재시작: 진행 중이던 턴이 끝나 있으면 이어 받아 한 번만 적용하고, 프로세스가 사라졌으면 결과 불명으로 두고 재실행하지 않는다', { timeout: 180_000 }, async () => {
  await withEnv(async (env0) => {
    as(env0, 'claude');
    await manualResult(env0, 'task-c', 'src_c');
    grant(env0); script({ delayMs: 3000 });
    await handoverMain(env0.ex, 'codex'); await taken(env0);
    await waitFor(() => turns().length === 1, '턴 시작', T);
    const env = env0.restart(); // 자식 프로세스는 살아 있음
    try {
      await expectPushed(env, 'task-c');
      assert.equal(turns().length === 2 || turns().length === 1, true);
      assert.equal(Object.values(pipe(env.ex).turns).filter((t) => t.actionResults.some((r) => r.type === 'integrate_task')).length, 1, '통합은 한 번');
      assert.equal(Object.values(env.ex.state.pushes ?? {}).length, 1);
    } finally { env.cleanup(); }
  });
  await withEnv(async (env0) => {
    as(env0, 'claude');
    await manualResult(env0, 'task-c', 'src_c');
    grant(env0); script({ delayMs: 20_000 });
    await handoverMain(env0.ex, 'codex'); await taken(env0);
    await waitFor(() => turns().length === 1, '턴 시작', T);
    const turn = Object.values(pipe(env0.ex).turns)[0];
    try { process.kill(-env0.ex.state.executions[turn.execId!].pgid, 'SIGKILL'); } catch { /* gone */ }
    const env = env0.restart();
    try {
      await waitFor(() => pipe(env.ex).turns[turn.id].status === 'unknown', '결과 불명', T);
      assert.ok(Object.values(pipe(env.ex).events).every((e) => e.state === 'unknown'));
      await sleep(1500);
      assert.equal(turns().length, 1, '재실행 없음'); assert.equal(getTask(env.ex, 'task-c').status, 'review_pending');
      assert.equal(originHead(env), env.fixture.baseSha);
    } finally { env.cleanup(); }
  });
});

test('적용 중 중단·push 결과 불명: 재시작 뒤 결과 불명으로 보존하고, 결과 불명 push가 있으면 push 행동을 하지 않는다', { timeout: 120_000 }, async () => withEnv(async (env) => {
  as(env, 'claude');
  await manualResult(env, 'task-c', 'src_c');
  grant(env, ALL);
  script({ mode: 'none' });
  await handoverMain(env.ex, 'codex'); const s = await taken(env);
  await waitFor(() => Object.values(pipe(env.ex).turns).find((t) => t.status === 'applied'), '빈 턴 적용', T);
  // 1) 적용 중이던 턴(이전 서버 수명)
  const key = Object.keys(pipe(env.ex).events)[0];
  pipe(env.ex).turns.ghost = { id: 'ghost', sessionId: s.id, generation: 1, agent: 'codex', status: 'applying', eventKeys: [key], startedAt: new Date().toISOString(), lifetime: 'old-lifetime', tokenHash: '', checkpointFile: '', checkpointHash: '', actionResults: [] };
  await pipelineTick(env.ex);
  assert.equal(pipe(env.ex).turns.ghost.status, 'unknown'); assert.equal(pipe(env.ex).events[key].state, 'unknown');
  // 2) push 결과 불명
  env.ex.state.pushes = { p1: { id: 'p1', status: 'push_unverified', tasks: ['task-c'], at: new Date().toISOString(), preRemoteHead: 'a'.repeat(40), pushedSha: 'b'.repeat(40) } as never };
  const r = await applyActions(env.ex, env.ex.runtime.session!, [{ id: 'pm1', type: 'push_main', target: 'main', sha: 'b'.repeat(40) }]);
  assert.match(r[0].detail, /push 결과 불명.*원격 확인 전 재수행하지 않음/);
  assert.equal(originHead(env), env.fixture.baseSha);
}));

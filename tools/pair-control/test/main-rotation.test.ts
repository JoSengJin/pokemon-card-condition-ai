import { getTask, limitOf } from '../src/executor/executorLookup.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
import { finishManual } from '../src/executor/taskManual.ts';
import { handoffToMain } from '../src/executor/handoffCreate.ts';
import { confirmHandoff } from '../src/executor/handoffRecords.ts';
// 메인 역할 교대 실행: 새 메인 프로세스 실행·인수 확인·승인 범위 승계·세대 차단·한도 복구. 가짜 CLI만 쓰며 실제 모델 호출은 없다.
// 가짜 새 메인의 응답은 test/fake-cli/.fake-takeover(JSON)로 정한다(자식 프로세스 환경은 정리되어 전달되므로).
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { grantApproval } from '../src/executor/mainApprovals.ts';
import { onMainEnd } from '../src/executor/mainEnd.ts';
import { handoverMain } from '../src/executor/mainHandover.ts';
import { handoverAfterLimit } from '../src/executor/mainLimit.ts';
import { resumeStep, startTask } from '../src/runtime.ts';
import { applyActions, fakeCli, setup, task, verify, waitFor, type Env } from './helpers.ts';

const real = { allowRealModelCalls: true, confirmedSubscriptionAuth: true, cli: fakeCli };
const flag = path.join(path.dirname(fakeCli.codex), '.fake-takeover');
const script = (o: Record<string, unknown>) => fs.writeFileSync(flag, JSON.stringify(o));
const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=session', '-c', 'user.email=s@l', ...a], { cwd }).toString().trim();

/** 구현이 끝나 메인 인계 확인까지 된(승인 가능한) 작업을 만든다. 전체 SHA를 돌려준다. */
async function ready(env: Env, name: string, dir: string) {
  await assign(env.ex, task(env, name, { mode: 'manual', allowedFiles: [`${dir}/`] }));
  await startTask(name);
  const wt = env.fixture.worktrees[name].path;
  fs.appendFileSync(path.join(wt, dir, 'work.txt'), 'change\n');
  gitOut(wt, 'add', '--', `${dir}/work.txt`); gitOut(wt, 'commit', '-qm', `feat: ${name}`);
  await finishManual(env.ex, name);
  await waitFor(() => getTask(env.ex, name).status === 'review_pending', `${name} review`);
  await verify(env, name);
  await handoffToMain(env.ex, name);
  confirmHandoff(env.ex, name, '테스트 확인');
  return getTask(env.ex, name).result!.headSha!;
}

/** 화면·API와 같은 연결: 승인은 기존 승인 함수와 workflow 재개로 수행한다. */
function wire(env: Env) {
  (env.ex.mainOps = { approve: async (id, sha) => {
    const a = await approve(env.ex, id, sha, { requireHandoff: true });
    await resumeStep(getTask(env.ex, id).runId!, 'review-gate', { decision: 'approve', sha: a.sha });
  } });
}

/** 교대가 끝날 때까지(성공이면 completed/idle, 실패면 history의 failed) 기다린다. */
const finished = (env: Env) => waitFor(() => {
  const rt = env.ex.runtime;
  if (rt.session && ['completed', 'idle'].includes(rt.session.status)) return rt.session;
  const last = rt.history[rt.history.length - 1];
  return rt.session === null && last?.status === 'failed' ? last : null;
}, '교대 종료');

async function withFlag<T>(env: Env, fn: () => Promise<T>) {
  try { return await fn(); } finally { fs.rmSync(flag, { force: true }); env.cleanup(); }
}

test('양방향 교대: 인수 확인 뒤에만 메인이 바뀌고, 승인은 재승인 없이 승계되며, 교대 중에는 이전 메인의 상태 변경이 차단된다', async () => {
  const env = setup(real);
  await withFlag(env, async () => {
    const shaA = await ready(env, 'task-a', 'src_a'), shaB = await ready(env, 'task-b', 'src_b');
    const contractA = { sha: getTask(env.ex, 'task-a').contractSha, hash: getTask(env.ex, 'task-a').contractHash };
    wire(env);
    grantApproval(env.ex, { basis: '사용자 승인: 개발·통합 승인 범위(2026-10-28 테스트)', actions: ['approve_task'], targets: ['task-a', 'task-b'] });
    script({ actions: [{ id: 'a1', type: 'approve_task', taskId: 'task-a', sha: shaA }] });

    assert.equal(env.ex.mainAgent, 'codex');
    const r = await handoverMain(env.ex, 'claude', { reason: '토큰 이슈' });
    assert.equal(r.status, 'launching');
    assert.equal(env.ex.mainAgent, 'codex', '인수 확인 전에는 메인이 바뀌지 않음');
    assert.equal(env.ex.runtime.frozen, true);
    await assert.rejects(assign(env.ex, task(env, 'task-c', { mode: 'manual' })), /메인 교대 중/);
    await assert.rejects(handoverMain(env.ex, 'claude'), /이미 진행 중/, '교대 중 중복 교대 명령 차단');
    const s1 = await finished(env);
    assert.equal(s1.status, 'completed');
    assert.equal(env.ex.mainAgent, 'claude');
    assert.equal(env.ex.state.main!.generation, 1);
    assert.equal(env.ex.runtime.frozen, false);
    assert.equal(getTask(env.ex, 'task-a').status, 'approved', '새 메인이 다음 승인 작업을 실제로 처리');
    assert.equal(getTask(env.ex, 'task-a').contractSha, contractA.sha, '교대했다는 이유로 확정된 계약을 다시 만들거나 바꾸지 않음');
    assert.equal(getTask(env.ex, 'task-a').contractHash, contractA.hash);
    assert.ok(s1.ackedAt && s1.completedAt);

    script({ actions: [{ id: 'b1', type: 'approve_task', taskId: 'task-b', sha: shaB }] });
    await handoverMain(env.ex, 'codex');
    const s2 = await finished(env);
    assert.equal(s2.status, 'completed');
    assert.equal(env.ex.mainAgent, 'codex');
    assert.equal(env.ex.runtime.generation, 2);
    assert.equal(getTask(env.ex, 'task-b').status, 'approved', '재승인 없이 같은 승인 범위를 승계');
  });
});

test('승인 범위: 장부 범위 안만 수행하고 범위 밖 작업·실험·force push·세션에 묶인 승인은 차단한다', async () => {
  const env = setup(real);
  await withFlag(env, async () => {
    const shaA = await ready(env, 'task-a', 'src_a'), shaB = await ready(env, 'task-b', 'src_b');
    wire(env);
    grantApproval(env.ex, { basis: 'task-a 승인', actions: ['approve_task'], targets: ['task-a'] });
    grantApproval(env.ex, { basis: '이전 세션에 묶인 승인', actions: ['approve_task'], targets: ['task-b'], boundSessionId: 'old-session' });
    assert.throws(() => grantApproval(env.ex, { basis: '', actions: ['approve_task'] }), /승인 근거/);
    script({ actions: [
      { id: 'ok', type: 'approve_task', taskId: 'task-a', sha: shaA },
      { id: 'other', type: 'approve_task', taskId: 'task-b', sha: shaB },
      { id: 'exp', type: 'run_experiment', target: 'exp-1' },
      { id: 'fp', type: 'force_push' },
      { id: 'asg', type: 'assign_task', input: { taskId: 'task-n' } },
    ] });
    await handoverMain(env.ex, 'claude');
    const s = await finished(env);
    const byId = Object.fromEntries(s.actionResults.map((x) => [x.id, x]));
    assert.equal(byId.ok.ok, true);
    assert.match(byId.other.detail, /승인 범위 밖.*다른 세션에 묶인 승인은 승계하지 않음/);
    assert.match(byId.exp.detail, /승인 범위 밖: run_experiment/);
    assert.match(byId.fp.detail, /어떤 승인으로도 자동 승계·수행하지 않음/);
    assert.match(byId.asg.detail, /승인 범위 밖: assign_task/);
    assert.equal(getTask(env.ex, 'task-a').status, 'approved');
    assert.equal(getTask(env.ex, 'task-b').status, 'review_pending', '범위 밖 작업은 건드리지 않음');
    assert.equal(s.status, 'completed', '범위 안 행동 하나가 실제로 수행됨');
  });
});

test('이전 메인의 지연 응답·중복 명령 차단: 같은 행동 ID는 한 번만, 이전 세대·이전 세션의 결과는 상태를 바꾸지 못한다', async () => {
  const env = setup(real);
  await withFlag(env, async () => {
    const shaA = await ready(env, 'task-a', 'src_a');
    wire(env);
    grantApproval(env.ex, { basis: '승인', actions: ['approve_task'], targets: '*' });
    const act = { id: 'dup', type: 'approve_task', taskId: 'task-a', sha: shaA };
    script({ actions: [act, act] });
    await handoverMain(env.ex, 'claude');
    const s1 = await finished(env);
    assert.deepEqual(s1.actionResults.map((x) => x.ok), [true, false]);
    assert.match(s1.actionResults[1].detail, /중복 행동 ID/);

    // 이전 세대: 이 세션 이후 교대가 한 번 더 일어난 뒤 늦게 도착한 옛 세션의 행동
    script({});
    await handoverMain(env.ex, 'codex');
    await finished(env);
    const before = JSON.stringify(getTask(env.ex, 'task-a'));
    const late = await applyActions(env.ex, s1, [{ id: 'late', type: 'approve_task', taskId: 'task-a', sha: shaA }]);
    assert.match(late[0].detail, /이전 세대의 메인/);
    assert.equal(JSON.stringify(getTask(env.ex, 'task-a')), before, '늦은 이전 세션은 상태를 덮어쓰지 못함');
    // 이전 세션의 프로세스 종료 알림도 무시
    const stale = { ...env.ex.state.executions[s1.execId!] };
    await onMainEnd(env.ex, stale, { code: 0, cancelled: false, unknown: false });
    assert.equal(env.ex.mainAgent, 'codex');
    assert.ok(fs.readFileSync(path.join(env.cfg.stateDir, 'events.jsonl'), 'utf8').includes('main_stale_result_rejected'));
  });
});

test('한도 오류 직후 복구: 마지막 인계문 없이 저장된 상태로 교대하고, 진행 중 구현 에이전트는 중단하지 않고 인수한다. 행동이 없으면 완료가 아니라 인수만 표시', async () => {
  const env = setup(real);
  await withFlag(env, async () => {
    await assign(env.ex, task(env, 'task-c', { mode: 'mock', mockScenario: 'slow-success', allowedFiles: ['src_c/'] }));
    await startTask('task-c');
    await waitFor(() => getTask(env.ex, 'task-c').status === 'running', 'running');
    script({ actions: [] });
    const r = await handoverAfterLimit(env.ex, 'claude', [], 'codex 한도 소진');
    assert.equal(r.status, 'launching', '한도 복구는 진행 중인 실행을 기다리지 않음');
    assert.ok(env.ex.runtime.limited.codex, '한도에 닿은 쪽이 기록됨');
    const cp = JSON.parse(fs.readFileSync(env.ex.runtime.lastCheckpoint!, 'utf8'));
    assert.equal(cp.why, 'limit-recovery');
    assert.ok(cp.inheritedExecutions.some((e: any) => e.taskId === 'task-c' && e.kind === 'agent'), '진행 중 구현 에이전트를 인수 대상으로 기록');
    const row = cp.tasks.find((t: any) => t.taskId === 'task-c');
    assert.equal(row.occupying, true, '진행 중 작업은 점유 파일과 함께 기록');
    assert.deepEqual(row.allowedFiles, ['src_c/']);
    assert.ok(!fs.existsSync(path.join(env.cfg.stateDir, 'main-handoffs')), '이전 메인이 쓴 인계 메모 없이 복구');
    const s = await finished(env);
    assert.equal(s.status, 'idle', '행동 근거가 없으면 완료로 표시하지 않음');
    assert.equal(env.ex.mainAgent, 'claude');
    // 구현 에이전트는 계속 실행되어 결과가 나온다(중단되지 않음)
    await waitFor(() => getTask(env.ex, 'task-c').status === 'review_pending', '구현 결과 인수', 30_000);
    const ag = Object.values(env.ex.state.executions).find((e) => e.taskId === 'task-c' && (e.kind ?? 'agent') === 'agent')!;
    assert.equal(ag.status, 'exited');
    assert.equal(ag.cancelRequested, false);
  });
});

test('결과 불명 대상은 확인 전에 다시 수행하지 않는다(작업·push)', async () => {
  const env = setup(real);
  await withFlag(env, async () => {
    const shaA = await ready(env, 'task-a', 'src_a');
    wire(env);
    grantApproval(env.ex, { basis: '승인', actions: ['approve_task', 'integrate_task'], targets: '*' });
    getTask(env.ex, 'task-a').status = 'unknown';
    env.ex.state.pushes = { p1: { id: 'p1', status: 'push_unverified', tasks: ['task-p'], at: new Date().toISOString(), preRemoteHead: 'a'.repeat(40), pushedSha: 'b'.repeat(40) } as any };
    script({ actions: [{ id: 'u1', type: 'approve_task', taskId: 'task-a', sha: shaA }, { id: 'p1', type: 'integrate_task', taskId: 'task-p' }] });
    await handoverAfterLimit(env.ex, 'claude', [], '메인 한도 소진 보고(사용자)'); // 일반 교대는 push 결과 불명을 막는다 → 한도 복구 경로로 확인
    const s = await finished(env);
    assert.match(s.actionResults[0].detail, /결과 불명·진행 중\(unknown\)/);
    assert.match(s.actionResults[1].detail, /push 결과 불명.*원격 확인 전 재수행하지 않음/);
    const cp = JSON.parse(fs.readFileSync(s.checkpointFile, 'utf8'));
    assert.equal(cp.tasks[0].doNotRetry, true);
    assert.deepEqual(cp.nextActionCandidates, [], '결과 불명 작업은 다음 행동 후보에서 제외');
    assert.ok(cp.pushes[0].doNotRetry);
    assert.equal(s.status, 'idle');
  });
});

test('교대 실패는 상태와 복구 지점을 보존하고 재시도하지 않는다: 새 메인 실행 불가·인수 확인 불일치·결과 없음·종료코드·양쪽 한도', async () => {
  const env = setup({ ...real, cli: { ...fakeCli, codex: '/nonexistent/codex' } });
  await withFlag(env, async () => {
    await ready(env, 'task-a', 'src_a');
    env.ex.state.main = { agent: 'claude', since: 'x', generation: 0 };
    const snap = () => JSON.stringify(Object.values(env.ex.state.tasks).map((t) => [t.taskId, t.status]));
    const before = snap(), execs = () => Object.keys(env.ex.state.executions).length;
    const n0 = execs();

    const r1 = await handoverMain(env.ex, 'codex');
    assert.equal(r1.status, 'launching');
    const f1 = await finished(env);
    assert.equal(f1.status, 'failed');
    assert.match(f1.failure!, /새 메인 실행 실패: 실제 codex 메인 실행 차단/);
    assert.ok(fs.existsSync(f1.checkpointFile), '복구 지점(체크포인트) 보존');
    assert.equal(env.ex.mainAgent, 'claude'); assert.equal(env.ex.runtime.frozen, false); assert.equal(env.ex.runtime.session, null);
    assert.equal(snap(), before, '작업 상태는 그대로');
    await new Promise((r) => setTimeout(r, 800));
    assert.equal(execs(), n0, '자동 재시도 없음');

    for (const [mode, re] of [['badhead', /인수 확인 불일치.*관찰한 헤드가 실제 Git과 다름/], ['nojson', /결과 JSON을 읽지 못함/], ['exit1', /종료코드 1/]] as const) {
      env.ex.state.main = { agent: 'codex', since: 'x', generation: 0 };
      env.ex.runtime.generation = 0;
      script({ mode });
      await handoverMain(env.ex, 'claude');
      const f = await finished(env);
      assert.equal(f.status, 'failed', mode);
      assert.match(f.failure!, re, mode);
      assert.equal(env.ex.mainAgent, 'codex', `${mode}: 인수 확인에 실패하면 메인이 바뀌지 않음`);
      assert.equal(env.ex.runtime.generation, 0);
    }
    assert.equal(env.ex.runtime.failures.length, 4);

    // 한도: 새 메인이 한도 문구를 내면 그 에이전트만 막히고, 다음 교대는 시도하지 않는다.
    env.ex.runtime.history.length = 0;
    script({ mode: 'limit' });
    await handoverMain(env.ex, 'claude');
    const lf = await finished(env);
    assert.match(lf.failure!, /한도 소진.*재시도하지 않음/);
    assert.ok(env.ex.runtime.limited.claude);
    const n1 = execs();
    const both = await handoverAfterLimit(env.ex, 'claude', [], 'codex도 한도');
    assert.equal(both.status, 'blocked_both_limited', '양쪽 한도 소진');
    assert.equal(execs(), n1, '새 프로세스를 시작하지 않음');
    assert.equal(env.ex.mainAgent, 'codex');
    assert.equal(limitOf(env.ex), null, '메인이 낸 한도는 구현 에이전트 전체 한도로 번지지 않음');
  });
});

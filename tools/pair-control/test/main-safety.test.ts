import { handoffToMain } from '../src/executor/handoffCreate.ts';
import { confirmHandoff } from '../src/executor/handoffRecords.ts';
// 메인 교대 안전성 회귀: 검토(2026-10-29)에서 재현된 반례를 합성 fixture로 고정한다. 가짜 CLI·스텁만 쓰며 실제 모델 호출은 없다.
// 합성 검사이므로 실제 Codex/Claude CLI 검증이 아니다.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { authorize, grantApproval } from '../src/executor/mainApprovals.ts';
import { saveCheckpoint } from '../src/executor/mainCheckpoint.ts';
import { onMainEnd } from '../src/executor/mainEnd.ts';
import { handoverMain } from '../src/executor/mainHandover.ts';
import { handoverAfterLimit } from '../src/executor/mainLimit.ts';
import { hashOf } from '../src/executor/mainCheckpoint.ts';
import { tokenHash } from '../src/executor/mainTakeover.ts';
import { resumeStep, startTask } from '../src/runtime.ts';
import { applyActions, setup, task, verify, waitFor, type Env } from './helpers.ts';

const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd }).toString().trim();

/** 현재 세션을 taken_over 상태의 유효한 메인으로 세운다. */
function session(env: Env, id = 'sess', generation = 1): any {
  const s: any = { id, agent: 'claude', from: 'codex', generation, status: 'taken_over', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: tokenHash('tok'), actionResults: [] };
  env.ex.runtime.generation = generation; env.ex.runtime.session = s;
  return s;
}
const assignInput = { agent: 'claude', mode: 'mock', goal: '합성 배정', allowedFiles: ['src_a/work.txt'], env: 'none' };

/** 구현·확인·승인 직전까지 끝난 작업(전체 SHA 반환). approved=true면 승인까지. */
async function ready(env: Env, name: string, opts: { approved?: boolean; confirm?: boolean } = {}) {
  await env.ex.assign(task(env, name, { mode: 'manual', allowedFiles: ['src_a/'] }));
  await startTask(name);
  const wt = env.fixture.worktrees[name].path;
  fs.appendFileSync(path.join(wt, 'src_a/work.txt'), 'change\n');
  git(wt, 'add', '--', 'src_a/work.txt'); git(wt, 'commit', '-qm', `feat: ${name}`);
  await env.ex.finishManual(name);
  await waitFor(() => env.ex.task(name).status === 'review_pending', `${name} review`);
  await verify(env, name);
  await handoffToMain(env.ex, name);
  if (opts.confirm !== false) confirmHandoff(env.ex, name, '합성 확인');
  const sha = env.ex.task(name).result!.headSha!;
  if (opts.approved) { const a = await env.ex.approve(name, sha, { requireHandoff: true }); await resumeStep(env.ex.task(name).runId!, 'review-gate', { decision: 'approve', sha: a.sha }); }
  return sha;
}

async function withEnv(fn: (env: Env) => Promise<void>) {
  const env = setup();
  try { await fn(env); } finally { env.cleanup(); }
}

// ---------- 1. 승인 대상 = 실제 배정 대상 ----------
test('배정: 승인된 task ID만 실제로 생성하고, 승인 밖·불일치 ID는 아무 작업도 만들지 않는다', async () => withEnv(async (env) => {
  const s = session(env);
  grantApproval(env.ex, { basis: '합성: 이름 지정 승인', actions: ['assign_task'], targets: ['only-approved-task'] });
  const r1 = await applyActions(env.ex, s, [{ id: 'a1', type: 'assign_task', taskId: 'only-approved-task', input: { ...assignInput } }]);
  assert.equal(r1[0].ok, true, r1[0].detail);
  assert.deepEqual(Object.keys(env.ex.state.tasks), ['only-approved-task'], '승인된 ID 하나만 생성');

  // ID가 없으면 자동 생성될 ID가 승인 대상이 아니므로 거부(작업 생성 없음)
  const r2 = await applyActions(env.ex, s, [{ id: 'a2', type: 'assign_task', input: { ...assignInput } }]);
  assert.equal(r2[0].ok, false);
  assert.match(r2[0].detail, /승인 범위 밖: assign_task/);
  // 바깥 taskId와 input.taskId가 다르면 거부
  const r3 = await applyActions(env.ex, s, [{ id: 'a3', type: 'assign_task', taskId: 'only-approved-task', input: { ...assignInput, taskId: 'other-task' } }]);
  assert.equal(r3[0].ok, false);
  assert.match(r3[0].detail, /일치하지 않음/);
  assert.equal(Object.keys(env.ex.state.tasks).length, 1, '승인 밖 작업이 생성되지 않음');
}));

test('배정: 전체 승인(*)이면 자동 생성 ID로 배정하고 실제 생성된 ID를 결과에 남긴다', async () => withEnv(async (env) => {
  const s = session(env);
  grantApproval(env.ex, { basis: '합성: 전체 승인', actions: ['assign_task'], targets: '*' });
  const r = await applyActions(env.ex, s, [{ id: 'a1', type: 'assign_task', input: { ...assignInput } }]);
  assert.equal(r[0].ok, true, r[0].detail);
  const ids = Object.keys(env.ex.state.tasks);
  assert.equal(ids.length, 1);
  assert.ok(r[0].detail.includes(ids[0]), '결과에 실제 task ID 기록');
}));

// ---------- 2. 조건부 승인 ----------
test('조건부 승인: 자유 문장 조건은 자동 수행을 보류하고, 구조화 조건(handoffConfirmed)은 실제로 검사한다', async () => withEnv(async (env) => {
  grantApproval(env.ex, { basis: '합성: 문장 조건', actions: ['approve_task'], targets: ['task-a'], conditions: '새 SHA를 사람이 확인하기 전에는 실행하지 않는다' });
  assert.throws(() => authorize(env.ex, 'x', 'approve_task', 'task-a'), /검증할 수 없는 조건.*자동 수행 보류/);
  // 장부에 이미 있던 조건부 승인도 무조건 승인으로 바뀌지 않는다
  env.ex.runtime.approvals.push({ id: 'legacy', basis: '기존', actions: ['approve_task'], repo: env.ex.cfg.repo, branch: env.ex.cfg.integration.branch, targets: '*', conditions: '사람 확인 후', grantedAt: 'x' });
  assert.throws(() => authorize(env.ex, 'x', 'approve_task', 'task-z'), /자동 수행 보류/);

  const env2 = setup();
  try {
    const sha = await ready(env2, 'task-a', { confirm: false });
    const s = session(env2);
    grantApproval(env2.ex, { basis: '합성: 구조화 조건', actions: ['approve_task'], targets: ['task-a'], requires: { handoffConfirmed: true } });
    const calls: string[] = [];
    env2.ex.setMainOps({ approve: async (id) => { calls.push(id); } });
    const r1 = await applyActions(env2.ex, s, [{ id: 'c1', type: 'approve_task', taskId: 'task-a', sha }]);
    assert.equal(r1[0].ok, false);
    assert.match(r1[0].detail, /조건 미충족.*메인 확인/);
    assert.deepEqual(calls, [], '조건 미충족이면 실행하지 않음');
    confirmHandoff(env2.ex, 'task-a', '합성 확인');
    const r2 = await applyActions(env2.ex, s, [{ id: 'c2', type: 'approve_task', taskId: 'task-a', sha: 'f'.repeat(40) }]);
    assert.equal(r2[0].ok, false, '확인된 SHA와 다른 SHA는 조건 미충족');
  } finally { env2.cleanup(); }
}));

// ---------- 3. 통합·승인의 실제 결과 ----------
test('통합 결과: 차단·거절·충돌·검사 실패·상태 미변경은 성공으로 기록하지 않고, 교대 completed 근거가 아니다', async () => withEnv(async (env) => {
  const s = session(env);
  grantApproval(env.ex, { basis: '합성', actions: ['approve_task', 'integrate_task'], targets: '*' });
  for (const status of ['integration_blocked', 'integration_refused', 'integration_conflict', 'integrated_check_failed', 'approved'] as const) {
    const id = `t-${status}`;
    env.ex.state.tasks[id] = { taskId: id, status: 'approved' } as any;
    env.ex.setMainOps({ integrate: async () => { env.ex.state.tasks[id].status = status; } });
    const r = await applyActions(env.ex, s, [{ id: `i-${status}`, type: 'integrate_task', taskId: id }]);
    assert.equal(r[0].ok, false, `${status}는 성공이 아님`);
    assert.ok(r[0].detail.includes(status), r[0].detail);
  }
  // integrated여도 통합 HEAD가 없거나 필수 통합 후 검사가 통과하지 않았으면 성공이 아님
  const cases: [string, any][] = [['no-head', { postStatus: 'not_run' }], ['post-failed', { newHead: 'a'.repeat(40), postStatus: 'failed' }]];
  for (const [name, integration] of cases) {
    const id = `t-${name}`;
    env.ex.state.tasks[id] = { taskId: id, status: 'approved', postChecks: [{}] } as any;
    env.ex.setMainOps({ integrate: async () => { Object.assign(env.ex.state.tasks[id], { status: 'integrated', integration }); } });
    const r = await applyActions(env.ex, s, [{ id: `i-${name}`, type: 'integrate_task', taskId: id }]);
    assert.equal(r[0].ok, false, name);
  }
  // 모든 근거를 갖춘 통합만 성공
  env.ex.state.tasks['t-ok'] = { taskId: 't-ok', status: 'approved', postChecks: [{}] } as any;
  env.ex.setMainOps({ integrate: async () => { Object.assign(env.ex.state.tasks['t-ok'], { status: 'integrated', integration: { newHead: 'a'.repeat(40), postStatus: 'passed' } }); } });
  const ok = await applyActions(env.ex, s, [{ id: 'i-ok', type: 'integrate_task', taskId: 't-ok' }]);
  assert.equal(ok[0].ok, true, ok[0].detail);
}));

test('통합 결과: 실제 workflow에서 통합 checkout이 깨끗하지 않아 차단되면 행동은 실패이고 세션은 completed가 아니다', async () => withEnv(async (env) => {
  await ready(env, 'task-a', { approved: true });
  fs.writeFileSync(path.join(env.fixture.repo, 'unrelated-untracked.txt'), '사용자 작업');
  const before = git(env.fixture.repo, 'rev-parse', 'HEAD');
  const s = session(env);
  grantApproval(env.ex, { basis: '합성', actions: ['integrate_task'], targets: ['task-a'] });
  const r = await applyActions(env.ex, s, [{ id: 'blocked', type: 'integrate_task', taskId: 'task-a' }]);
  assert.equal(r[0].ok, false);
  assert.match(r[0].detail, /통합되지 않음/);
  assert.equal(git(env.fixture.repo, 'rev-parse', 'HEAD'), before);
  assert.notEqual(s.actionResults.some((x: any) => x.ok && x.type !== 'note'), true, '성공 근거 없음');
  // 막힌 원인을 치우면 같은 작업의 새 행동 ID로 실제 통합되고 성공으로 기록된다
  fs.rmSync(path.join(env.fixture.repo, 'unrelated-untracked.txt'));
  const r2 = await applyActions(env.ex, s, [{ id: 'retry-new-id', type: 'integrate_task', taskId: 'task-a' }]);
  assert.equal(r2[0].ok, true, r2[0].detail);
  assert.equal(env.ex.task('task-a').status, 'integrated');
}));

// ---------- 4. 잘못된 모델 출력 ----------
async function takeoverWith(env: Env, body: Record<string, unknown>) {
  const cp = await saveCheckpoint(env.ex, 'synthetic');
  const s = session(env);
  Object.assign(s, { status: 'launching', checkpointFile: cp.file, checkpointHash: cp.hash, execId: 'x1' });
  env.ex.runtime.generation = 0; env.ex.runtime.frozen = true;
  const logPath = path.join(env.dir, 'out.log');
  fs.writeFileSync(logPath, JSON.stringify({ session_id: s.id, generation: 1, token: 'tok', checkpoint_hash: cp.hash, observed: { heads: {} }, actions: [], ...body }));
  await onMainEnd(env.ex, { execId: 'x1', logPath, runId: s.id } as any, { code: 0, cancelled: false, unknown: false });
  return { s, cp };
}

test('잘못된 응답: 응답·행동 구조가 틀리면 메인·세대를 바꾸지 않고 체크포인트와 실패 근거를 남기며 예외를 내보내지 않는다', async () => {
  const bad: Record<string, Record<string, unknown>> = {
    'actions가 객체': { actions: {} }, 'actions가 문자열': { actions: 'approve' }, '항목이 null': { actions: [null] }, '항목이 문자열': { actions: ['x'] },
    'id 없음': { actions: [{ type: 'note' }] }, 'id가 숫자': { actions: [{ id: 5, type: 'note' }] }, '지원하지 않는 행동': { actions: [{ id: 'a', type: 'rm_rf' }] },
    'taskId가 숫자': { actions: [{ id: 'a', type: 'approve_task', taskId: 7 }] }, 'input이 배열': { actions: [{ id: 'a', type: 'assign_task', input: [] }] },
    'observed가 문자열': { observed: 'x' }, 'heads가 배열': { observed: { heads: [] } },
  };
  for (const [name, body] of Object.entries(bad)) {
    const env = setup();
    try {
      const { s } = await takeoverWith(env, body);
      assert.equal(env.ex.mainAgent, 'codex', `${name}: 메인 불변`);
      assert.equal(env.ex.runtime.generation, 0, `${name}: 세대 불변`);
      assert.equal(env.ex.runtime.frozen, false);
      assert.equal(env.ex.runtime.session, null);
      assert.equal(s.status, 'failed', name);
      const f = env.ex.runtime.failures.at(-1)!;
      assert.match(f.reason, /응답 형식/, name);
      assert.ok(f.checkpointFile && fs.existsSync(f.checkpointFile), `${name}: 체크포인트 보존`);
    } finally { env.cleanup(); }
  }
});

test('잘못된 응답: 행동 수행 중 예기치 않은 예외도 감시 루프로 새지 않고 해당 행동만 실패로 기록한다', async () => withEnv(async (env) => {
  const s = session(env);
  grantApproval(env.ex, { basis: '합성', actions: ['approve_task'], targets: '*' });
  env.ex.state.tasks['t1'] = { taskId: 't1', status: 'review_pending' } as any;
  env.ex.audit = () => { throw new Error('audit 실패'); };
  const r = await applyActions(env.ex, s, [{ id: 'boom', type: 'approve_task', taskId: 't1', sha: 'a'.repeat(40) }]).catch((e) => e);
  assert.ok(Array.isArray(r), String(r));
}));

// ---------- 5. 행동 실행 중 소유권·중복 ----------
const gate = () => { let open!: () => void; const p = new Promise<void>((r) => { open = r; }); return { p, open }; };
const tick = () => new Promise((r) => setTimeout(r, 30));

test('소유권: 행동 묶음 도중 세대가 바뀌면 이전 메인의 남은 행동은 수행되지 않는다', async () => withEnv(async (env) => {
  const s = session(env, 'old', 1);
  grantApproval(env.ex, { basis: '합성', actions: ['approve_task'], targets: '*' });
  env.ex.state.tasks['task-a'] = { taskId: 'task-a', status: 'review_pending' } as any;
  env.ex.state.tasks['task-b'] = { taskId: 'task-b', status: 'review_pending' } as any;
  const g = gate(); const calls: string[] = [];
  env.ex.setMainOps({ approve: async (id) => { calls.push(id); env.ex.state.tasks[id].status = 'approved'; if (calls.length === 1) await g.p; } });
  const p = applyActions(env.ex, s, [{ id: 'one', type: 'approve_task', taskId: 'task-a' }, { id: 'two', type: 'approve_task', taskId: 'task-b' }]);
  await tick();
  env.ex.runtime.session = { ...s, id: 'new', generation: 2 }; env.ex.runtime.generation = 2;
  g.open();
  const r = await p;
  assert.deepEqual(calls, ['task-a']);
  assert.equal(r[1].ok, false);
  assert.match(r[1].detail, /이전 세대/);
}));

test('소유권: 행동 실행 중 시작된 교대는 그 행동이 끝난 뒤에 진행되고, 이전 메인의 남은 행동은 정지 상태로 거부된다', async () => withEnv(async (env) => {
  const s = session(env, 'old', 1);
  grantApproval(env.ex, { basis: '합성', actions: ['approve_task'], targets: '*' });
  env.ex.state.tasks['task-a'] = { taskId: 'task-a', status: 'review_pending' } as any;
  env.ex.state.tasks['task-b'] = { taskId: 'task-b', status: 'review_pending' } as any;
  const g = gate(); const calls: string[] = [];
  env.ex.setMainOps({ approve: async (id) => { calls.push(id); env.ex.state.tasks[id].status = 'approved'; if (calls.length === 1) await g.p; } });
  env.ex.launchMainProcess = async () => 'synthetic-exec';
  const p = applyActions(env.ex, s, [{ id: 'one', type: 'approve_task', taskId: 'task-a' }, { id: 'two', type: 'approve_task', taskId: 'task-b' }]);
  await tick();
  const h = handoverAfterLimit(env.ex, 'claude', [], '메인 한도 소진 보고(사용자)');
  await tick();
  assert.equal(env.ex.runtime.frozen, false, '진행 중인 행동이 끝나기 전에는 교대가 정지를 걸지 않음');
  g.open();
  const [r, hr] = await Promise.all([p, h]);
  assert.equal(hr.status, 'launching');
  assert.deepEqual(calls, ['task-a'], '교대가 시작된 뒤 이전 메인의 남은 행동은 수행되지 않음');
  assert.equal(r[0].ok, true);
  assert.equal(r[1].ok, false);
}));

test('중복: 같은 행동 ID는 동시에 보내도 한 번만 수행되고, 수행 시작 표시만 남은(결과 불명) 행동은 재실행하지 않는다', async () => withEnv(async (env) => {
  const s = session(env);
  grantApproval(env.ex, { basis: '합성', actions: ['approve_task'], targets: '*' });
  env.ex.state.tasks['task-a'] = { taskId: 'task-a', status: 'review_pending' } as any;
  const g = gate(); let calls = 0;
  env.ex.setMainOps({ approve: async (id) => { calls++; env.ex.state.tasks[id].status = 'approved'; await g.p; } });
  const act = { id: 'same', type: 'approve_task', taskId: 'task-a' };
  const p1 = applyActions(env.ex, s, [act]); const p2 = applyActions(env.ex, s, [act]);
  await tick();
  assert.equal(env.ex.runtime.processed['same']?.ok, false, '실행 전에 수행 중 표시를 먼저 남김');
  assert.match(env.ex.runtime.processed['same'].detail, /수행 중/);
  g.open();
  const [a, b] = await Promise.all([p1, p2]);
  assert.equal(calls, 1);
  assert.deepEqual([a[0].ok, b[0].ok].sort(), [false, true]);
  assert.equal(env.ex.runtime.processed['same'].ok, true, '완료 후 결과로 갱신');

  // 프로세스가 수행 중 표시만 남기고 죽은 경우를 흉내: 재시작 후에도 같은 ID는 재실행하지 않는다
  env.ex.runtime.processed['crashed'] = { id: 'crashed', type: 'approve_task', ok: false, detail: '수행 중(완료 기록 전 중단되면 결과 불명 — 재실행하지 않음)', at: 'x' };
  const c = await applyActions(env.ex, s, [{ id: 'crashed', type: 'approve_task', taskId: 'task-a' }]);
  assert.equal(c[0].ok, false);
  assert.equal(calls, 1);
}));

// ---------- 6. 구조 기준 보조 검증 ----------
test('체크포인트 해시는 키 순서와 무관하고 재귀 없이 계산된다', () => {
  assert.equal(hashOf({ a: 1, b: { c: [1, { d: 2, e: 3 }], f: null } }), hashOf({ b: { f: null, c: [1, { e: 3, d: 2 }] }, a: 1 }));
  assert.notEqual(hashOf({ a: 1 }), hashOf({ a: 2 }));
});

test('구조: 메인 교대 파일은 익명 콜백 포함 함수 정의가 7개 이하다(전체 구조 점검은 structure-trace.test.ts·review-fixes.test.ts)', () => {
  const files = ['mainApprovals', 'mainCheckpoint', 'mainEnd', 'mainGuard', 'mainHandover', 'mainOutcome', 'mainSerial', 'mainSessionLaunch'].map((n) => `src/executor/${n}.ts`);
  const out = JSON.parse(execFileSync('node', ['scripts/structure-trace.mjs'], { cwd: path.resolve(import.meta.dirname, '..'), stdio: ['ignore', 'pipe', 'ignore'] }).toString());
  for (const f of files) assert.ok(out.perFile[f] <= 7, `${f}: ${out.perFile[f]}개`);
});

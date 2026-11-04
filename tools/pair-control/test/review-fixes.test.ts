import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
import { finishManual } from '../src/executor/taskManual.ts';
import { spawnSupervised } from '../src/executor/processSupervisor.ts';
import { handoffToMain } from '../src/executor/handoffCreate.ts';
import { confirmHandoff } from '../src/executor/handoffRecords.ts';
// 연속 관제 통합 검토(2026-10-29) 반례 회귀: 공급자별 한도, 자동 push 커밋 범위, 조건 미확정 보류, selfReview 승인 선택, 정지·spawn 오류, 재시작 정책, 구조 기준.
// 가짜 CLI·임시 bare 원격·스텁만 쓰며 실제 Codex/Claude/Gemini 호출·운영 push는 없다. 합성 계약/회귀 검사이지 실제 CLI 검증이 아니다.
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { acceptActions } from '../src/executor/actionState.ts';
import { authorize, grantApproval, revokeApproval } from '../src/executor/mainApprovals.ts';
import { handoverMain } from '../src/executor/mainHandover.ts';
import { handoverAfterLimit } from '../src/executor/mainLimit.ts';
import { pipelineTick } from '../src/executor/pipelineTick.ts';
import { pipe } from '../src/executor/pipelineState.ts';
import { runPush } from '../src/executor/push.ts';
import { resumeStep, startTask } from '../src/runtime.ts';
import { advanceActions, applyActions, setup, task, verify, waitFor, type Env } from './helpers.ts';

const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd, stdio: 'pipe' }).toString().trim();
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const LIMIT = "You've hit your usage limit. Try again later.";
const originHead = (e: Env) => git(e.fixture.origin, 'rev-parse', 'refs/heads/main');

/** 인수 확인이 끝난 유효한 메인 세션을 세운다(턴·행동을 받을 수 있는 idle 상태). */
function owner(e: Env, agent: 'codex' | 'claude' = 'codex') {
  const s: any = { id: 'owner-sess', generation: 1, agent, from: agent === 'codex' ? 'claude' : 'codex', status: 'idle', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: '', actionResults: [], ackedAt: new Date().toISOString() };
  e.ex.runtime.session = s; e.ex.runtime.generation = 1; e.ex.state.main = { agent, generation: 1, since: s.startedAt };
  return s;
}
/** 모델 프로세스를 실제로 띄우지 않고 호출 횟수만 센다. */
function stubLaunch(e: Env) {
  const calls: unknown[] = [];
  (e.ex as any).launchMainProcess = async (o: unknown) => { calls.push(o); return `stub-exec-${calls.length}`; };
  return calls;
}
/** 실제 검사 시작 감사 기록을 센다. */
function countChecks(e: Env) {
  const calls: string[] = [], audit = e.ex.audit.bind(e.ex);
  e.ex.audit = (type, data) => { if (type === 'checks_started') calls.push(String(data.taskId)); audit(type, data); };
  return calls;
}

// ---------- A. 공급자별 한도 ----------
async function slowWorker(e: Env, name: string, dir: string) {
  await assign(e.ex, task(e, name, { mode: 'mock', mockScenario: 'slow-success', allowedFiles: [`${dir}/`] }));
  await startTask(name);
  await waitFor(() => e.ex.task(name).status === 'running', `${name} running`);
  return Object.values(e.ex.state.executions).find((x) => x.taskId === name && (x.kind ?? 'agent') === 'agent')!;
}
const hit = (e: Env, execId: string) => e.ex.guard.scanLog(LIMIT, `exec:${execId}`);

for (const [workerName, workerDir, limitedAgent, otherAgent] of [['task-b', 'src_b', 'codex', 'claude'], ['task-a', 'src_a', 'claude', 'codex']] as const) {
  test(`A. ${limitedAgent} worker 한도: ${limitedAgent}만 막고 ${otherAgent} 메인 교대는 허용한다(전역 차단·상대 공급자 차단 없음)`, { timeout: 60_000 }, async () => {
    const e = setup();
    try {
      owner(e, limitedAgent);
      const ex = await slowWorker(e, workerName, workerDir);
      hit(e, ex.execId);
      assert.equal(e.ex.limit, null, '공급자 실행이 낸 한도는 전역 한도가 아님');
      assert.ok(e.ex.limitFor(limitedAgent), '한도에 닿은 공급자는 막힘');
      assert.equal(e.ex.limitFor(otherAgent), null, '다른 공급자는 막히지 않음');
      stubLaunch(e);
      const r = await handoverAfterLimit(e.ex, otherAgent, [], '합성: worker 한도 복구');
      assert.equal(r.status, 'launching');
    } finally { e.cleanup(); }
  });
}

test('A. 같은 공급자 한도는 다른 세션(새 메인·새 worker)으로 우회할 수 없다', { timeout: 60_000 }, async () => {
  const e = setup({ allowRealModelCalls: true, confirmedSubscriptionAuth: true });
  try {
    owner(e, 'claude');
    const ex = await slowWorker(e, 'task-b', 'src_b'); // codex worker
    hit(e, ex.execId);
    stubLaunch(e);
    const r = await handoverMain(e.ex, 'codex', { reason: '합성: 한도 우회 시도' });
    assert.equal(r.status, 'blocked_target_limited');
    assert.ok(e.ex.limitFor('codex'));
  } finally { e.cleanup(); }
});

test('A. 양쪽 공급자 한도는 blocked_both_limited, 출처를 알 수 없는 한도는 전역 차단을 유지한다', { timeout: 60_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex');
    const b = await slowWorker(e, 'task-b', 'src_b'), a = await slowWorker(e, 'task-a', 'src_a');
    hit(e, b.execId); hit(e, a.execId);
    stubLaunch(e);
    assert.equal((await handoverAfterLimit(e.ex, 'claude', [], '메인 한도 소진 보고(사용자)')).status, 'blocked_both_limited');
  } finally { e.cleanup(); }
  const u = setup();
  try {
    owner(u, 'codex');
    u.ex.guard.scanLog(LIMIT, 'exec:no-such-execution');
    assert.ok(u.ex.limit, '출처 불명 → 보수적 전역 한도');
    assert.ok(u.ex.limitFor('claude'));
    stubLaunch(u);
    assert.equal((await handoverAfterLimit(u.ex, 'claude', [], '메인 한도 소진 보고(사용자)')).status, 'blocked_target_limited');
  } finally { u.cleanup(); }
});

test('A. 한도에 닿은 공급자의 worker만 중단하고 다른 공급자의 진행 중 worker는 보존한다', { timeout: 60_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'claude');
    const codexExec = await slowWorker(e, 'task-b', 'src_b'), claudeExec = await slowWorker(e, 'task-a', 'src_a');
    hit(e, codexExec.execId);
    await waitFor(() => e.ex.state.executions[codexExec.execId].cancelRequested, 'codex worker 중단 요청');
    await sleep(800);
    assert.equal(e.ex.state.executions[claudeExec.execId].cancelRequested, false, '한도에 닿지 않은 claude worker는 중단하지 않음');
    assert.equal(e.ex.task('task-a').status, 'running');
  } finally { e.cleanup(); }
});

// ---------- B. 자동 push의 커밋 범위 ----------
async function integratedTaskA(e: Env) {
  await assign(e.ex, task(e, 'task-a', { mode: 'manual', allowedFiles: ['src_a/'] }));
  await startTask('task-a');
  const wt = e.fixture.worktrees['task-a'].path;
  fs.appendFileSync(path.join(wt, 'src_a/file.txt'), 'review change\n');
  git(wt, 'add', '--', 'src_a/file.txt'); git(wt, 'commit', '-qm', 'synthetic task change');
  await finishManual(e.ex, 'task-a');
  await waitFor(() => e.ex.task('task-a').status === 'review_pending', 'review');
  await verify(e, 'task-a'); await handoffToMain(e.ex, 'task-a');
  const sha = e.ex.task('task-a').result!.headSha!;
  confirmHandoff(e.ex, 'task-a', '합성 검토');
  const a = await approve(e.ex, 'task-a', sha, { requireHandoff: true });
  await resumeStep(e.ex.task('task-a').runId!, 'review-gate', { decision: 'approve', sha: a.sha });
  await resumeStep(e.ex.task('task-a').runId!, 'integrate-gate', { action: 'integrate' });
  assert.equal(e.ex.task('task-a').status, 'integrated');
  return e.ex.task('task-a').integration!.newHead!;
}
const pushGrants = (e: Env) => {
  grantApproval(e.ex, { basis: '합성: task-a 통합 범위', actions: ['integrate_task'], targets: ['task-a'] });
  return grantApproval(e.ex, { basis: '합성: main 일반 push', actions: ['push_main'], targets: ['main'] });
};
const extraCommit = (e: Env, file = 'outside-task.txt') => {
  fs.writeFileSync(path.join(e.fixture.repo, file), 'unreviewed\n');
  git(e.fixture.repo, 'add', '--', file); git(e.fixture.repo, 'commit', '-qm', 'unowned extra commit');
  return git(e.fixture.repo, 'rev-parse', 'HEAD');
};

test('B. 승인된 작업의 커밋만 있으면 합성 원격에 push된다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    const s = owner(e); const head = await integratedTaskA(e); pushGrants(e);
    acceptActions(e.ex, s, [{ id: 'p1', type: 'push_main', target: 'main', sha: head }]);
    assert.equal(s.actionWork[0].status, 'accepted');
    await advanceActions(e.ex, s, s); assert.equal(s.actionWork[0].status, 'authorized');
    await advanceActions(e.ex, s, s); assert.equal(s.actionWork[0].pushStage, 'plan');
    await advanceActions(e.ex, s, s); assert.equal(s.actionWork[0].pushStage, 'scope');
    await advanceActions(e.ex, s, s); assert.equal(s.actionWork[0].pushStage, 'lock');
    await advanceActions(e.ex, s, s); assert.equal(s.actionWork[0].pushStage, 'exec');
    await advanceActions(e.ex, s, s);
    assert.equal(s.actionWork[0].status, 'done'); assert.equal(s.actionWork[0].result.ok, true, s.actionWork[0].result.detail);
    assert.equal(originHead(e), head);
  } finally { e.cleanup(); }
});

test('B. 승인 작업 뒤에 미등록 커밋이 섞이면 자동 push를 보류하고 원격은 바뀌지 않는다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    const s = owner(e); await integratedTaskA(e); pushGrants(e);
    const before = originHead(e), extra = extraCommit(e);
    const r = await applyActions(e.ex, s, [{ id: 'p2', type: 'push_main', target: 'main', sha: extra }]);
    assert.equal(r[0].ok, false);
    assert.match(r[0].detail, /승인된 통합 이력에 없는 커밋/);
    assert.equal(originHead(e), before, '원격 불변');
    assert.equal(Object.keys(e.ex.state.pushes ?? {}).length, 0, 'push 시도 기록도 없음');
  } finally { e.cleanup(); }
});

test('B. 점검 뒤 push 직전 재검사: gate가 승인 철회를 잡으면 push하지 않고, 점검 뒤 HEAD가 바뀌어도 점검한 SHA만 올라간다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    const s = owner(e); const head = await integratedTaskA(e); const before = originHead(e);
    const grants = pushGrants(e);
    // 점검(preflight)과 잠금 사이에 승인이 철회되는 경우: 잠금 획득 시점에 철회를 끼워 넣는다.
    const acquire = e.ex.locks.acquire.bind(e.ex.locks);
    e.ex.locks.acquire = ((...a: Parameters<typeof acquire>) => { revokeApproval(e.ex, grants.id); return acquire(...a); }) as typeof acquire;
    await assert.rejects(runPush(e.ex, head, { sessionId: s.id }), /승인 범위 밖|승인 조건/);
    assert.equal(originHead(e), before, '철회 후 push하지 않음');
    e.ex.locks.acquire = acquire;
    pushGrants(e);
    const later = { sha: '' };
    e.ex.locks.acquire = ((...a: Parameters<typeof acquire>) => { later.sha = extraCommit(e); return acquire(...a); }) as typeof acquire; // 점검 뒤 HEAD 변경
    const rec = await runPush(e.ex, head, { sessionId: s.id });
    assert.equal(rec.status, 'pushed_verified');
    assert.equal(originHead(e), head, '점검한 계획의 SHA만 push');
    assert.notEqual(originHead(e), later.sha);
  } finally { e.cleanup(); }
});

test('B. 승인 철회·push 결과 불명 뒤에는 재수행하지 않는다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    const s = owner(e); const head = await integratedTaskA(e); const before = originHead(e);
    const approval = pushGrants(e);
    revokeApproval(e.ex, approval.id);
    const r1 = await applyActions(e.ex, s, [{ id: 'p3', type: 'push_main', target: 'main', sha: head }]);
    assert.equal(r1[0].ok, false); assert.match(r1[0].detail, /승인 범위 밖|승인 조건/);
    pushGrants(e);
    (e.ex.state.pushes ??= {})['unk'] = { id: 'unk-0000-0000', at: new Date().toISOString(), kind: 'push', remote: 'origin', remoteUrl: '', branch: 'main', preRemoteHead: before, pushedSha: head, commits: [], tasks: ['task-a'], command: [], status: 'push_unverified', detail: '합성: 결과 불명' };
    const r2 = await applyActions(e.ex, s, [{ id: 'p4', type: 'push_main', target: 'main', sha: head }]);
    assert.equal(r2[0].ok, false); assert.match(r2[0].detail, /push 결과 불명/);
    assert.equal(originHead(e), before);
  } finally { e.cleanup(); }
});

// ---------- C. 조건 미확정 시 자동 검사·모델 턴 보류 ----------
async function unverifiedResult(e: Env, name = 'task-a', dir = 'src_a') {
  await assign(e.ex, task(e, name, { mode: 'manual', allowedFiles: [`${dir}/`] }));
  await startTask(name);
  const wt = e.fixture.worktrees[name].path;
  fs.appendFileSync(path.join(wt, dir, 'work.txt'), 'change\n');
  git(wt, 'add', '--', `${dir}/work.txt`); git(wt, 'commit', '-qm', `feat: ${name}`);
  await finishManual(e.ex, name);
  await waitFor(() => e.ex.task(name).status === 'review_pending', `${name} review`);
}
const tickUntil = async (e: Env, cond: () => unknown, label: string) => waitFor(async () => { await pipelineTick(e.ex); return cond(); }, label, 30_000);

test('C. 자유 문장 조건뿐인 승인: 사람 판단 전 검사·인계·모델 턴이 모두 0회다', { timeout: 60_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex'); await unverifiedResult(e);
    const checks = countChecks(e), launches = stubLaunch(e);
    grantApproval(e.ex, { basis: '합성: 조건부', actions: ['prepare_checks', 'confirm_handoff', 'approve_task', 'integrate_task'], targets: '*', conditions: '사용자가 확인하기 전에는 자동 처리 금지' });
    for (let i = 0; i < 4; i++) { await pipelineTick(e.ex); await sleep(150); }
    assert.equal(checks.length, 0); assert.equal(launches.length, 0);
    assert.equal(e.ex.task('task-a').verification ?? null, null); assert.equal(e.ex.task('task-a').handoff ?? null, null);
    assert.equal(Object.keys(pipe(e.ex).steps).length, 0);
    assert.ok(Object.values(pipe(e.ex).events).every((ev) => ev.state === 'held' && /조건/.test(ev.reason ?? '')), '보류 사유에 조건 미확정이 남음');
  } finally { e.cleanup(); }
});

test('C. approve_task 조건부 승인은 준비 권한을 주지 않는다: prepare_checks를 따로 기록해야 검사·인계가 한 번 수행되고, 모델 턴은 다음 행동 승인이 열렸을 때만 시작한다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex'); await unverifiedResult(e);
    const checks = countChecks(e), launches = stubLaunch(e);
    grantApproval(e.ex, { basis: '합성: handoffConfirmed 조건부 승인', actions: ['approve_task'], targets: '*', requires: { handoffConfirmed: true } });
    for (let i = 0; i < 3; i++) { await pipelineTick(e.ex); await sleep(100); }
    assert.equal(checks.length, 0, 'approve_task 승인은 검사 권한이 아님'); assert.equal(launches.length, 0);
    grantApproval(e.ex, { basis: '합성: 준비 권한(검사·인계 문서)만', actions: ['prepare_checks'], targets: '*' });
    await tickUntil(e, () => e.ex.task('task-a').handoff && !e.ex.task('task-a').handoff!.cancelledAt, '인계 문서 생성');
    for (let i = 0; i < 3; i++) { await pipelineTick(e.ex); await sleep(100); }
    assert.equal(checks.length, 1, '검사는 한 번'); assert.equal(launches.length, 0, '확인(confirm_handoff) 승인이 없으면 모델 턴 없음');
    assert.ok(Object.values(pipe(e.ex).events).some((ev) => ev.state === 'held' && /confirm_handoff/.test(ev.reason ?? '')));
    confirmHandoff(e.ex, 'task-a', '사용자가 직접 확인(합성)'); // 사람이 확인하면 다음 행동은 approve_task → 이미 열린 승인
    await tickUntil(e, () => launches.length === 1, '모델 턴 시작');
    for (let i = 0; i < 3; i++) { await pipelineTick(e.ex); await sleep(100); }
    assert.equal(launches.length, 1, '턴은 한 번');
  } finally { e.cleanup(); }
});

test('C. 열린 confirm_handoff 승인이면 검사→인계→모델 턴이 필요한 단계만 한 번씩 수행된다. prepare_checks는 모델 행동 목록에 들어가지 않는다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex'); await unverifiedResult(e);
    const checks = countChecks(e), launches = stubLaunch(e);
    grantApproval(e.ex, { basis: '합성: 확인·준비 권한', actions: ['confirm_handoff', 'prepare_checks'], targets: ['task-a'] });
    await tickUntil(e, () => launches.length === 1, '모델 턴 시작');
    for (let i = 0; i < 3; i++) { await pipelineTick(e.ex); await sleep(100); }
    assert.equal(checks.length, 1); assert.equal(launches.length, 1);
    const turn = Object.values(pipe(e.ex).turns)[0];
    const req = fs.readFileSync(path.join(e.cfg.stateDir, 'main-sessions', turn.id, 'TURN_REQUEST.md'), 'utf8');
    assert.match(req, /승인된 행동 종류: confirm_handoff\./);
    assert.ok(!req.includes('prepare_checks'));
    const res = await applyActions(e.ex, e.ex.runtime.session!, [{ id: 'bad-prep', type: 'prepare_checks', taskId: 'task-a' }]);
    assert.equal(res[0].ok, false, '모델이 준비 권한을 행동으로 쓸 수 없음');
  } finally { e.cleanup(); }
});

// ---------- D. selfReview 승인 선택 ----------
async function selfSetup(e: Env, mainAgent: 'claude' | 'codex') {
  const s = owner(e, mainAgent);
  await unverifiedResult(e); await verify(e, 'task-a'); await handoffToMain(e.ex, 'task-a'); // task-a 구현 담당 = claude
  const t = e.ex.task('task-a'), sha = t.result!.headSha!;
  const diff = git(t.worktree, 'diff', '--binary', t.baseSha, sha);
  return { s, sha, act: (id: string) => ({ id, type: 'confirm_handoff', taskId: 'task-a', sha, reviewedFiles: t.result!.changedFiles, note: '합성 검토 메모', diffHash: crypto.createHash('sha256').update(diff + '\n').digest('hex') }) };
}
const diffOk = (e: Env) => { const t = e.ex.task('task-a'); return crypto.createHash('sha256').update(execFileSync('git', ['diff', '--binary', t.baseSha, t.result!.headSha!], { cwd: t.worktree })).digest('hex'); };

test('D. 일반 승인이 먼저 기록돼도 명시적 selfReview 승인이 선택된다. 일반 승인만으로는 자기 확인 불가', { timeout: 90_000 }, async () => {
  for (const order of ['generic-first', 'self-first'] as const) {
    const e = setup();
    try {
      const { s, act } = await selfSetup(e, 'claude');
      const g = () => grantApproval(e.ex, { basis: '합성: 일반 확인', actions: ['confirm_handoff'], targets: ['task-a'] });
      const sr = () => grantApproval(e.ex, { basis: '합성: 사용자가 자기 확인을 명시 허용', actions: ['confirm_handoff'], targets: ['task-a'], requires: { selfReview: true } });
      const a = (id: string) => ({ ...act(id), diffHash: diffOk(e) });
      g();
      const denied = await applyActions(e.ex, s, [a('d0')]);
      assert.equal(denied[0].ok, false, '일반 승인만으로는 자기 확인 불가'); assert.match(denied[0].detail, /독립 확인이 아님.*selfReview/);
      if (order === 'generic-first') sr(); else { revokeApproval(e.ex, e.ex.runtime.approvals[0].id); sr(); g(); }
      const ok = await applyActions(e.ex, s, [a('d1')]);
      assert.equal(ok[0].ok, true, ok[0].detail); assert.match(ok[0].detail, /자기 확인.*독립 검토 아님/, '독립 검토와 구별해 표시');
      assert.match(e.ex.task('task-a').handoff!.note!, /^\[자기 확인 — 독립 확인 아님\]/);
    } finally { e.cleanup(); }
  }
});

test('D. selfReview 승인 철회·자유 문장 조건이 있으면 거부하고, 독립 확인(구현≠메인)은 일반 승인으로 계속 가능하다', { timeout: 90_000 }, async () => {
  const e = setup();
  try {
    const { s, act } = await selfSetup(e, 'claude');
    const a = (id: string) => ({ ...act(id), diffHash: diffOk(e) });
    grantApproval(e.ex, { basis: '합성: 일반 확인', actions: ['confirm_handoff'], targets: ['task-a'] });
    const sr = grantApproval(e.ex, { basis: '합성: selfReview', actions: ['confirm_handoff'], targets: ['task-a'], requires: { selfReview: true } });
    revokeApproval(e.ex, sr.id);
    assert.equal((await applyActions(e.ex, s, [a('r1')]))[0].ok, false, '철회된 selfReview는 쓰지 못함');
    grantApproval(e.ex, { basis: '합성: 조건부 selfReview', actions: ['confirm_handoff'], targets: ['task-a'], requires: { selfReview: true }, conditions: '구두 확인 후에만' });
    const r = await applyActions(e.ex, s, [a('r2')]);
    assert.equal(r[0].ok, false); assert.match(r[0].detail, /검증할 수 없는 조건|독립 확인이 아님/);
    assert.equal(e.ex.task('task-a').handoff?.confirmedAt, undefined);
  } finally { e.cleanup(); }
  const ind = setup();
  try {
    const { s, act } = await selfSetup(ind, 'codex'); // 구현 claude, 메인 codex → 독립
    grantApproval(ind.ex, { basis: '합성: 일반 확인', actions: ['confirm_handoff'], targets: ['task-a'] });
    const r = await applyActions(ind.ex, s, [{ ...act('i1'), diffHash: diffOk(ind) }]);
    assert.equal(r[0].ok, true, r[0].detail); assert.ok(!/자기 확인/.test(r[0].detail));
    assert.doesNotThrow(() => authorize(ind.ex, s.id, 'confirm_handoff', 'task-a'));
  } finally { ind.cleanup(); }
});

// ---------- G. executor 정지 가드·spawn 오류 ----------
test('G. stop() 뒤 연속 처리는 새 검사·모델 턴을 시작하지 않는다', { timeout: 60_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex'); await unverifiedResult(e);
    const checks = countChecks(e), launches = stubLaunch(e);
    grantApproval(e.ex, { basis: '합성: 열린 승인', actions: ['prepare_checks', 'confirm_handoff'], targets: '*' });
    e.ex.stop();
    for (let i = 0; i < 3; i++) { await pipelineTick(e.ex); await sleep(100); }
    assert.equal(checks.length, 0); assert.equal(launches.length, 0);
  } finally { e.cleanup(); }
});

test('G. 감독 프로세스 시작 실패는 예외를 던지고 프로세스 전체 예외로 번지지 않으며 감사 기록에 실행 ID가 남는다', { timeout: 30_000 }, async () => {
  const e = setup();
  try {
    assert.throws(() => spawnSupervised(e.ex, { taskId: 'x', agent: 'claude', mode: 'mock' }, { kind: 'agent', runId: 'r', cwd: path.join(e.dir, 'no-such-dir'), command: process.execPath, args: [], env: {}, display: [] }), /감독 프로세스 시작 실패/);
    const log = path.join(e.cfg.stateDir, 'events.jsonl');
    const row = await waitFor(() => (fs.existsSync(log) ? fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map((l) => JSON.parse(l)).find((x) => x.type === 'supervisor_spawn_error') : null), 'spawn 오류 감사 기록');
    assert.ok(row.execId, '실행 ID가 기록됨(undefined 아님)');
  } finally { e.cleanup(); }
});

// ---------- 재시작 정책: 결과 불명 보존 vs 검증 가능한 저장 응답의 최초 적용 ----------
test('재시작: 적용 중(applying)이던 턴은 다시 적용하지 않고 결과 불명으로 보존한다', { timeout: 60_000 }, async () => {
  const e = setup();
  try {
    owner(e, 'codex'); await unverifiedResult(e);
    grantApproval(e.ex, { basis: '합성: 열린 승인', actions: ['confirm_handoff'], targets: '*' });
    const launches = stubLaunch(e);
    pipe(e.ex).turns['old'] = { id: 'old', sessionId: 'owner-sess', generation: 1, agent: 'codex', status: 'applying', eventKeys: ['k'], startedAt: new Date().toISOString(), lifetime: 'previous-server', execId: 'gone', tokenHash: '', checkpointFile: '', checkpointHash: '', actionResults: [] };
    pipe(e.ex).events['k'] = { key: 'k', kind: 'result_ready', taskId: 'task-a', sha: 'x', at: new Date().toISOString(), state: 'launched', tried: [1] };
    await pipelineTick(e.ex);
    assert.equal(pipe(e.ex).turns['old'].status, 'unknown'); assert.equal(pipe(e.ex).events['k'].state, 'unknown');
    assert.equal(pipe(e.ex).turns['old'].actionResults.length, 0, '다시 적용하지 않음');
    assert.equal(launches.length, 0, '결과 불명 턴이 있어도 같은 요청을 다시 보내지 않음');
  } finally { e.cleanup(); }
});

// ---------- F. 구조 기준 ----------
test('F. 이번 재설계 파일은 익명 콜백 포함 함수 정의 7개 이하(전체 저장소 점검은 structure-trace 보고서·구조 준수 작업이 관리)', () => {
  const root = path.resolve(import.meta.dirname, '..');
  const out = JSON.parse(execFileSync(process.execPath, [path.join(root, 'scripts/structure-trace.mjs')], { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString()).perFile as Record<string, number>;
  const files = ['limitScope', 'approvalGate', 'approvalScope', 'actionPlan', 'pipelineEnd', 'pushOwnership', 'mainAck', 'checkpointBuild', 'mainApprovals', 'actionState', 'mainCheckpoint', 'mainHandover', 'mainSessionLaunch', 'mainDispatch', 'mainEnd', 'mainSerial', 'pipelineEvents', 'pipelineSteps', 'pipelineTick', 'pipelineTurn', 'pipelineView', 'pipelineApply', 'turnBundle', 'mainTakeover', 'mainGuard', 'mainOutcome'].map((f) => `src/executor/${f}.ts`).concat(['src/ui/js/view-pipeline.js']);
  assert.deepEqual(files.filter((f) => !(out[f] <= 7)).map((f) => `${f}:${out[f]}`), []);
});

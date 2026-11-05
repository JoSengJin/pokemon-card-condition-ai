import { getTask } from '../src/executor/executorLookup.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
import { finishManual } from '../src/executor/taskManual.ts';
// 푸시·되돌림 절차. 원격은 로컬 bare 저장소(합성)뿐이며 실제 GitHub에는 연결하지 않는다.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { acknowledgeFindings, prepareRevert, preflight, pushState, runPush, verifyPush } from '../src/executor/push.ts';
import { resumeStep, startTask } from '../src/runtime.ts';
import { setup, task, verify, waitFor, type Env } from './helpers.ts';

const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd, stdio: 'pipe' }).toString().trim();
const originHead = (env: Env) => git(env.fixture.origin, 'rev-parse', 'refs/heads/main');
const fakeKey = () => ['sk', 'live', 'a1b2c3d4e5f6g7h8i9j0k1l2'].join('-'); // 리터럴로 두지 않아 이 저장소의 푸시 점검에 걸리지 않는다

/** 수동 모드 작업 하나를 승인·통합까지 진행한다(에이전트 세션은 직접 커밋으로 흉내낸다). */
async function integrate(env: Env, name: string, file: string, extra: Record<string, unknown> = {}) {
  await assign(env.ex, task(env, name, { mode: 'manual', allowedFiles: [path.dirname(file) + '/'], ...extra }));
  await startTask(name);
  const wt = env.fixture.worktrees[name].path;
  fs.mkdirSync(path.dirname(path.join(wt, file)), { recursive: true });
  fs.appendFileSync(path.join(wt, file), `${name} change\n`);
  git(wt, 'add', '--', file); git(wt, 'commit', '-qm', `feat: ${name}`);
  await finishManual(env.ex, name);
  await waitFor(() => getTask(env.ex, name).status === 'review_pending', `${name} review`);
  await verify(env, name);
  const t = getTask(env.ex, name);
  const a = await approve(env.ex, name, t.result!.headSha!);
  await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
  await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
  return getTask(env.ex, name);
}
const otherClonePush = (env: Env, file = 'other.txt') => {
  const dir = path.join(env.dir, `clone-${Math.random().toString(36).slice(2)}`);
  execFileSync('git', ['clone', '-q', env.fixture.origin, dir], { stdio: 'pipe' });
  fs.writeFileSync(path.join(dir, file), 'other\n');
  git(dir, 'add', '--', file); git(dir, 'commit', '-qm', 'other work'); git(dir, 'push', '-q', 'origin', 'main');
  return git(dir, 'rev-parse', 'HEAD');
};

test('정상 푸시: 점검 → 틀린 확인 입력 거절 → 앞 12자 입력 → 일반 push → 원격 SHA 사후 확인 → 기록', async () => {
  const env = setup();
  try {
    const before = originHead(env);
    const t = await integrate(env, 'task-a', 'src_a/work.txt');
    assert.equal(t.status, 'integrated', t.statusReason ?? '');
    const plan = await preflight(env.ex);
    assert.deepEqual(plan.blockers, [], plan.blockers.join(' / '));
    assert.equal(plan.remoteHead, before);
    assert.equal(plan.commits.length, 2, '계약 커밋 + 변경 커밋');
    assert.ok(plan.commits.every((c) => /^[0-9a-f]{40}$/.test(c.sha) && c.subject));
    assert.deepEqual(plan.tasks, ['task-a']);
    assert.ok(plan.files.includes('src_a/work.txt') && plan.files.includes(t.contractPath));
    assert.equal(plan.dryRun?.ok, true);
    assert.ok(!plan.remoteUrl.includes('@'), '원격 주소의 자격 정보는 표시하지 않음');
    assert.equal(originHead(env), before, '점검은 원격을 바꾸지 않음');

    await assert.rejects(runPush(env.ex, 'abc'), /앞 12자와 다름/);
    await assert.rejects(runPush(env.ex, '0'.repeat(12)), /앞 12자와 다름/);
    assert.equal(originHead(env), before);
    const rec = await runPush(env.ex, plan.localHead.slice(0, 12));
    assert.equal(rec.status, 'pushed_verified', rec.detail);
    assert.equal(originHead(env), plan.localHead);
    assert.equal(rec.preRemoteHead, before);
    assert.deepEqual(rec.tasks, ['task-a']);
    assert.ok(!rec.command.some((a) => /force|^\+|-f$/.test(a)), 'force 없음');
    assert.equal(rec.command.at(-1), `${plan.localHead}:refs/heads/main`, '브랜치 이름이 아니라 확인한 SHA를 지정해 푸시');
    assert.equal(git(env.fixture.origin, 'merge-base', '--is-ancestor', before, plan.localHead) ?? '', '', '이전 원격 이력은 보존');
    assert.ok((await preflight(env.ex)).blockers.some((b) => /푸시할 커밋이 없음/.test(b)));
    assert.equal(pushState(env.ex).records.length, 1);
  } finally { env.cleanup(); }
});

test('점검에서 막는 경우: 원격이 앞섬·금지 경로·비밀 패턴·큰 파일·미커밋·원격 없음 — 원격은 그대로', async () => {
  const env = setup();
  try {
    const cwd = env.fixture.repo;
    await integrate(env, 'task-a', 'src_a/work.txt');
    // 비밀값 의심: 값은 계획·기록 어디에도 나오지 않는다
    fs.writeFileSync(path.join(cwd, 'src_a', 'config.txt'), `TOKEN=${fakeKey()}\n`);
    git(cwd, 'add', '--', 'src_a/config.txt'); git(cwd, 'commit', '-qm', 'add config');
    // 금지 경로, 큰 파일
    fs.mkdirSync(path.join(cwd, 'data'), { recursive: true });
    fs.writeFileSync(path.join(cwd, 'data', 'labels.jsonl'), '{}\n');
    fs.writeFileSync(path.join(cwd, 'big.bin'), Buffer.alloc(5_100_000, 1));
    git(cwd, 'add', '-f', '--', 'data/labels.jsonl', 'big.bin'); git(cwd, 'commit', '-qm', 'add data and big file');
    // 미커밋
    fs.writeFileSync(path.join(cwd, 'wip.txt'), 'wip');
    const before = originHead(env);
    const plan = await preflight(env.ex);
    const text = plan.blockers.join('\n');
    assert.match(text, /금지 경로: data\/labels\.jsonl/);
    assert.match(text, /비밀값 의심: src_a\/config\.txt:1/);
    assert.match(text, /큰 파일: big\.bin/);
    assert.match(text, /미커밋 변경이 있음: wip\.txt/);
    assert.ok(!JSON.stringify(plan).includes(fakeKey()), '비밀값은 어디에도 나오지 않음');
    assert.equal(plan.dryRun, null, '막힘이 있으면 dry-run까지 가지 않음');
    await assert.rejects(runPush(env.ex, plan.localHead.slice(0, 12)), /푸시할 수 없음/);
    assert.equal(originHead(env), before);

    // 원격이 앞선 경우
    const other = otherClonePush(env);
    fs.rmSync(path.join(cwd, 'wip.txt'));
    const p2 = await preflight(env.ex);
    assert.ok(p2.blockers.some((b) => /fast-forward 불가/.test(b)));
    assert.equal(originHead(env), other, '원격은 다른 사람의 커밋 그대로(덮어쓰지 않음)');
    // 원격 없음
    git(cwd, 'remote', 'remove', 'origin');
    assert.ok((await preflight(env.ex)).blockers.some((b) => /설정되어 있지 않음/.test(b)));
    git(cwd, 'remote', 'add', 'origin', path.join(env.dir, 'no-such-remote.git'));
    assert.ok((await preflight(env.ex)).blockers.some((b) => /원격 fetch 실패/.test(b)));
  } finally { env.cleanup(); }
});

test('통합 후 검사 실패 작업이 범위에 있으면 푸시 막음, 통합 후 검사 미지정은 경고', async () => {
  const env = setup();
  try {
    const failing = [{ id: 'post', name: '실패', executable: 'node', args: ['-e', 'process.exit(2)'] }];
    const a = await integrate(env, 'task-a', 'src_a/work.txt', { postChecks: failing });
    assert.equal(a.status, 'integrated_check_failed');
    const plan = await preflight(env.ex);
    assert.ok(plan.blockers.some((b) => /task-a: 통합 후 검사 실패 상태/.test(b)), plan.blockers.join(' / '));
    const env2 = setup();
    try {
      await integrate(env2, 'task-b', 'src_b/work.txt');
      const p = await preflight(env2.ex);
      assert.deepEqual(p.blockers, []);
      assert.ok(p.warnings.some((w) => /통합 후 검사가 지정되지 않아 미실행/.test(w)));
    } finally { env2.cleanup(); }
  } finally { env.cleanup(); }
});

test('확인 입력 이후 로컬이 바뀌면 거절, 다른 푸시·통합이 진행 중이면 거절, 원격이 거절하면 push_failed로 기록하고 재시도하지 않음', async () => {
  const env = setup();
  try {
    const cwd = env.fixture.repo;
    await integrate(env, 'task-a', 'src_a/work.txt');
    const plan = await preflight(env.ex);
    fs.writeFileSync(path.join(cwd, 'src_a', 'later.txt'), 'later\n');
    git(cwd, 'add', '--', 'src_a/later.txt'); git(cwd, 'commit', '-qm', 'later');
    await assert.rejects(runPush(env.ex, plan.localHead.slice(0, 12)), /앞 12자와 다름/);

    const p2 = await preflight(env.ex);
    assert.ok(env.ex.locks.acquire('integration', { owner: 'other' }));
    await assert.rejects(runPush(env.ex, p2.localHead.slice(0, 12)), /진행 중/);
    env.ex.locks.release('integration', 'owner', 'other');

    // 원격 pre-receive 훅이 거절 → push_failed, 원격 불변, 자동 재시도 없음
    const hook = path.join(env.fixture.origin, 'hooks', 'pre-receive');
    fs.writeFileSync(hook, '#!/bin/sh\necho "rejected by policy" >&2\nexit 1\n', { mode: 0o755 });
    const before = originHead(env);
    const rec = await runPush(env.ex, p2.localHead.slice(0, 12));
    assert.equal(rec.status, 'push_failed');
    assert.match(rec.detail, /rejected by policy/);
    assert.equal(originHead(env), before);
    assert.equal(pushState(env.ex).records.length, 1, '자동 재시도 없음');
    await assert.rejects(prepareRevert(env.ex, rec.id), /확인된 푸시만 되돌릴 수 있음/);
  } finally { env.cleanup(); }
});

test('되돌림: revert 커밋 생성(로컬) → 트리 복원 확인 → 같은 푸시 절차로 올림, 원격 이력 보존·force 없음', async () => {
  const env = setup();
  try {
    const cwd = env.fixture.repo;
    await integrate(env, 'task-a', 'src_a/work.txt');
    await integrate(env, 'task-b', 'src_b/work.txt');
    const pre = originHead(env);
    const pushed = await runPush(env.ex, (await preflight(env.ex)).localHead.slice(0, 12));
    assert.equal(pushed.status, 'pushed_verified');
    assert.equal(pushed.commits.length, 4);

    const rv = await prepareRevert(env.ex, pushed.id);
    assert.equal(rv.treeRestored, true, '되돌린 트리가 푸시 전 트리와 같음');
    assert.equal(rv.commits.length, 4, '커밋마다 되돌림 커밋 1개');
    assert.equal(originHead(env), pushed.pushedSha, '되돌림 준비는 원격을 바꾸지 않음');
    assert.equal(git(cwd, 'rev-parse', 'HEAD'), rv.newHead);
    assert.equal(git(cwd, 'status', '--porcelain'), '');
    await assert.rejects(prepareRevert(env.ex, pushed.id), /이미 되돌림을 준비함/);

    const plan = await preflight(env.ex);
    assert.deepEqual(plan.blockers, [], plan.blockers.join(' / '));
    assert.equal(plan.revertOf, pushed.id);
    const rec = await runPush(env.ex, plan.localHead.slice(0, 12));
    assert.equal(rec.kind, 'revert');
    assert.equal(rec.status, 'pushed_verified');
    assert.equal(rec.revertOf, pushed.id);
    assert.equal(env.ex.state.pushes![pushed.id].revert!.pushedAs, rec.id);
    assert.equal(git(env.fixture.origin, 'diff', '--quiet', pre, 'refs/heads/main') ?? '', '', '원격 트리가 푸시 전과 같음');
    git(env.fixture.origin, 'merge-base', '--is-ancestor', pushed.pushedSha, 'refs/heads/main'); // 원래 푸시한 커밋이 이력에 그대로 있음
    await assert.rejects(prepareRevert(env.ex, rec.id), /다시 되돌리지 않음/);
  } finally { env.cleanup(); }
});

test('되돌림 거절: 로컬이 앞섬·원격이 앞섬·./develop 잠금 사용 중·.venv 없음 — 상태를 바꾸지 않음', async () => {
  const env = setup();
  try {
    const cwd = env.fixture.repo;
    await integrate(env, 'task-a', 'src_a/work.txt');
    const rec = await runPush(env.ex, (await preflight(env.ex)).localHead.slice(0, 12));
    const head = git(cwd, 'rev-parse', 'HEAD');

    // 잠금 사용 중
    const { spawn } = await import('node:child_process');
    const holder = spawn(path.join(cwd, 'develop'), ['--', 'sleep', '3'], { cwd, stdio: 'ignore' });
    await new Promise((r) => setTimeout(r, 700));
    await assert.rejects(prepareRevert(env.ex, rec.id), /잠금 사용 중|다른 통합·푸시/);
    await new Promise((r) => holder.on('exit', r));
    assert.equal(git(cwd, 'rev-parse', 'HEAD'), head);
    assert.equal(env.ex.state.pushes![rec.id].revert ?? null, null);

    // .venv 없음
    fs.renameSync(path.join(cwd, '.venv'), path.join(env.dir, 'moved-venv'));
    await assert.rejects(prepareRevert(env.ex, rec.id), /실행 환경 미준비/);
    fs.renameSync(path.join(env.dir, 'moved-venv'), path.join(cwd, '.venv'));

    // 원격이 앞섬
    const other = otherClonePush(env);
    await assert.rejects(prepareRevert(env.ex, rec.id), /원격이 푸시한 SHA와 다름/);
    assert.equal(originHead(env), other);
    git(cwd, 'fetch', '-q', 'origin');
    // 재시작 후 사후 확인: 대상 SHA가 이력에 포함되면 확인됨
    const env2 = env.restart();
    const v = await verifyPush(env2.ex, rec.id);
    assert.equal(v.status, 'pushed_verified');
    assert.match(v.detail, /이력에 포함/);
    // 로컬이 앞섬
    fs.writeFileSync(path.join(cwd, 'src_a', 'later.txt'), 'x');
    git(cwd, 'add', '--', 'src_a/later.txt'); git(cwd, 'commit', '-qm', 'later');
    await assert.rejects(prepareRevert(env2.ex, rec.id), /로컬이 푸시한 SHA와 다름/);
  } finally { env.cleanup(); }
});

test('이력 점검: 중간 커밋에 들어갔다 지워진 비밀값·금지 파일도 막고, 오탐 확인은 그 항목에만 적용', async () => {
  const env = setup();
  try {
    const cwd = env.fixture.repo;
    await integrate(env, 'task-a', 'src_a/work.txt');
    // 커밋 1: 비밀값 모양과 금지 파일 추가 → 커밋 2: 둘 다 삭제(최종 diff에는 없음)
    fs.writeFileSync(path.join(cwd, 'src_a', 'cfg.txt'), `K=${fakeKey()}\n`);
    fs.mkdirSync(path.join(cwd, 'data'), { recursive: true });
    fs.writeFileSync(path.join(cwd, 'data', 'labels.jsonl'), '{}\n');
    git(cwd, 'add', '-f', '--', 'src_a/cfg.txt', 'data/labels.jsonl'); git(cwd, 'commit', '-qm', 'oops add');
    const bad = git(cwd, 'rev-parse', 'HEAD');
    git(cwd, 'rm', '-q', '--', 'src_a/cfg.txt', 'data/labels.jsonl'); git(cwd, 'commit', '-qm', 'remove them');
    assert.ok(!(await preflight(env.ex)).files.includes('src_a/cfg.txt'), '최종 diff에는 파일이 없음');
    const plan = await preflight(env.ex);
    const text = plan.blockers.join('\n');
    assert.match(text, new RegExp(`비밀값 의심: src_a/cfg\\.txt:1 \\(커밋 ${bad.slice(0, 8)}\\)`), '이력에 남은 비밀값 의심을 커밋과 함께 표시');
    assert.match(text, /금지 경로: data\/labels\.jsonl/);
    assert.ok(!JSON.stringify(plan).includes(fakeKey()));
    const secret = plan.findings.find((f) => f.kind === 'secret_pattern')!;
    assert.ok(secret.fingerprint);
    assert.throws(() => acknowledgeFindings(env.ex, []), /확인할 수 있는 비밀 패턴 항목이 없음/);
    assert.throws(() => acknowledgeFindings(env.ex, [plan.findings.find((f) => f.kind === 'forbidden_path')!.commit!]), /확인할 수 있는/, '금지 경로는 확인으로 넘길 수 없음');

    // 오탐 확인 후에도 금지 경로는 계속 막힘, 비밀 항목은 경고로 바뀜
    acknowledgeFindings(env.ex, [secret.fingerprint!]);
    const p2 = await preflight(env.ex);
    assert.ok(!p2.blockers.some((b) => /비밀값 의심/.test(b)));
    assert.ok(p2.warnings.some((w) => /확인된 오탐: src_a\/cfg\.txt:1/.test(w)));
    assert.ok(p2.blockers.some((b) => /금지 경로/.test(b)));
    // 다른 위치의 새 비밀값은 다시 막힘
    fs.writeFileSync(path.join(cwd, 'src_a', 'cfg2.txt'), `K=${fakeKey()}\n`);
    git(cwd, 'add', '--', 'src_a/cfg2.txt'); git(cwd, 'commit', '-qm', 'another');
    assert.ok((await preflight(env.ex)).blockers.some((b) => /비밀값 의심: src_a\/cfg2\.txt:1/.test(b)));
    // 기록에 남음
    assert.equal(Object.keys(env.ex.state.pushAllow ?? {}).length, 1);
  } finally { env.cleanup(); }
});

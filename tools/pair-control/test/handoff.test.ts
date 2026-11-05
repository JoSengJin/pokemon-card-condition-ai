import { getTask } from '../src/executor/executorLookup.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { approve } from '../src/executor/taskApproval.ts';
import { recollect } from '../src/executor/taskCollect.ts';
import { finishManual } from '../src/executor/taskManual.ts';
import { handoffToMain } from '../src/executor/handoffCreate.ts';
import { startPrompt } from '../src/executor/executorPrompt.ts';
import { readHandoff, confirmHandoff, cancelHandoff } from '../src/executor/handoffRecords.ts';
import { turnOf } from '../src/executor/executorView.ts';
// 메인 에이전트 인계: 누구 차례 상태, 인계 문서(커밋하지 않음), 확인·취소, SHA 변경 시 낡은 인계.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { resumeStep, startTask } from '../src/runtime.ts';
import { setup, task, verify, waitFor, type Env } from './helpers.ts';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=session', '-c', 'user.email=s@l', ...a], { cwd }).toString().trim();
const commit = (env: Env, name: string, file: string) => {
  const wt = env.fixture.worktrees[name].path;
  fs.mkdirSync(path.dirname(path.join(wt, file)), { recursive: true });
  fs.appendFileSync(path.join(wt, file), 'change\n');
  gitOut(wt, 'add', '--', file); gitOut(wt, 'commit', '-qm', `feat: ${file}`);
  return gitOut(wt, 'rev-parse', 'HEAD');
};
async function manualDone(env: Env, name: string, file = 'src_a/work.txt', extra: Record<string, unknown> = {}) {
  await assign(env.ex, task(env, name, { mode: 'manual', ...extra }));
  await startTask(name);
  const sha = file ? commit(env, name, file) : null;
  await finishManual(env.ex, name);
  await waitFor(() => getTask(env.ex, name).status === 'review_pending', `${name} review`);
  return sha;
}
const turn = (env: Env, id: string) => turnOf(getTask(env.ex, id));

test('누구 차례: 배정 → 에이전트 작업 → 사용자(검사·인계) → 메인 확인 중 → 사용자(승인) → 통합', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { mode: 'manual' }));
    assert.equal(turn(env, 'task-a').who, 'user');
    await startTask('task-a');
    assert.deepEqual([turn(env, 'task-a').who, turn(env, 'task-a').agent], ['implementer', 'claude']);
    const sha = commit(env, 'task-a', 'src_a/work.txt');
    await finishManual(env.ex, 'task-a');
    await waitFor(() => getTask(env.ex, 'task-a').status === 'review_pending', 'review');
    assert.match(turn(env, 'task-a').next, /메인에게 인계/);
    await verify(env, 'task-a');

    const h = await handoffToMain(env.ex, 'task-a');
    assert.equal(h.handoff.to, 'codex');
    assert.deepEqual([turn(env, 'task-a').who, turn(env, 'task-a').agent], ['main', 'codex']);
    // 인계 문서: 전체 SHA·부모·변경 파일·검사·미검증·롤백, 상태 폴더에만 저장하고 브랜치에는 커밋하지 않음
    const wt = env.fixture.worktrees['task-a'].path;
    const t = getTask(env.ex, 'task-a');
    const parent = gitOut(wt, 'rev-parse', `${sha}^`);
    for (const needle of [`전체 SHA: \`${sha}\``, `\`${sha}\` ← \`${parent}\``, '- src_a/work.txt', 'Git 계약 검사: 통과', '작업 테스트: passed', '독립 리뷰: 미실행', '미검증·한계', './develop -- git revert', '## 메인(codex)이 할 일', wt]) {
      assert.ok(h.text.includes(needle), `없음: ${needle}`);
    }
    assert.ok(h.handoff.file.startsWith(env.cfg.stateDir), '인계 문서는 상태 폴더(Git 제외)에 저장');
    assert.equal(fs.readFileSync(h.handoff.file, 'utf8'), h.text);
    assert.equal(gitOut(wt, 'rev-parse', 'HEAD'), sha, '인계가 브랜치에 커밋을 만들지 않음');
    assert.equal(gitOut(wt, 'status', '--porcelain'), '');
    assert.ok(h.message.includes(sha) && h.message.includes(h.handoff.file));
    assert.equal(readHandoff(env.ex, 'task-a').text, h.text);

    // 메인 확인 → 사용자 차례, 승인에 기록
    confirmHandoff(env.ex, 'task-a', '계약 대조 완료');
    assert.equal(turn(env, 'task-a').who, 'user');
    assert.match(turn(env, 'task-a').next, /승인 또는 거절/);
    const a = await approve(env.ex, 'task-a', t.result!.headSha!);
    assert.ok(a.mainConfirmedAt);
    await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    assert.equal(turn(env, 'task-a').next, '통합 실행');
    await assert.rejects(async () => cancelHandoff(env.ex, 'task-a'), /승인 후에는 인계를 취소할 수 없음/);
  } finally { env.cleanup(); }
});

test('인계 거절 조건: 커밋 없음·미커밋 변경·낡은 SHA·중복, 작업 테스트 미실행은 문서에 미실행으로 표시', async () => {
  const env = setup();
  try {
    await manualDone(env, 'task-a', '');
    await assert.rejects(handoffToMain(env.ex, 'task-a'), /인계할 커밋이 없음/);

    await manualDone(env, 'task-b', 'src_b/work.txt', { allowedFiles: ['src_b/'] });
    fs.writeFileSync(path.join(env.fixture.worktrees['task-b'].path, 'src_b', 'wip.txt'), 'x');
    await assert.rejects(handoffToMain(env.ex, 'task-b'), /미커밋 변경/);
    fs.rmSync(path.join(env.fixture.worktrees['task-b'].path, 'src_b', 'wip.txt'));
    commit(env, 'task-b', 'src_b/more.txt');
    await assert.rejects(handoffToMain(env.ex, 'task-b'), /다시 수집/);
    await recollect(env.ex, 'task-b');
    const h = await handoffToMain(env.ex, 'task-b');
    assert.match(h.text, /작업 테스트: \*\*미실행 또는 이전 SHA 결과 — 통과가 아님\*\*/);
    await assert.rejects(handoffToMain(env.ex, 'task-b'), /이미 인계됨/);
    // 취소하면 사용자 차례로 돌아오고 다시 인계 가능
    cancelHandoff(env.ex, 'task-b');
    assert.equal(turn(env, 'task-b').who, 'user');
    await assert.rejects(async () => confirmHandoff(env.ex, 'task-b'), /유효한 인계가 없음/);
    await handoffToMain(env.ex, 'task-b');
    // 인계 후 코드가 바뀌면 낡은 인계: 확인 불가, 사용자가 다시 인계
    commit(env, 'task-b', 'src_b/after.txt');
    await recollect(env.ex, 'task-b');
    assert.match(turn(env, 'task-b').next, /다시 인계/);
    assert.throws(() => confirmHandoff(env.ex, 'task-b'), /코드가 바뀜/);
    await handoffToMain(env.ex, 'task-b');
    assert.equal(turn(env, 'task-b').who, 'main');
  } finally { env.cleanup(); }
});

test('메인 에이전트 기본값은 codex, 인계 대상은 인계 시점의 메인으로 기록', async () => {
  const env = setup();
  try {
    assert.equal(env.ex.mainAgent, 'codex');
    await manualDone(env, 'task-a');
    env.ex.state.main = { agent: 'claude', since: new Date().toISOString(), reason: '테스트' };
    const h = await handoffToMain(env.ex, 'task-a');
    assert.equal(h.handoff.to, 'claude');
    assert.match(h.text, /메인\(확인·통합·푸시 담당\): claude/);
    const p = await startPrompt(env.ex, 'task-a');
    assert.match(p.text, /main 통합과 push는 Claude가 담당/);
  } finally { env.cleanup(); }
});

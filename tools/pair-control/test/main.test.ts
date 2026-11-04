import { assign } from '../src/executor/taskAssign.ts';
import { finishManual } from '../src/executor/taskManual.ts';
import { handoffToMain } from '../src/executor/handoffCreate.ts';
import { startPrompt } from '../src/executor/executorPrompt.ts';
import { cancelHandoff } from '../src/executor/handoffRecords.ts';
// 메인 역할 이양: 안전 확인·기록·인계 메모. 권한을 강제하지 않는다.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { setMain, swapBlockers } from '../src/executor/mainRole.ts';
import { startTask } from '../src/runtime.ts';
import { setup, task, verify, waitFor } from './helpers.ts';

test('이양: 안전 확인 통과 시 메인 변경·이력·인계 메모, 이후 프롬프트·인계 문구에 반영, 재시작 후 유지', async () => {
  let env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { mode: 'manual' }));
    await startTask('task-a');
    assert.equal(env.ex.mainAgent, 'codex');
    assert.deepEqual(await swapBlockers(env.ex), []);
    await assert.rejects(setMain(env.ex, 'gemini', ''), /codex 또는 claude/);
    await assert.rejects(setMain(env.ex, 'codex', ''), /이미 codex이\(가\) 메인/);
    const { role, memo } = await setMain(env.ex, 'claude', 'Codex 토큰 부족');
    assert.equal(role.agent, 'claude');
    assert.equal(role.reason, 'Codex 토큰 부족');
    assert.deepEqual(role.history!.map((h) => h.agent), ['codex']);
    assert.ok(fs.existsSync(role.memoFile!) && role.memoFile!.startsWith(env.cfg.stateDir));
    for (const needle of ['메인 역할 이양: codex → claude', '사유: Codex 토큰 부족', '권한을 강제하지 않는다', '`task-a`', 'claude 세션에서 작업 중', '실행 중인 것이 없음을 도구가 확인']) assert.ok(memo.includes(needle), needle);
    assert.match((await startPrompt(env.ex, 'task-a')).text, /main 통합과 push는 Claude가 담당/);
    env = env.restart();
    assert.equal(env.ex.mainAgent, 'claude', '재시작 후에도 유지');
    await setMain(env.ex, 'codex', '복귀');
    assert.deepEqual(env.ex.state.main!.history!.map((h) => h.agent), ['codex', 'claude']);
  } finally { env.cleanup(); }
});

test('이양 거절: 프로세스 실행 중·통합 잠금·푸시 결과 불명·./develop 잠금 사용 중 — 메인은 그대로', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { mockScenario: 'hang' }));
    await startTask('task-a');
    await waitFor(() => Object.values(env.ex.state.executions).some((e) => e.status === 'running'), 'running');
    await assert.rejects(setMain(env.ex, 'claude'), /프로세스 실행 중: agent task-a/);
    await env.ex.cancel('task-a');
    await waitFor(() => env.ex.task('task-a').status === 'cancelled', 'cancelled');
    assert.deepEqual(await swapBlockers(env.ex), []);

    assert.ok(env.ex.locks.acquire('integration', { owner: 'x', kind: 'push' }));
    await assert.rejects(setMain(env.ex, 'claude'), /통합·푸시·되돌림 진행 중/);
    env.ex.locks.release('integration', 'owner', 'x');

    (env.ex.state.pushes ??= {})['p1xxxxxxxx'] = { id: 'p1xxxxxxxx', at: new Date().toISOString(), kind: 'push', remote: 'origin', remoteUrl: '', branch: 'main', preRemoteHead: 'a'.repeat(40), pushedSha: 'b'.repeat(40), commits: [], tasks: [], command: [], status: 'push_unverified', detail: '' };
    await assert.rejects(setMain(env.ex, 'claude'), /푸시 결과 불명/);
    delete env.ex.state.pushes!['p1xxxxxxxx'];

    const cwd = env.fixture.repo;
    const holder = spawn(path.join(cwd, 'develop'), ['--', 'sleep', '3'], { cwd, stdio: 'ignore' });
    await new Promise((r) => setTimeout(r, 700));
    await assert.rejects(setMain(env.ex, 'claude'), /\.\/develop 잠금이 사용 중/);
    await new Promise((r) => holder.on('exit', r));
    assert.equal(env.ex.mainAgent, 'codex');
    assert.equal(env.ex.state.main ?? null, null);
    await setMain(env.ex, 'claude', '잠금 해제 후');
    assert.equal(env.ex.mainAgent, 'claude');
  } finally { env.cleanup(); }
});

test('이양 메모: 이전 메인에게 인계되어 확인 전인 작업은 새 메인에게 다시 전달하라고 안내, 같은 에이전트가 메인이면 인계 문서에 독립 확인 아님 표시', async () => {
  const env = setup();
  try {
    await assign(env.ex, task(env, 'task-a', { mode: 'manual' }));
    await startTask('task-a');
    const wt = env.fixture.worktrees['task-a'].path;
    fs.mkdirSync(path.join(wt, 'src_a'), { recursive: true });
    fs.appendFileSync(path.join(wt, 'src_a', 'w.txt'), 'x\n');
    const { execFileSync } = await import('node:child_process');
    execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', 'add', '--', 'src_a/w.txt'], { cwd: wt });
    execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', 'commit', '-qm', 'w'], { cwd: wt });
    await finishManual(env.ex, 'task-a');
    await waitFor(() => env.ex.task('task-a').status === 'review_pending', 'review');
    await verify(env, 'task-a');
    await handoffToMain(env.ex, 'task-a');
    const { memo } = await setMain(env.ex, 'claude', '토큰');
    assert.match(memo, /`task-a`: 이전 메인\(codex\)에게 인계됨 → claude에게 인계 안내문을 다시 전달/);
    // 구현 담당(claude)이 곧 메인(claude)일 때
    cancelHandoff(env.ex, 'task-a');
    const h = await handoffToMain(env.ex, 'task-a');
    assert.match(h.text, /구현 담당과 메인이 같은 에이전트다 — 이 확인은 독립 확인이 아니다/);
  } finally { env.cleanup(); }
});

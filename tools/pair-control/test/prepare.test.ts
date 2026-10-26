// 작업 준비 자동화(prepare-task workflow) 검증. 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { planTask } from '../src/executor/prepare.ts';
import { prepareTask, startTask } from '../src/runtime.ts';
import { setup, waitFor } from './helpers.ts';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', a, { cwd }).toString().trim();

test('미리보기: 담당·목표·파일만으로 ID·브랜치·기준 SHA·worktree 계산, 부작용 없음', async () => {
  const env = setup();
  try {
    const before = gitOut(env.fixture.repo, 'worktree', 'list');
    const p = await planTask(env.ex, { agent: 'claude', goal: '연습', allowedFiles: ['src_b/'] });
    assert.ok(p.ok, JSON.stringify(p.checks));
    const t = p.task!;
    assert.match(t.taskId, /^task-\d{4}-1$/);
    assert.equal(t.branch, `claude/${t.taskId}`);
    assert.equal(t.baseSha, gitOut(env.fixture.repo, 'rev-parse', 'main'));
    assert.equal(t.worktree, path.join(env.dir, 'fx', `repo-claude-${t.taskId}`));
    assert.equal(p.createWorktree, true);
    assert.equal(fs.existsSync(t.worktree), false, '미리보기는 폴더를 만들지 않음');
    assert.equal(gitOut(env.fixture.repo, 'worktree', 'list'), before);
    const bad = await planTask(env.ex, { agent: 'codex', goal: 'x', allowedFiles: ['data/labels.jsonl'] });
    assert.equal(bad.ok, false);
    assert.ok(bad.checks.some((c) => !c.ok && /금지 경로/.test(c.detail)));
    // 비우면 실패가 아니라 기본 범위(코드·테스트·문서)가 적용된다(scope.test.ts에서 자세히 검사).
    const empty = await planTask(env.ex, { agent: 'codex', goal: 'x', allowedFiles: [] });
    assert.equal(empty.scopeDefault, true);
  } finally { env.cleanup(); }
});

test('준비하고 배정: worktree·브랜치 생성 → 등록 → 그대로 시작 가능, 기존 경로·브랜치는 덮어쓰지 않음', async () => {
  const env = setup();
  try {
    const r = await prepareTask({ agent: 'codex', goal: '연습', allowedFiles: ['src_b/'], mockScenario: 'success' });
    const t = env.ex.task(r.taskId!);
    assert.equal(t.status, 'assigned');
    assert.ok(t.preflight!.every((c) => c.ok), JSON.stringify(t.preflight));
    assert.equal(gitOut(t.worktree, 'symbolic-ref', '--short', 'HEAD'), t.branch);
    await startTask(t.taskId);
    await waitFor(() => env.ex.task(t.taskId).status === 'review_pending', 'review');

    // 같은 ID로 다시: 이미 배정·브랜치 존재 → 거절, 기존 폴더 그대로
    const marker = path.join(t.worktree, 'src_b', 'file.txt');
    const content = fs.readFileSync(marker, 'utf8');
    await assert.rejects(prepareTask({ taskId: t.taskId, agent: 'codex', goal: '다시', allowedFiles: ['src_b/'] }), /이미/);
    assert.equal(fs.readFileSync(marker, 'utf8'), content);

    // 진행 중 작업과 겹치면 배정은 경고만, 시작은 거절
    const p = await planTask(env.ex, { agent: 'claude', goal: '겹침', allowedFiles: ['src_b/file.txt'] });
    assert.ok(p.ok);
    assert.ok(p.warnings.some((w) => w.includes(t.taskId)));
  } finally { env.cleanup(); }
});

test('고급: 기존 worktree 사용 시 그 브랜치를 쓰고 새로 만들지 않음', async () => {
  const env = setup();
  try {
    const w = env.fixture.worktrees['task-a'];
    const p = await planTask(env.ex, { agent: 'claude', goal: 'x', allowedFiles: ['src_a/'], worktree: w.path, taskId: 'task-a' });
    assert.ok(p.ok, JSON.stringify(p.checks));
    assert.equal(p.createWorktree, false);
    assert.equal(p.task!.branch, 'claude/task-a');
    const main = await planTask(env.ex, { agent: 'claude', goal: 'x', allowedFiles: ['src_a/'], worktree: env.fixture.repo });
    assert.equal(main.ok, false, '기본 checkout은 거절');
  } finally { env.cleanup(); }
});

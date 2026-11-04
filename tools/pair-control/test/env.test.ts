import { assign } from '../src/executor/taskAssign.ts';
// 실행 준비 검사. 가상환경은 테스트가 "사용자 준비"로 직접 만든다(실행기는 만들지 않음).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { checkVenv } from '../src/executor/envcheck.ts';
import { setup, task } from './helpers.ts';
// @ts-ignore plain JS helper
import { makeVenv } from '../scripts/fixture-lib.mjs';

test('다른 checkout의 .venv를 symlink로 공유하면 준비 안 됨', async () => {
  const env = setup();
  try {
    const wt = env.fixture.worktrees['task-a'].path;
    fs.symlinkSync(path.join(env.fixture.repo, '.venv'), path.join(wt, '.venv'));
    const r = await checkVenv(wt, 'python');
    assert.equal(r.ready, false);
    assert.match(r.checks[0].detail, /심볼릭 링크/);
  } finally { env.cleanup(); }
});

test('python-project: card_condition import가 자기 worktree가 아니면 준비 안 됨, 필요 모듈 확인', async () => {
  const env = setup();
  try {
    const wt = env.fixture.worktrees['task-a'].path;
    makeVenv(wt);
    const r = await checkVenv(wt, 'python-project', ['json', 'surely_missing_module_x']);
    assert.equal(r.ready, false);
    assert.match(r.checks.find((c) => c.name === 'card_condition import 경로')!.detail, /설치되지 않음/, '-I로 현재 폴더 import를 배제');
    assert.equal(r.checks.find((c) => c.name === '모듈 json')!.ok, true);
    assert.equal(r.checks.find((c) => c.name === '모듈 surely_missing_module_x')!.ok, false);
    assert.ok(r.fixes.some((f) => f.includes('pip install -e .')));
    // 같은 worktree를 가리키는 .pth(editable 설치와 같은 효과)를 넣으면 통과
    const site = fs.globSync(path.join(wt, '.venv/lib/python*/site-packages'))[0];
    fs.writeFileSync(path.join(site, 'fixture.pth'), wt + '\n');
    const ok = await checkVenv(wt, 'python-project', ['json']);
    assert.equal(ok.ready, true, JSON.stringify(ok.checks));
  } finally { env.cleanup(); }
});

test('계약 env=none이고 ./develop을 쓰지 않는 작업은 .venv 없이도 준비됨', async () => {
  const env = setup();
  try {
    const t = await assign(env.ex, task(env, 'task-b', { allowedFiles: ['src_b/'] }));
    assert.equal(t.envReadiness?.needed, 'none');
    assert.equal(t.envReadiness?.ready, true);
  } finally { env.cleanup(); }
});

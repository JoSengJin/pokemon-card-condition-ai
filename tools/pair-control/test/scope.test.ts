import { effectiveGroups } from '../src/executor/contract.ts';
import { assign } from '../src/executor/taskAssign.ts';
// 허용 파일 정리 규칙·프롬프트 추출·프리셋. 모델 요청 없음.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { TaskInput, conflicts, isForbidden } from '../src/executor/contract.ts';
import { planTask } from '../src/executor/prepare.ts';
import { SCOPE_PRESET, extractScope } from '../src/executor/scope.ts';
import { setup, task } from './helpers.ts';

const input = (allowedFiles: string[]) => TaskInput.safeParse({
  taskId: 'task-s', agent: 'claude', branch: 'claude/task-s', worktree: '/tmp/wt-s', baseSha: 'a'.repeat(40), goal: 'x', allowedFiles,
});

test('정리되지 않은 허용 경로는 거부, 정상 경로는 유지', () => {
  for (const bad of ['./', '.', './docs/', './a.py', 'a//b.py', 'a/./b.py', 'docs/.']) {
    const r = input([bad]);
    assert.equal(r.success, false, `${bad} 거부`);
    assert.match(JSON.stringify(r.error?.issues), /정리되지 않은 경로|상대경로만/);
  }
  for (const ok of ['card_condition/', 'tests/test_a.py', 'docs/collaboration/tasks/x.md', 'a.py']) assert.equal(input([ok]).success, true, `${ok} 허용`);
});

test('프롬프트 추출: 목록·번호 목록·인라인·정리·제외·중복', () => {
  const list = extractScope([
    '# 작업', '작업 위치: /Users/someone/wt-1', '', '허용 파일 5개:', '- `card_condition/a.py`', '- `tests/test_a.py`', '- `./docs/x.md`', '- `card_condition/a.py`', '- `data/labels.jsonl`', '', '## 금지', '- `tools/other.py`',
  ].join('\n'));
  assert.equal(list.found, true);
  assert.deepEqual(list.files, ['card_condition/a.py', 'tests/test_a.py', 'docs/x.md'], './ 정리·중복 제거·제목 뒤 목록은 무시');
  assert.deepEqual(list.rejected.map((r) => r.path), ['data/labels.jsonl']);
  assert.match(list.rejected[0].why, /금지 경로/);

  assert.deepEqual(extractScope('allowed_files: `a/b.py`, `c/`').files, ['a/b.py', 'c/']);
  assert.deepEqual(extractScope('**허용 파일**\n1. tools/x.py (새 파일)\n2) tests/y.py').files, ['tools/x.py', 'tests/y.py'], '백틱 없는 번호 목록');
});

test('프롬프트 추출: 못 찾으면 아무것도 채우지 않고 알림, 전체·절대경로·glob은 제외', () => {
  for (const text of ['', '그냥 설명만 있는 글', '허용 파일을 알려 주세요.\n\n그 밖의 내용']) {
    const r = extractScope(text);
    assert.equal(r.found, false);
    assert.deepEqual(r.files, []);
  }
  const bad = extractScope('허용 파일:\n- `./`\n- `.`\n- `/Users/x/a.py`\n- `src/*.py`\n- `없음`');
  assert.equal(bad.found, false);
  assert.equal(bad.rejected.length, 5);
  assert.match(bad.note, /모두 제외됨/);
});

test('프리셋: 데이터·라벨·산출물·공용 설정 없음, 계약 통과', () => {
  assert.deepEqual(SCOPE_PRESET.files, ['card_condition/', 'tests/', 'tools/experiments/', 'docs/collaboration/']);
  assert.ok(SCOPE_PRESET.files.every((f) => !isForbidden(f)));
  assert.equal(input(SCOPE_PRESET.files).success, true);
});

test('작업 만들기 미리보기(planTask)와 assign(API 직접 호출) 모두 ./ 를 거부', async () => {
  const env = setup();
  try {
    const p = await planTask(env.ex, { agent: 'claude', goal: '범위 모름', allowedFiles: ['./'] });
    assert.equal(p.ok, false);
    assert.match(JSON.stringify(p.checks), /정리되지 않은 경로/);
    await assert.rejects(assign(env.ex, task(env, 'task-a', { allowedFiles: ['./'] })), /정리되지 않은 경로/);
    assert.equal(Object.keys(env.ex.state.tasks).length, 0, '거부된 작업은 등록되지 않음');
  } finally { env.cleanup(); }
});

test('허용 파일을 비우면 기본 범위 적용, 금지 경로·"./"는 직접 적어도 여전히 거부, 같은 기본 범위끼리는 겹침', async () => {
  const env = setup();
  try {
    const p = await planTask(env.ex, { agent: 'claude', goal: '범위 비움', allowedFiles: [] });
    assert.equal(p.scopeDefault, true);
    assert.deepEqual(p.task!.allowedFiles, SCOPE_PRESET.files);
    assert.ok(p.checks.some((c) => c.name === '허용 파일' && c.ok && /기본 범위/.test(c.detail)));
    assert.ok(p.checks.every((c) => c.ok || /worktree|브랜치|환경/.test(c.name)), JSON.stringify(p.checks.filter((c) => !c.ok)));

    // 기본 범위끼리는 같은 폴더라 겹친다 — 병렬로 돌리려면 범위를 좁혀야 한다는 뜻이다.
    const other = { ...p.task!, taskId: 'task-other', branch: 'claude/task-other', worktree: '/tmp/wt-other' };
    assert.ok(conflicts(p.task!, other, { a: effectiveGroups(p.task!), b: effectiveGroups(other) }).some((c) => c.kind === 'files'), '기본 범위끼리 겹침');

    const own = await planTask(env.ex, { agent: 'claude', goal: '직접 적음', allowedFiles: ['src_a/'] });
    assert.equal(own.scopeDefault, false);
    assert.deepEqual(own.task!.allowedFiles, ['src_a/']);

    for (const bad of [['data/labels.jsonl'], ['./']]) {
      const r = await planTask(env.ex, { agent: 'claude', goal: 'x', allowedFiles: bad });
      assert.equal(r.ok, false, `${bad} 거부`);
      assert.equal(r.scopeDefault, false);
    }
  } finally { env.cleanup(); }
});

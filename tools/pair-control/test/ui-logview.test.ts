// 로그 창의 표시 규칙(줄 색·받은 시각·찾기·시작 전 안내). 서버·브라우저 없이 글자 규칙만 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { footText, logRows, logTarget, paintLines, statText } from '../src/ui/js/logview.js';

const row = (s: string, t = '') => ({ t, s });

test('명령·오류·경고·통과 요약만 색을 입히고 나머지는 그대로, 받은 시각은 속성으로, HTML은 이스케이프', () => {
  const html = paintLines([
    row('$ python -m unittest tests.test_scope', '14:01:48'), row('Ran 6 tests in 0.012s', '14:01:51'), row('OK'), row('FAILED (failures=1)'), row('Traceback (most recent call last):'), row('[main 7f3a9c2] feat(scope): 범위 추출 보강'),
    row('경고: data/labels.jsonl 은 금지 경로'), row('일반 설명 줄'), row('<script>alert(1)</script> & "x"'),
  ]).split('\n');
  assert.equal(html[0], '<span class="ln" data-t="14:01:48"><span class="info">$ python -m unittest tests.test_scope</span></span>');
  assert.equal(html[1], '<span class="ln" data-t="14:01:51"><span class="ok">Ran 6 tests in 0.012s</span></span>');
  assert.equal(html[2], '<span class="ln" data-t=""><span class="ok">OK</span></span>');
  assert.match(html[3], /<span class="bad">FAILED/);
  assert.match(html[4], /<span class="bad">Traceback/);
  assert.match(html[5], /<span class="ok">\[main 7f3a9c2\]/);
  assert.match(html[6], /<span class="warn">경고/);
  assert.equal(html[7], '<span class="ln" data-t="">일반 설명 줄</span>');
  assert.equal(html[8], '<span class="ln" data-t="">&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;x&quot;</span>', '태그는 글자로만 보임');
  assert.equal(paintLines([]), '');
  assert.ok(!paintLines([row('a')]).includes('14:'), '시각은 글자(textContent)에 들어가지 않고 data-t로만');
});

test('logRows: 줄별 시각 정렬·끝의 빈 줄 제외·찾기는 일치하는 줄만·다른 로그면 비움', () => {
  const ui: any = { keep: {}, log: { id: 'e1', next: 0, text: 'a\nGit add\nb\n', stamps: ['', '14:00:01', '14:00:02'] } };
  assert.deepEqual(logRows(ui, 'e1'), [{ t: '', s: 'a' }, { t: '14:00:01', s: 'Git add' }, { t: '14:00:02', s: 'b' }]);
  ui.keep.logFind = 'GIT';
  assert.deepEqual(logRows(ui, 'e1'), [{ t: '14:00:01', s: 'Git add' }], '대소문자 구분 없이 일치하는 줄만');
  assert.deepEqual(logRows(ui, 'other'), []);
  ui.keep.logFind = '';
  ui.log.text = 'a\nb'; ui.log.stamps = ['', ''];
  assert.equal(logRows(ui, 'e1').length, 2, '마지막 줄이 아직 끝나지 않아도 보임');
  assert.equal(footText({ id: 'e1' }, ui), '2줄 · 새 출력이 오면 자동으로 아래로 이동');
});

test('로그 단계는 시작 전에도 창을 보여 주고(안내문), 로그가 없는 단계는 null, 기록이 있으면 실행 중 로그를 고름', () => {
  const ui: any = { keep: {}, log: { id: null, text: '', stamps: [] } };
  const base: any = { taskId: 't1', mode: 'mock', exec: null, review: null, verification: null, integration: null };
  for (const key of ['build', 'tests', 'review', 'postcheck']) assert.ok(logTarget(base, key, ui).empty, `${key} 시작 전 안내`);
  for (const key of ['prepare', 'gitcheck', 'handoff', 'approve', 'integrate', 'push']) assert.equal(logTarget(base, key, ui), null);
  assert.match(logTarget({ ...base, mode: 'manual' }, 'build', ui).empty, /수동 모드/);
  assert.match(logTarget({ ...base, integration: { postStatus: 'not_run' } }, 'postcheck', ui).empty, /통합 후 검사가 없어/);
  const running = { ...base, exec: { execId: 'e1', status: 'running', pid: 4821, startedAt: new Date(Date.now() - 134_000).toISOString(), exitCode: null } };
  const g = logTarget(running, 'build', ui);
  assert.equal(g.live, true);
  assert.equal(g.api, 'execs/e1/log?from=');
  assert.match(statText(g), /● 실행 중.*PID 4821.*02:1\d 경과/);
  assert.equal(statText({ empty: 'x' }), '<span class="muted">○ 시작 전</span>');
  const tests = { ...base, verification: { items: [{ name: 'c1', execId: 'x1', status: 'passed', exitCode: 0 }, { name: 'c2', execId: 'x2', status: 'running' }] } };
  assert.equal(logTarget(tests, 'tests', ui).id, 'x2', '실행 중인 명령이 기본');
  ui.keep.logSel = 'x1';
  assert.equal(logTarget(tests, 'tests', ui).id, 'x1', '고른 명령');
  const post = { ...base, taskId: 't1', integration: { postChecks: [{ id: 'p1', name: 'post', status: 'running', logPath: 'a.log' }] } };
  assert.equal(logTarget(post, 'postcheck', ui).api, 'tasks/t1/post-log?check=p1&from=');
});

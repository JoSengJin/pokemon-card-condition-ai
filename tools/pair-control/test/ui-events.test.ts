// CLI 이벤트(JSONL) → 읽기 쉬운 줄, 받은 글 쌓기. 서버·브라우저 없이 샘플 이벤트로만 검사한다(실제 CLI 출력으로는 검증되지 않음).
import assert from 'node:assert/strict';
import { test } from 'node:test';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { appendLog, fmtLine } from '../src/ui/js/events.js';

const j = (o: unknown) => JSON.stringify(o);

test('Claude 이벤트: 시작·텍스트·도구 호출·도구 결과·완료를 줄로, 비용은 안 보임, 내용 이벤트의 형식 문자는 그대로', () => {
  assert.deepEqual(fmtLine(j({ type: 'system', subtype: 'init', model: 'm1', tools: ['Bash', 'Edit'], apiKeySource: 'none' })), ['[시작] 모델 m1 · 도구 2개 · 인증 none']);
  assert.deepEqual(fmtLine(j({ type: 'system', subtype: 'hook_started' })), []);
  assert.deepEqual(fmtLine(j({ type: 'assistant', message: { content: [{ type: 'text', text: '계약을 읽겠습니다.\n둘째 줄' }, { type: 'tool_use', name: 'Read', input: { file_path: 'docs/x.md' } }, { type: 'tool_use', name: 'Bash', input: { command: 'git status --short' } }] } })),
    ['계약을 읽겠습니다.', '둘째 줄', '[Read] docs/x.md', '$ git status --short']);
  assert.deepEqual(fmtLine(j({ type: 'user', message: { content: [{ type: 'tool_result', content: '\n# 작업 계약\n목표', is_error: false }, { type: 'tool_result', content: [{ type: 'text', text: 'boom' }], is_error: true }, { type: 'tool_result', content: '' }] } })),
    ['  → # 작업 계약', '  → 오류: boom']);
  assert.deepEqual(fmtLine(j({ type: 'result', subtype: 'success', is_error: false, duration_ms: 12_400, num_turns: 4, total_cost_usd: 0.5, result: 'x' })), ['[완료] 정상 종료 · 12초 · 4턴']);
  assert.deepEqual(fmtLine(j({ type: 'result', is_error: true, duration_ms: 900, num_turns: 1, result: 'Claude usage limit reached' })), ['[완료] 오류로 종료 · 1초 · 1턴', '오류: Claude usage limit reached']);
  assert.deepEqual(fmtLine(j({ type: 'rate_limit_event', rate_limit_info: { status: 'allowed' } })), []);
  assert.deepEqual(fmtLine(j({ type: 'rate_limit_event', rate_limit_info: { status: 'rejected' } })), ['[한도] rejected']);
  assert.ok(!fmtLine(j({ type: 'result', total_cost_usd: 0.123, duration_ms: 1, num_turns: 1 })).join('').includes('0.123'));
});

test('Codex 이벤트: 시작·명령·결과·메시지·파일 수정·완료·오류', () => {
  assert.deepEqual(fmtLine(j({ type: 'thread.started', thread_id: 'abcdef123456' })), ['[시작] 스레드 abcdef12']);
  assert.deepEqual(fmtLine(j({ type: 'turn.started' })), []);
  assert.deepEqual(fmtLine(j({ type: 'item.started', item: { type: 'command_execution', command: 'ls tests' } })), ['$ ls tests']);
  assert.deepEqual(fmtLine(j({ type: 'item.completed', item: { type: 'command_execution', command: 'ls tests', aggregated_output: 'a.py\n\nb.py\n', exit_code: 0 } })), ['  → 종료 코드 0', '    a.py', '    b.py']);
  assert.deepEqual(fmtLine(j({ type: 'item.completed', item: { type: 'agent_message', text: '수정했습니다.' } })), ['수정했습니다.']);
  assert.deepEqual(fmtLine(j({ type: 'item.completed', item: { type: 'file_change', changes: [{ path: 'a.py', kind: 'update' }] } })), ['[수정] a.py']);
  assert.deepEqual(fmtLine(j({ type: 'item.completed', item: { type: 'reasoning', text: '…' } })), []);
  assert.deepEqual(fmtLine(j({ type: 'turn.completed', usage: { input_tokens: 1 } })), ['[완료] 정상 종료']);
  assert.deepEqual(fmtLine(j({ type: 'turn.failed', error: { message: 'boom' } })), ['[완료] 오류로 종료', '오류: boom']);
  assert.deepEqual(fmtLine(j({ type: 'error', message: 'fail' })), ['오류: fail']);
});

test('모르는 이벤트·JSON이 아닌 줄·깨진 JSON은 원문 그대로(잘라서), 숨기지 않음', () => {
  assert.deepEqual(fmtLine('일반 텍스트 줄'), ['일반 텍스트 줄']);
  assert.deepEqual(fmtLine('{ 깨진 JSON'), ['{ 깨진 JSON']);
  assert.deepEqual(fmtLine('{"no":"type"}'), ['{"no":"type"}']);
  assert.deepEqual(fmtLine('{"type":"brand_new_event","x":1}'), ['{"type":"brand_new_event","x":1}']);
  const long = fmtLine(j({ type: 'new_event', pad: 'x'.repeat(1000) }))[0];
  assert.ok(long.length < 320 && long.endsWith(' …'));
});

test('appendLog: 끝난 줄만 변환해 쌓고 조각은 보류, 처음 열 때 줄은 시각 없음·이후는 HH:MM:SS, 종료하면 조각도 내보냄', () => {
  const log: any = { id: 'x', next: 0, rows: [], pending: '' };
  const ev = j({ type: 'assistant', message: { content: [{ type: 'text', text: '안녕' }] } });
  appendLog(log, '첫줄\n' + ev.slice(0, 20), true, true);
  assert.deepEqual(log.rows, [{ t: '', s: '첫줄' }], '처음 열 때 이미 있던 줄은 시각 없음, 잘린 JSON은 보류');
  appendLog(log, ev.slice(20) + '\n마지막', false, true);
  assert.equal(log.rows.length, 2);
  assert.equal(log.rows[1].s, '안녕', '이어 받은 이벤트가 변환됨');
  assert.match(log.rows[1].t, /^\d\d:\d\d:\d\d$/);
  assert.equal(log.pending, '마지막', '끝나지 않은 줄은 보류');
  appendLog(log, '', false, false);
  assert.equal(log.rows.at(-1).s, '마지막');
  assert.equal(log.pending, '', '실행이 끝나면 남은 조각을 내보냄');
  const many: any = { rows: [], pending: '' };
  appendLog(many, Array.from({ length: 5100 }, (_, i) => 'l' + i).join('\n') + '\n', false, true);
  assert.equal(many.rows.length, 5000);
  assert.equal(many.rows[0].s, 'l100', '앞쪽 줄부터 버림');
});

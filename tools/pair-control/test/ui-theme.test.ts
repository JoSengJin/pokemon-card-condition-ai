// 화면 색 전환 값 정리. DOM 없이 값 규칙만 검사한다(전환·기억은 브라우저에서 확인).
import assert from 'node:assert/strict';
import { test } from 'node:test';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { normalize } from '../src/ui/js/theme.js';

test('테마 값: light·dark만 그대로, 나머지(비어 있음·알 수 없음·조작된 값)는 시스템', () => {
  assert.equal(normalize('light'), 'light');
  assert.equal(normalize('dark'), 'dark');
  for (const v of [undefined, null, '', 'system', 'Light', '<script>', 'auto', 0]) assert.equal(normalize(v as any), 'system');
});

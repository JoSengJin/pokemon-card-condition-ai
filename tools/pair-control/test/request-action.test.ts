import assert from 'node:assert/strict';
import { test } from 'node:test';
import { act } from '../src/mastra/requestAction.ts';
import { UserError } from '../src/executor/errors.ts';

const context = { id: 'request', json: (value: unknown, status = 200) => ({ status, value }) };

test('HTTP 어댑터는 기존 컨텍스트·고정 입력·해석된 인자 목록을 서비스에 직접 넘긴다', async () => {
  assert.deepEqual(await act((input) => input.id)(context), { status: 200, value: { ok: true, data: 'request' } });
  const fixed = { id: 'executor' };
  assert.deepEqual(await act((input) => input.id, fixed)(context), { status: 200, value: { ok: true, data: 'executor' } });
  const order: string[] = [];
  const handler = act((owner, id) => { order.push('service'); assert.equal(owner, fixed); return id; }, async (input: typeof context) => { order.push('arguments'); return [fixed, input.id]; });
  assert.deepEqual(await handler(context), { status: 200, value: { ok: true, data: 'request' } });
  assert.deepEqual(order, ['arguments', 'service']);
});

test('인자 해석·동기 서비스·비동기 서비스 오류는 기존 400/500 응답 계약으로 돌아온다', async () => {
  const invalid = await act(() => 'unreachable', async () => { throw new UserError('잘못된 요청'); })(context);
  assert.deepEqual(invalid, { status: 400, value: { ok: false, error: '잘못된 요청' } });
  const failed = await act(() => { throw new Error('fixture failure'); })(context);
  assert.deepEqual(failed, { status: 500, value: { ok: false, error: '내부 오류: fixture failure' } });
  const asynchronous = await act(async () => { throw new UserError('보류'); })(context);
  assert.equal(asynchronous.status, 400);
});

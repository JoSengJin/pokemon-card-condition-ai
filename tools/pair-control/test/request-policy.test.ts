// Hono의 실제 검증 미들웨어를 사용하되 서버·네트워크·모델은 실행하지 않는다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Hono } from 'hono';
import { validator } from 'hono/validator';
import { validateRequest } from '../src/mastra/requestPolicy.ts';

test('검증은 기존 host/origin/요청 헤더 보호를 유지하고 통과한 요청만 라우트에 도달한다', async () => {
  const origin = 'http://127.0.0.1:4111', hosts = new Set(['127.0.0.1:4111', 'localhost:4111']);
  const app = new Hono(); let handled = 0;
  app.use('*', validator('header', (_headers, c) => validateRequest(c, hosts, [origin])));
  app.all('*', (c) => { handled++; return c.json({ ok: true }); });
  const cases: { method: string; headers: Record<string, string>; status: number }[] = [
    { method: 'GET', headers: { host: 'evil.example' }, status: 403 },
    { method: 'GET', headers: { host: '127.0.0.1:4111' }, status: 200 },
    { method: 'HEAD', headers: { host: 'localhost:4111' }, status: 200 },
    { method: 'OPTIONS', headers: { host: '127.0.0.1:4111' }, status: 200 },
    { method: 'POST', headers: { host: '127.0.0.1:4111', 'x-pair-control': '1' }, status: 403 },
    { method: 'POST', headers: { host: '127.0.0.1:4111', origin: 'https://evil.example', 'x-pair-control': '1' }, status: 403 },
    { method: 'POST', headers: { host: '127.0.0.1:4111', origin }, status: 403 },
    { method: 'POST', headers: { host: '127.0.0.1:4111', origin, 'x-pair-control': '2' }, status: 403 },
    { method: 'POST', headers: { host: '127.0.0.1:4111', origin, 'x-pair-control': '1' }, status: 200 },
  ];
  for (const row of cases) {
    const before = handled, response = await app.request(origin + '/pair/api/example', { method: row.method, headers: row.headers });
    assert.equal(response.status, row.status, JSON.stringify(row));
    assert.equal(handled - before, row.status === 200 ? 1 : 0, '거부되면 라우트 실행 없음');
  }
});

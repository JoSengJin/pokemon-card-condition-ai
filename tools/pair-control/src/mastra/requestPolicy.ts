// 검증 결과만 반환한다. 라우트 실행은 Hono가 검증 결과를 받은 뒤 담당한다.
export function validateRequest(c: any, allowedHosts: ReadonlySet<string>, allowedOrigins: readonly string[]) {
  const host = c.req.header('host') ?? '';
  if (!allowedHosts.has(host)) return c.json({ error: 'host not allowed' }, 403);
  const method = c.req.method;
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const origin = c.req.header('origin');
    if (origin && !allowedOrigins.includes(origin)) return c.json({ error: 'origin not allowed' }, 403);
    if (c.req.path.startsWith('/pair/api/') && (origin === undefined || c.req.header('x-pair-control') !== '1')) return c.json({ error: 'pair-control 요청 헤더/출처 누락' }, 403);
  }
}

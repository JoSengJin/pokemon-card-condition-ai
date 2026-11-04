import { ALLOWED_HOSTS, ALLOWED_ORIGINS } from './serverContext.ts';

export async function requestGuard(c: any, next: any) {
  const host = c.req.header('host') ?? '';
  if (!ALLOWED_HOSTS.has(host)) return c.json({ error: 'host not allowed' }, 403);
  const method = c.req.method;
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    const origin = c.req.header('origin');
    if (origin && !ALLOWED_ORIGINS.includes(origin)) return c.json({ error: 'origin not allowed' }, 403);
    if (c.req.path.startsWith('/pair/api/') && (origin === undefined || c.req.header('x-pair-control') !== '1')) return c.json({ error: 'pair-control 요청 헤더/출처 누락' }, 403);
  }
  await next();
}

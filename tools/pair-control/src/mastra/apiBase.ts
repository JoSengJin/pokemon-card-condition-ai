import fs from 'node:fs';
import path from 'node:path';
import { UserError } from '../executor/executor.ts';
import { cfg } from './serverContext.ts';

export { act } from './requestAction.ts';

export async function body(c: any) {
  try { return await c.req.json(); } catch { return {}; }
}

export function id(c: any) { return String(c.req.param('id')); }

export function serveStatic(c: any) {
  const file = String(c.req.param('file'));
  const full = path.join(cfg.toolRoot, 'src', 'ui', 'js', file);
  if (!/^[a-z][a-z-]{0,30}\.js$/.test(file) || !fs.existsSync(full)) return c.text('not found', 404);
  return c.body(fs.readFileSync(full, 'utf8'), 200, { 'content-type': 'text/javascript; charset=utf-8', 'cache-control': 'no-store' });
}

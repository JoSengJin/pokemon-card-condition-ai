import fs from 'node:fs';
import path from 'node:path';
import { registerApiRoute } from '@mastra/core/server';
import { serveStatic } from './apiBase.ts';
import { cfg } from './serverContext.ts';

export const staticRoutes = [
  registerApiRoute('/pair', { method: 'GET', handler: async (c: any) => c.html(fs.readFileSync(path.join(cfg.toolRoot, 'src', 'ui', 'page.html'), 'utf8')) }),
  registerApiRoute('/pair/static/:file', { method: 'GET', handler: async (c: any) => serveStatic(c) }),
];

// Mastra 조립 진입점. 설정·실행기·라우트 책임은 각각의 모듈에서 제공한다.
import path from 'node:path';
import { Mastra } from '@mastra/core/mastra';
import { LibSQLStore } from '@mastra/libsql';
import { pairTaskWorkflow, prepareTaskWorkflow } from '../workflow.ts';
import { bindRuntime } from '../runtime.ts';
import { cfg, executor, HOST, ALLOWED_ORIGINS } from './serverContext.ts';
import { requestGuard } from './serverMiddleware.ts';
import { routes } from './serverRoutes.ts';

export const mastra = new Mastra({
  workflows: { pairTaskWorkflow, prepareTaskWorkflow },
  storage: new LibSQLStore({ id: 'pair-control', url: `file:${path.join(cfg.stateDir, 'mastra.db')}` }),
  server: {
    host: HOST,
    port: cfg.port,
    cors: { origin: ALLOWED_ORIGINS, allowMethods: ['GET', 'POST', 'OPTIONS'], credentials: false },
    middleware: [requestGuard],
    apiRoutes: routes,
  },
});
bindRuntime(executor, mastra);

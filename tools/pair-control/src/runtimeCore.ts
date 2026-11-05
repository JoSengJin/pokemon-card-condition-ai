import { AsyncLocalStorage } from 'node:async_hooks';
import type { Mastra } from '@mastra/core/mastra';
import type { Executor } from './executor/executor.ts';

export const executionContext = new AsyncLocalStorage<{ executor: Executor; mastra: Mastra }>();
const instances = new WeakMap<Executor, Mastra>();
let executor: Executor | null = null;
let mastra: Mastra | null = null;

export function getExecutor(): Executor {
  const contextual = executionContext.getStore()?.executor;
  if (contextual) return contextual;
  if (!executor) throw new Error('pair-control 실행기가 초기화되지 않음');
  return executor;
}

export function getMastra(ex?: Executor): Mastra {
  const contextual = ex ? instances.get(ex) : executionContext.getStore()?.mastra;
  if (contextual) return contextual;
  if (!mastra) throw new Error('Mastra 인스턴스가 없음');
  return mastra;
}

export function setRuntime(ex: Executor, instance: Mastra) {
  instances.set(ex, instance);
  executor = ex;
  mastra = instance;
}

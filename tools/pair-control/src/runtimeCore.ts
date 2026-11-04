import type { Mastra } from '@mastra/core/mastra';
import type { Executor } from './executor/executor.ts';

let executor: Executor | null = null;
let mastra: Mastra | null = null;

export function getExecutor(): Executor {
  if (!executor) throw new Error('pair-control 실행기가 초기화되지 않음');
  return executor;
}

export function getMastra(): Mastra {
  if (!mastra) throw new Error('Mastra 인스턴스가 없음');
  return mastra;
}

export function setRuntime(ex: Executor, instance: Mastra) {
  executor = ex;
  mastra = instance;
}

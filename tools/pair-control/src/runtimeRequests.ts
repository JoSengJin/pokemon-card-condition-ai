// 요청과 결과는 JSON 상태에 남는다. 대기 함수는 실행 서비스를 호출하지 않는다.
import crypto from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { getExecutor } from './runtimeCore.ts';
import { UserError } from './executor/errors.ts';

export interface RuntimeOrigin { sessionId: string; generation: number; lifetime: string; action: string; target: string; sha?: string }
export interface RequestState { id: string; stage: 'queued' | 'dispatching' | 'done' | 'failed' | 'unknown'; lifetime?: string; error?: string; userError?: boolean; origin?: RuntimeOrigin }
export interface WorkflowResult { runId: string; status: string; result?: unknown }
export interface WorkflowRequest extends RequestState { kind: 'start' | 'resume'; workflow: 'pairTaskWorkflow' | 'prepareTaskWorkflow'; resourceId?: string; runId?: string; inputData?: unknown; step?: string; resumeData?: Record<string, unknown>; result?: WorkflowResult }
export interface ServiceRequest extends RequestState { parentId: string; service: 'plan' | 'worktree' | 'assign' | 'launch' | 'collect' | 'integrate'; payload: { raw?: unknown; taskId?: string; runId?: string; execId?: string | null }; result?: unknown }

export async function startWorkflow(workflow: WorkflowRequest['workflow'], inputData: unknown, resourceId?: string, origin?: RuntimeOrigin): Promise<WorkflowResult> {
  const ex = getExecutor(), request: WorkflowRequest = { id: crypto.randomUUID(), kind: 'start', workflow, inputData, resourceId, origin, stage: 'queued' };
  if (ex.stopped) throw new UserError('실행기가 정지됨 — workflow 요청을 시작하지 않음');
  (ex.state.workflowRequests ??= {})[request.id] = request; ex.store.save();
  while (!['done', 'failed', 'unknown'].includes(request.stage)) {
    if (ex.stopped) throw new UserError('실행기가 정지됨 — workflow 결과 불명, 재시도하지 않음');
    await delay(25);
  }
  if (request.stage !== 'done') throw request.userError ? new UserError(request.error!) : new Error(request.error);
  return request.result!;
}

export async function resumeStep(runId: string, step: string, resumeData: Record<string, unknown>, origin?: RuntimeOrigin) {
  const ex = getExecutor(), request: WorkflowRequest = { id: crypto.randomUUID(), kind: 'resume', workflow: 'pairTaskWorkflow', runId, step, resumeData, origin, stage: 'queued' };
  if (ex.stopped) throw new UserError('실행기가 정지됨 — workflow 재개 요청을 시작하지 않음');
  (ex.state.workflowRequests ??= {})[request.id] = request; ex.store.save();
  while (!['done', 'failed', 'unknown'].includes(request.stage)) {
    if (ex.stopped) throw new UserError('실행기가 정지됨 — workflow 재개 결과 불명, 재시도하지 않음');
    await delay(25);
  }
  if (request.stage !== 'done') throw request.userError ? new UserError(request.error!) : new Error(request.error);
  return request.result!.status;
}

export async function requestService<T>(service: ServiceRequest['service'], runId: string, payload: ServiceRequest['payload']): Promise<T> {
  const ex = getExecutor();
  let parent: WorkflowRequest | undefined;
  for (const request of Object.values(ex.state.workflowRequests ?? {})) if (request.runId === runId && request.stage === 'dispatching' && request.lifetime === ex.lifetime) parent = request;
  if (!parent || ex.stopped) throw new UserError('현재 수명의 workflow 실행 요청이 없음 — 도메인 서비스를 실행하지 않음');
  const request: ServiceRequest = { id: crypto.randomUUID(), parentId: parent.id, service, payload, stage: 'queued', origin: parent.origin };
  (ex.state.serviceRequests ??= {})[request.id] = request; ex.store.save();
  while (!['done', 'failed', 'unknown'].includes(request.stage)) {
    if (ex.stopped) throw new UserError('실행기가 정지됨 — 서비스 결과 불명, 재시도하지 않음');
    await delay(25);
  }
  if (request.stage !== 'done') throw request.userError ? new UserError(request.error!) : new Error(request.error);
  return request.result as T;
}

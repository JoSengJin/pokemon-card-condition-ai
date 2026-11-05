import { planTask } from './executor/preparePlan.ts';
import { createWorktree } from './executor/prepareWorktree.ts';
import { assign } from './executor/taskAssign.ts';
import { launch } from './executor/taskLaunch.ts';
import { collect } from './executor/taskCollect.ts';
import { integrate } from './executor/taskIntegration.ts';
import { UserError, type Executor } from './executor/executor.ts';
import type { TaskInputT } from './executor/contract.ts';
import { validateOrigin } from './runtimeRequestPolicy.ts';

/** 도메인 서비스는 framework 호출 사슬 밖에서 저장된 요청 하나만 처리한다. */
export async function serviceTick(ex: Executor) {
  if (ex.stopped || ex.serviceBusy) return;
  for (const request of Object.values(ex.state.serviceRequests ?? {})) if (request.stage === 'dispatching' && request.lifetime !== ex.lifetime) {
    request.stage = 'unknown'; request.error = '서버 재시작 전 서비스 실행 시작 — 결과 불명, 재시도하지 않음'; request.userError = true; ex.store.save();
  }
  let request;
  for (const row of Object.values(ex.state.serviceRequests ?? {})) if (row.stage === 'queued') { request = row; break; }
  if (!request) return;
  ex.serviceBusy = true;
  try {
    const parent = ex.state.workflowRequests?.[request.parentId];
    if (parent?.stage !== 'dispatching' || parent.lifetime !== ex.lifetime) throw new UserError('현재 수명의 workflow 소유 요청이 없음 — 서비스를 재시도하지 않음');
    validateOrigin(ex, request.origin);
    request.stage = 'dispatching'; request.lifetime = ex.lifetime; ex.store.save();
    const data = request.payload;
    if (request.service === 'plan') request.result = await planTask(ex, data.raw);
    else if (request.service === 'worktree') request.result = await createWorktree(ex, data.raw as TaskInputT);
    else if (request.service === 'assign') request.result = await assign(ex, data.raw);
    else if (request.service === 'launch') request.result = await launch(ex, data.taskId!, data.runId!);
    else if (request.service === 'collect') request.result = await collect(ex, data.taskId!, data.execId ?? null);
    else if (request.service === 'integrate') request.result = await integrate(ex, data.taskId!);
    else throw new UserError('지원하지 않는 workflow 서비스');
    if (ex.stopped) return;
    request.stage = 'done'; ex.store.save();
  } catch (error) {
    if (!ex.stopped) { request.stage = 'failed'; request.error = (error as Error).message; request.userError = error instanceof UserError; ex.store.save(); }
  } finally { ex.serviceBusy = false; }
}

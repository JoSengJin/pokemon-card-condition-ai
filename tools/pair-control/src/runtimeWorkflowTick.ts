import { getMastra, executionContext } from './runtimeCore.ts';
import { validateOrigin } from './runtimeRequestPolicy.ts';
import { UserError, type Executor } from './executor/executor.ts';

/** 저장된 workflow 요청만 실행한다. dispatching 재시작은 라이브러리를 재호출하지 않는다. */
export async function workflowTick(ex: Executor) {
  if (ex.stopped || ex.workflowBusy) return;
  for (const request of Object.values(ex.state.workflowRequests ?? {})) if (request.stage === 'dispatching' && request.lifetime !== ex.lifetime) {
    request.stage = 'unknown'; request.error = '서버 재시작 전 workflow 실행 시작 — 결과 불명, 재시도하지 않음'; request.userError = true; ex.store.save();
  }
  let request;
  for (const row of Object.values(ex.state.workflowRequests ?? {})) if (row.stage === 'queued') { request = row; break; }
  if (!request) return;
  ex.workflowBusy = true;
  try {
    validateOrigin(ex, request.origin);
    request.stage = 'dispatching'; request.lifetime = ex.lifetime; ex.store.save();
    const mastra = getMastra(ex), workflow = mastra.getWorkflow(request.workflow);
    const run = await workflow.createRun(request.kind === 'resume' ? { runId: request.runId! } : { resourceId: request.resourceId });
    request.runId = run.runId;
    if (request.kind === 'start' && request.workflow === 'pairTaskWorkflow' && (request.inputData as { reviewOnly?: boolean })?.reviewOnly) {
      const task = ex.state.tasks[request.resourceId!];
      if (!task) throw new UserError('재검토 대상 작업이 없음');
      task.runId = run.runId; task.runHistory = [...task.runHistory, run.runId];
    }
    ex.store.save();
    validateOrigin(ex, request.origin); // createRun 대기 사이 승인 철회·세대 변경도 실행을 막는다.
    const output = request.kind === 'resume'
      ? await executionContext.run({ executor: ex, mastra }, run.resume.bind(run, { step: request.step!, resumeData: request.resumeData! }))
      : await executionContext.run({ executor: ex, mastra }, run.start.bind(run, { inputData: request.inputData }));
    if (ex.stopped) return;
    request.result = { runId: run.runId, status: output.status, result: output.status === 'success' ? output.result : undefined };
    request.stage = 'done'; ex.store.save();
  } catch (error) {
    if (!ex.stopped) { request.stage = 'failed'; request.error = (error as Error).message; request.userError = error instanceof UserError; ex.store.save(); }
  } finally { ex.workflowBusy = false; }
}

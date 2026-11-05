import { getTask } from './executor/executorLookup.ts';
import { integrate } from './executor/taskIntegration.ts';
import { reject } from './executor/taskApproval.ts';
import { createStep } from '@mastra/core/workflows';
import { z } from 'zod';
import { getExecutor } from './runtime.ts';
import { Flow, type FlowT } from './workflowSchemas.ts';

export const reviewGate = createStep({
  id: 'review-gate', description: '검토 단계: 작업 테스트·별도 리뷰를 기다린 뒤 사람이 전체 SHA를 승인 또는 거절', inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.literal('human_review'), headSha: z.string().nullable(), checksPassed: z.boolean(), error: z.string().optional() }),
  resumeSchema: z.object({ decision: z.enum(['approve', 'reject']), sha: z.string().optional(), reason: z.string().optional() }),
  execute: async ({ inputData, resumeData, suspend, bail }) => {
    const ex = getExecutor();
    const wait = (error?: string) => suspend({ waitingFor: 'human_review', headSha: inputData.headSha ?? null, checksPassed: !!inputData.checksPassed, error });
    if (!resumeData) return await wait();
    const task = getTask(ex, inputData.taskId);
    if (resumeData.decision === 'reject') {
      if (task.status !== 'rejected') reject(ex, inputData.taskId, resumeData.reason ?? '');
      return bail({ taskId: inputData.taskId, outcome: 'rejected', detail: resumeData.reason ?? '사용자 거절' });
    }
    if (task.status !== 'approved' || task.approval?.sha !== resumeData.sha) return await wait('실행기 승인 기록과 재개 SHA가 다름');
    return { ...inputData, headSha: resumeData.sha };
  },
});

export const integrateGate = createStep({
  id: 'integrate-gate', description: '승인 SHA 통합 실행 대기 → 재검증 후 ./develop 안에서 cherry-pick', inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.literal('integration_approval'), sha: z.string().nullable(), detail: z.string().optional() }),
  resumeSchema: z.object({ action: z.enum(['integrate', 'reject', 'withdraw']), reason: z.string().optional() }),
  execute: async ({ inputData, resumeData, suspend }): Promise<FlowT> => {
    const ex = getExecutor();
    if (!resumeData) return (await suspend({ waitingFor: 'integration_approval', sha: inputData.headSha ?? null })) as never;
    if (resumeData.action === 'withdraw') return { ...inputData, outcome: 'withdrawn', detail: '사용자가 승인을 취소 — 재검토 실행으로 넘김' };
    if (resumeData.action === 'reject') {
      const task = getTask(ex, inputData.taskId);
      if (task.status !== 'rejected') reject(ex, inputData.taskId, resumeData.reason ?? '통합 거절');
      return { ...inputData, outcome: 'rejected', detail: resumeData.reason ?? '통합 거절' };
    }
    const result = await integrate(ex, inputData.taskId);
    if (result.outcome === 'integration_blocked') return (await suspend({ waitingFor: 'integration_approval', sha: inputData.headSha ?? null, detail: result.detail })) as never;
    return { ...inputData, outcome: result.outcome, detail: result.detail };
  },
});

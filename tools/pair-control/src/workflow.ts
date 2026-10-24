// Mastra Workflow: 작업 단계·분기·사람 승인 대기·실행 추적. 관리용 LLM 없음(결정적 단계만).
// 'await-exit' 대기 = CLI 프로세스가 실행 중이며 종료를 기다리는 workflow 대기(프로세스 일시정지가 아님).
// 'review-gate'·'integrate-gate' 대기 = 사람 승인 대기. CLI 프로세스는 이미 종료된 상태.
import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { getExecutor } from './runtime.ts';

const Flow = z.object({
  taskId: z.string(),
  reviewOnly: z.boolean().optional(),
  execId: z.string().nullable().optional(),
  exitCode: z.number().nullable().optional(),
  cancelled: z.boolean().optional(),
  headSha: z.string().nullable().optional(),
  checksPassed: z.boolean().optional(),
  outcome: z.string().optional(),
  detail: z.string().optional(),
});
type FlowT = z.infer<typeof Flow>;

const launch = createStep({
  id: 'launch',
  description: '계약·충돌·잠금·Git 사전 검사 후 감독 프로세스로 CLI 시작',
  inputSchema: Flow, outputSchema: Flow,
  execute: async ({ inputData, runId, bail }) => {
    if (inputData.reviewOnly) return { ...inputData, execId: null };
    const r = await getExecutor().launch(inputData.taskId, runId);
    if (!r.ok) return bail({ taskId: inputData.taskId, outcome: 'blocked', detail: r.reason });
    return { ...inputData, execId: r.execId };
  },
});

const awaitExit = createStep({
  id: 'await-exit',
  description: 'CLI 실행 중 — 실행기가 종료를 확인하면 재개(사람 승인 대기 아님)',
  inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.literal('cli_exit'), execId: z.string() }),
  resumeSchema: z.object({ execId: z.string(), exitCode: z.number().nullable(), signal: z.string().nullable(), cancelled: z.boolean() }),
  execute: async ({ inputData, resumeData, suspend }) => {
    if (!inputData.execId) return inputData;
    if (!resumeData || resumeData.execId !== inputData.execId) return await suspend({ waitingFor: 'cli_exit', execId: inputData.execId });
    return { ...inputData, exitCode: resumeData.exitCode, cancelled: resumeData.cancelled };
  },
});

const collect = createStep({
  id: 'collect',
  description: '전체 HEAD SHA·변경 파일·허용 범위·미커밋 변경 검사',
  inputSchema: Flow, outputSchema: Flow,
  execute: async ({ inputData, bail }) => {
    const r = await getExecutor().collect(inputData.taskId, inputData.execId ?? null);
    if (inputData.cancelled) return bail({ taskId: inputData.taskId, outcome: 'cancelled', detail: '사용자 중단' });
    if (inputData.execId && inputData.exitCode !== 0) return bail({ taskId: inputData.taskId, outcome: 'failed', detail: `종료코드 ${inputData.exitCode}` });
    return { ...inputData, headSha: r.headSha, checksPassed: r.checksPassed };
  },
});

const reviewGate = createStep({
  id: 'review-gate',
  description: '사람이 diff·검사 결과를 보고 전체 SHA를 승인 또는 거절',
  inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.literal('human_review'), headSha: z.string().nullable(), checksPassed: z.boolean(), error: z.string().optional() }),
  resumeSchema: z.object({ decision: z.enum(['approve', 'reject']), sha: z.string().optional(), reason: z.string().optional() }),
  execute: async ({ inputData, resumeData, suspend, bail }) => {
    const ex = getExecutor();
    const wait = (error?: string) => suspend({ waitingFor: 'human_review', headSha: inputData.headSha ?? null, checksPassed: !!inputData.checksPassed, error });
    if (!resumeData) return await wait();
    const t = ex.task(inputData.taskId);
    if (resumeData.decision === 'reject') {
      if (t.status !== 'rejected') ex.reject(inputData.taskId, resumeData.reason ?? '');
      return bail({ taskId: inputData.taskId, outcome: 'rejected', detail: resumeData.reason ?? '사용자 거절' });
    }
    // 승인 자체는 실행기가 SHA·검사를 검증해 기록한다. 기록과 재개 값이 다르면 다시 대기한다.
    if (t.status !== 'approved' || t.approval?.sha !== resumeData.sha) return await wait('실행기 승인 기록과 재개 SHA가 다름');
    return { ...inputData, headSha: resumeData.sha };
  },
});

const integrateGate = createStep({
  id: 'integrate-gate',
  description: '승인 SHA 통합 실행 대기 → 재검증 후 ./develop 안에서 cherry-pick',
  inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.literal('integration_approval'), sha: z.string().nullable(), detail: z.string().optional() }),
  resumeSchema: z.object({ action: z.enum(['integrate', 'reject']), reason: z.string().optional() }),
  execute: async ({ inputData, resumeData, suspend }): Promise<FlowT> => {
    const ex = getExecutor();
    if (!resumeData) return (await suspend({ waitingFor: 'integration_approval', sha: inputData.headSha ?? null })) as never;
    if (resumeData.action === 'reject') {
      const t = ex.task(inputData.taskId);
      if (t.status !== 'rejected') ex.reject(inputData.taskId, resumeData.reason ?? '통합 거절');
      return { ...inputData, outcome: 'rejected', detail: resumeData.reason ?? '통합 거절' };
    }
    const r = await ex.integrate(inputData.taskId);
    // 잠금 사용 중·checkout 미정리: 승인은 유지하고 같은 단계에서 다시 대기한다.
    if (r.outcome === 'integration_blocked') return (await suspend({ waitingFor: 'integration_approval', sha: inputData.headSha ?? null, detail: r.detail })) as never;
    return { ...inputData, outcome: r.outcome, detail: r.detail };
  },
});

export const pairTaskWorkflow = createWorkflow({
  id: 'pair-task',
  description: 'Codex·Claude 병렬 구현 작업 하나: 시작 → CLI 종료 대기 → 결과 수집 → 사람 검토 → 통합 대기 → 통합',
  inputSchema: Flow,
  outputSchema: Flow,
})
  .then(launch)
  .then(awaitExit)
  .then(collect)
  .then(reviewGate)
  .then(integrateGate)
  .commit();

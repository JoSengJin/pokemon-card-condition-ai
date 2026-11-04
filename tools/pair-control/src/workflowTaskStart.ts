import { createStep } from '@mastra/core/workflows';
import { z } from 'zod';
import { getExecutor } from './runtime.ts';
import { Flow } from './workflowSchemas.ts';

export const launch = createStep({
  id: 'launch', description: '계약·충돌·잠금·Git 사전 검사 후 감독 프로세스로 CLI 시작', inputSchema: Flow, outputSchema: Flow,
  execute: async ({ inputData, runId, bail }) => {
    if (inputData.reviewOnly) return { ...inputData, execId: null };
    const result = await getExecutor().launch(inputData.taskId, runId);
    if (!result.ok) return bail({ taskId: inputData.taskId, outcome: 'blocked', detail: result.reason });
    if ('manual' in result) return { ...inputData, execId: null, manual: true };
    return { ...inputData, execId: result.execId };
  },
});

export const awaitExit = createStep({
  id: 'await-exit', description: 'CLI 실행 중 — 실행기가 종료를 확인하면 재개(사람 승인 대기 아님)', inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.enum(['cli_exit', 'manual_done']), execId: z.string() }),
  resumeSchema: z.object({ execId: z.string(), exitCode: z.number().nullable(), signal: z.string().nullable(), cancelled: z.boolean() }),
  execute: async ({ inputData, resumeData, suspend }) => {
    if (inputData.manual) {
      if (!resumeData) return await suspend({ waitingFor: 'manual_done', execId: 'manual' });
      return { ...inputData, exitCode: resumeData.exitCode, cancelled: resumeData.cancelled };
    }
    if (!inputData.execId) return inputData;
    if (!resumeData || resumeData.execId !== inputData.execId) return await suspend({ waitingFor: 'cli_exit', execId: inputData.execId });
    return { ...inputData, exitCode: resumeData.exitCode, cancelled: resumeData.cancelled };
  },
});

export const collect = createStep({
  id: 'collect', description: '전체 HEAD SHA·변경 파일·허용 범위·미커밋 변경 검사', inputSchema: Flow, outputSchema: Flow,
  execute: async ({ inputData, bail }) => {
    if (inputData.manual && inputData.cancelled) return bail({ taskId: inputData.taskId, outcome: 'cancelled', detail: '수동 작업 취소' });
    const result = await getExecutor().collect(inputData.taskId, inputData.execId ?? null);
    if (inputData.cancelled) return bail({ taskId: inputData.taskId, outcome: 'cancelled', detail: '사용자 중단' });
    if (inputData.execId && inputData.exitCode !== 0) return bail({ taskId: inputData.taskId, outcome: 'failed', detail: `종료코드 ${inputData.exitCode}` });
    return { ...inputData, headSha: result.headSha, checksPassed: result.checksPassed };
  },
});

// Workflow 조립만 담당한다. 각 단계의 실행 책임은 task/prepare 단계 파일에 둔다.
import { createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { Flow, Prepared } from './workflowSchemas.ts';
import { awaitExit, collect, launch } from './workflowTaskStart.ts';
import { integrateGate, reviewGate } from './workflowTaskGates.ts';
import { createWorktreeStep, planStep, registerStep } from './workflowPrepare.ts';

export const pairTaskWorkflow = createWorkflow({
  id: 'pair-task',
  description: 'Codex·Claude 병렬 구현 작업 하나: 시작 → CLI 종료 대기 → 결과 수집 → 사람 검토 → 통합 대기 → 통합',
  inputSchema: Flow,
  outputSchema: Flow,
}).then(launch).then(awaitExit).then(collect).then(reviewGate).then(integrateGate).commit();

export const prepareTaskWorkflow = createWorkflow({
  id: 'prepare-task',
  description: '작업 준비: 값 자동 계산 → worktree·브랜치 생성(재시도 시 재사용) → 계약 커밋·배정 (관리용 LLM 없음)',
  inputSchema: z.any(),
  outputSchema: Prepared,
}).then(planStep).then(createWorktreeStep).then(registerStep).commit();

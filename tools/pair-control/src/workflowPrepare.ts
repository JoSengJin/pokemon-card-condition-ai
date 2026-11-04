import { assign } from './executor/taskAssign.ts';
import { createStep } from '@mastra/core/workflows';
import { z } from 'zod';
import { getExecutor } from './runtime.ts';
import { createWorktree, planTask } from './executor/prepare.ts';
import { Prepared } from './workflowSchemas.ts';

export const planStep = createStep({
  id: 'plan', description: 'task ID·브랜치·기준 SHA·worktree 경로 계산과 겹침 검사', inputSchema: z.any(), outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    const plan = await planTask(getExecutor(), inputData);
    if (!plan.ok || !plan.task) return bail({ ok: false, detail: plan.checks.filter((check) => !check.ok).map((check) => `${check.name}: ${check.detail}`).join(' / ') });
    return { ok: true, taskId: plan.task.taskId, createWorktree: plan.createWorktree, task: plan.task };
  },
});

export const createWorktreeStep = createStep({
  id: 'create-worktree', description: 'worktree와 브랜치 생성(기존 경로·브랜치는 덮어쓰지 않음)', inputSchema: Prepared, outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    if (!inputData.createWorktree) return inputData;
    try {
      const worktree = await createWorktree(getExecutor(), inputData.task);
      return { ...inputData, task: { ...inputData.task, worktree } };
    } catch (err) { return bail({ ok: false, taskId: inputData.taskId, detail: (err as Error).message }); }
  },
});

export const registerStep = createStep({
  id: 'register', description: '작업 계약을 커밋하고 등록한다. 시작은 사람이 따로 누른다.', inputSchema: Prepared, outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    try {
      const task = await assign(getExecutor(), inputData.task);
      return { ok: true, taskId: task.taskId, createWorktree: inputData.createWorktree, detail: `배정 완료: ${task.branch} @ ${task.baseSha.slice(0, 12)}` };
    } catch (err) { return bail({ ok: false, taskId: inputData.taskId, detail: `${(err as Error).message}${inputData.createWorktree ? ' (만든 worktree는 지우지 않았음 — 직접 확인)' : ''}` }); }
  },
});

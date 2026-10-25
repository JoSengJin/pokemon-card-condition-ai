// Mastra Workflow: 작업 단계·분기·사람 승인 대기·실행 추적. 관리용 LLM 없음(결정적 단계만).
// 'await-exit' 대기 = CLI 프로세스가 실행 중이며 종료를 기다리는 workflow 대기(프로세스 일시정지가 아님).
// 'review-gate'·'integrate-gate' 대기 = 사람 승인 대기. CLI 프로세스는 이미 종료된 상태.
import { createStep, createWorkflow } from '@mastra/core/workflows';
import { z } from 'zod';
import { getExecutor } from './runtime.ts';
import { createWorktree, planTask } from './executor/prepare.ts';

const Flow = z.object({
  taskId: z.string(),
  reviewOnly: z.boolean().optional(),
  execId: z.string().nullable().optional(),
  exitCode: z.number().nullable().optional(),
  cancelled: z.boolean().optional(),
  manual: z.boolean().optional(),
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
    if ('manual' in r) return { ...inputData, execId: null, manual: true };
    return { ...inputData, execId: r.execId };
  },
});

const awaitExit = createStep({
  id: 'await-exit',
  description: 'CLI 실행 중 — 실행기가 종료를 확인하면 재개(사람 승인 대기 아님)',
  inputSchema: Flow, outputSchema: Flow,
  suspendSchema: z.object({ waitingFor: z.enum(['cli_exit', 'manual_done']), execId: z.string() }),
  resumeSchema: z.object({ execId: z.string(), exitCode: z.number().nullable(), signal: z.string().nullable(), cancelled: z.boolean() }),
  execute: async ({ inputData, resumeData, suspend }) => {
    if (inputData.manual) {
      // 수동 모드: 프로세스가 없다. 사용자가 "작업 완료"(또는 취소)를 누르면 재개된다.
      if (!resumeData) return await suspend({ waitingFor: 'manual_done', execId: 'manual' });
      return { ...inputData, exitCode: resumeData.exitCode, cancelled: resumeData.cancelled };
    }
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
    // 수동 작업 취소는 결과를 수집하지 않는다(실행기가 이미 취소로 기록함).
    if (inputData.manual && inputData.cancelled) return bail({ taskId: inputData.taskId, outcome: 'cancelled', detail: '수동 작업 취소' });
    const r = await getExecutor().collect(inputData.taskId, inputData.execId ?? null);
    if (inputData.cancelled) return bail({ taskId: inputData.taskId, outcome: 'cancelled', detail: '사용자 중단' });
    if (inputData.execId && inputData.exitCode !== 0) return bail({ taskId: inputData.taskId, outcome: 'failed', detail: `종료코드 ${inputData.exitCode}` });
    return { ...inputData, headSha: r.headSha, checksPassed: r.checksPassed };
  },
});

const reviewGate = createStep({
  id: 'review-gate',
  description: '검토 단계: 실행기가 작업 테스트·별도 리뷰를 사용자 요청으로 실행하는 동안 대기. 사람이 diff·Git 계약 검사·작업 테스트 결과를 보고 전체 SHA를 승인 또는 거절',
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
  resumeSchema: z.object({ action: z.enum(['integrate', 'reject', 'withdraw']), reason: z.string().optional() }),
  execute: async ({ inputData, resumeData, suspend }): Promise<FlowT> => {
    const ex = getExecutor();
    if (!resumeData) return (await suspend({ waitingFor: 'integration_approval', sha: inputData.headSha ?? null })) as never;
    // 승인 취소: 실행기가 이미 검토 단계로 되돌리는 중이다. 이 실행은 여기서 끝내고 재검토 실행이 이어받는다.
    if (resumeData.action === 'withdraw') return { ...inputData, outcome: 'withdrawn', detail: '사용자가 승인을 취소 — 재검토 실행으로 넘김' };
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

// ---------- 작업 준비: 사람이 고르기 어려운 값(브랜치·기준 SHA·worktree)을 결정적으로 채우고 만든다 ----------
const Prepared = z.object({
  ok: z.boolean(),
  taskId: z.string().optional(),
  createWorktree: z.boolean().optional(),
  task: z.any().optional(),
  detail: z.string().optional(),
});

const planStep = createStep({
  id: 'plan',
  description: 'task ID·브랜치·기준 SHA(통합 브랜치 HEAD)·worktree 경로 계산과 겹침 검사(부작용 없음)',
  inputSchema: z.any(), outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    const p = await planTask(getExecutor(), inputData);
    if (!p.ok || !p.task) return bail({ ok: false, detail: p.checks.filter((c) => !c.ok).map((c) => `${c.name}: ${c.detail}`).join(' / ') });
    return { ok: true, taskId: p.task.taskId, createWorktree: p.createWorktree, task: p.task };
  },
});

const createWorktreeStep = createStep({
  id: 'create-worktree',
  description: 'git worktree add -b <브랜치> <경로> <기준 SHA> (기존 경로·브랜치는 덮어쓰지 않음)',
  inputSchema: Prepared, outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    if (!inputData.createWorktree) return inputData;
    try {
      const real = await createWorktree(getExecutor(), inputData.task);
      return { ...inputData, task: { ...inputData.task, worktree: real } };
    } catch (err) {
      return bail({ ok: false, taskId: inputData.taskId, detail: (err as Error).message });
    }
  },
});

const registerStep = createStep({
  id: 'register',
  description: '작업 계약 파일을 작업 브랜치에 커밋(같은 내용이면 재사용)하고 등록. 시작은 사람이 따로 누른다.',
  inputSchema: Prepared, outputSchema: Prepared,
  execute: async ({ inputData, bail }) => {
    try {
      const t = await getExecutor().assign(inputData.task);
      return { ok: true, taskId: t.taskId, createWorktree: inputData.createWorktree, detail: `배정 완료: ${t.branch} @ ${t.baseSha.slice(0, 12)}` };
    } catch (err) {
      return bail({ ok: false, taskId: inputData.taskId, detail: `${(err as Error).message}${inputData.createWorktree ? ' (만든 worktree는 지우지 않았음 — 직접 확인)' : ''}` });
    }
  },
});

export const prepareTaskWorkflow = createWorkflow({
  id: 'prepare-task',
  description: '작업 준비: 값 자동 계산 → worktree·브랜치 생성(재시도 시 재사용) → 계약 커밋·배정 (관리용 LLM 없음)',
  inputSchema: z.any(),
  outputSchema: Prepared,
})
  .then(planStep)
  .then(createWorktreeStep)
  .then(registerStep)
  .commit();

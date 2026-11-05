import { z } from 'zod';
import { AGENTS, MODES, MOCK_SCENARIOS, type TaskInputT, type ConflictReason } from './contract.ts';
import type { Check } from './executor.ts';

export const PrepareInput = z.object({
  taskId: z.string().trim().optional().default(''),
  agent: z.enum(AGENTS),
  mode: z.enum(MODES).default('mock'),
  mockScenario: z.enum(MOCK_SCENARIOS).default('success'),
  goal: z.string().trim().min(1, '목표를 적어 주세요').max(500),
  prompt: z.string().max(8000).default(''),
  allowedFiles: z.array(z.string()).default([]),
  conflictGroups: z.array(z.string()).default([]),
  doneCriteria: z.array(z.string()).default([]),
  readDocs: z.array(z.string()).default([]),
  /** 구조화된 검사 명령. 상세 검증은 TaskInput(CheckSpec)이 한다. */
  checks: z.array(z.any()).default([]),
  postChecks: z.array(z.any()).default([]),
  env: z.enum(['auto', 'none', 'python', 'python-project']).default('auto'),
  requiredModules: z.array(z.string()).default([]),
  /** 고급: 기준 SHA 직접 지정(비우면 통합 브랜치 HEAD) */
  baseSha: z.string().trim().optional().default(''),
  /** 고급: 이미 있는 worktree 사용(비우면 새로 만든다) */
  worktree: z.string().trim().optional().default(''),
});
export type PrepareInputT = z.infer<typeof PrepareInput>;

export interface Plan {
  ok: boolean;
  task: TaskInputT | null;
  createWorktree: boolean;
  baseRef: string;
  baseSubject: string;
  checks: Check[];
  conflicts: ConflictReason[];
  warnings: string[];
  envAuto?: boolean;
  /** 허용 파일을 비워 기본 범위(코드·테스트·문서)가 적용됨 */
  scopeDefault?: boolean;
}

import { z } from 'zod';
import { AGENTS, MODES, MOCK_SCENARIOS, ENV_PROFILES } from './contractConstants.ts';
import { scopePath } from './contractScopeSchema.ts';
import { CheckSpec } from './contractCheckSchema.ts';
import { isForbidden } from './contractPaths.ts';

export const TaskInput = z.object({
  taskId: z.string().regex(/^[a-z0-9][a-z0-9._-]{2,63}$/, 'task ID 형식: 소문자·숫자·.-_ 3~64자'),
  agent: z.enum(AGENTS),
  mode: z.enum(MODES).default('mock'),
  branch: z.string().regex(/^(claude|codex)\/[A-Za-z0-9._\/-]{1,100}$/),
  worktree: z.string().min(2).refine((p) => p.startsWith('/'), '절대경로'),
  baseSha: z.string().regex(/^[0-9a-f]{40}$/, '전체 40자 SHA'),
  allowedFiles: z.array(scopePath).min(1).max(200),
  conflictGroups: z.array(z.string().regex(/^[a-z0-9:._-]{1,64}$/)).max(20).default([]),
  goal: z.string().min(1).max(500),
  prompt: z.string().max(8000).default(''),
  mockScenario: z.enum(MOCK_SCENARIOS).default('success'),
  requiresExperiment: z.boolean().default(false),
  doneCriteria: z.array(z.string().min(1).max(300)).max(20).default([]),
  /** 에이전트가 먼저 읽을 저장소 문서(상대경로). 메인이 본 근거를 담은 문서를 가리킨다(worktree에는 data·artifacts가 없다). */
  readDocs: z.array(scopePath).max(20).default([]),
  checks: z.array(CheckSpec).max(20).default([]),
  postChecks: z.array(CheckSpec).max(20).default([]),
  env: z.enum(ENV_PROFILES).default('none'),
  requiredModules: z.array(z.string().regex(/^[A-Za-z_][A-Za-z0-9_.]{0,80}$/)).max(30).default([]),
}).superRefine((t, ctx) => {
  if (t.postChecks.some((c) => c.cwd !== '.')) ctx.addIssue({ code: 'custom', message: '통합 후 검사는 ./develop 안에서 checkout 루트(cwd=.)로만 실행', path: ['postChecks'] });
  const ids = [...t.checks, ...t.postChecks].map((c) => c.id);
  if (new Set(ids).size !== ids.length) ctx.addIssue({ code: 'custom', message: '검사 id가 중복됨', path: ['checks'] });
  if ([...t.checks, ...t.postChecks].some((c) => c.executable === '.venv/bin/python') && t.env === 'none') {
    ctx.addIssue({ code: 'custom', message: '.venv/bin/python 검사는 실행 환경을 python 또는 python-project로 지정해야 함', path: ['env'] });
  }
  const prefix = t.branch.split('/')[0];
  if (prefix !== t.agent) ctx.addIssue({ code: 'custom', message: `branch 접두어(${prefix})가 담당 에이전트(${t.agent})와 다릅니다.`, path: ['branch'] });
  for (const f of t.allowedFiles) {
    if (isForbidden(f)) {
      ctx.addIssue({ code: 'custom', message: `금지 경로: ${f} (데이터·라벨·산출물·비밀 설정은 기본 checkout 단일 담당자 소관)`, path: ['allowedFiles'] });
    }
  }
  if (t.requiresExperiment) {
    ctx.addIssue({ code: 'custom', message: '학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토는 기본 checkout 단일 실행 담당자만 수행합니다.', path: ['requiresExperiment'] });
  }
});

export type TaskInputT = z.infer<typeof TaskInput>;

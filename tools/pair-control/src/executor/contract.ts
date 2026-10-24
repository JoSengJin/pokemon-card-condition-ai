// task 계약 검증과 동시 실행 충돌 규칙.
// 허용 파일 목록은 사후 diff 검사로만 확인한다. 실행 중 파일 쓰기를 막는 격리 장치는 아니다.
import { z } from 'zod';

export const AGENTS = ['codex', 'claude'] as const;
/** mock = 모델 요청 없는 mock 프로세스(기본). real = 설치 확인된 실제 CLI(별도 승인 필요). */
export const MODES = ['mock', 'real'] as const;
export type Agent = (typeof AGENTS)[number];

export const MOCK_SCENARIOS = ['success', 'fail', 'hang', 'spawn-child', 'touch-forbidden', 'paid-message', 'slow-success'] as const;

/** 기본 checkout 단일 담당자만 다루는 경로. 병렬 구현 작업에 배정하지 않는다. */
export const FORBIDDEN_PREFIXES = ['data/', 'artifacts/', '.backups/', '.venv/', '.git/', 'build/', 'dist/'];
export const FORBIDDEN_FILES = ['development-review.json', 'nemotron-review.json', '.env', 'trusted-experiment.json'];
/** 공용 설정. 이 중 하나라도 허용하면 암묵 그룹 shared-config로 직렬화한다. */
export const SHARED_CONFIG = ['pyproject.toml', 'requirements-tested.txt', 'AGENTS.md', 'PAIR_CODING.md', 'README.md',
  'development-progress.json', 'PROGRESS_CRITERIA.md', '.gitignore', 'develop', 'experiment', 'review'];
/** 모델·worker 경로. 이 경로를 허용한 작업은 worktree의 ./develop 잠금 안에서 실행한다. */
export const DEVELOP_LOCK_PREFIXES = ['card_condition/', 'tools/experiments/'];

const relPath = z.string().min(1).max(300)
  .refine((p) => !p.startsWith('/') && !p.split('/').includes('..') && !p.includes('\0') && !p.includes('\\'), '상대경로만 허용')
  .refine((p) => !/[*?[\]]/.test(p), 'glob은 허용하지 않음. 정확한 파일 또는 "디렉터리/"');

export const TaskInput = z.object({
  taskId: z.string().regex(/^[a-z0-9][a-z0-9._-]{2,63}$/, 'task ID 형식: 소문자·숫자·.-_ 3~64자'),
  agent: z.enum(AGENTS),
  mode: z.enum(MODES).default('mock'),
  branch: z.string().regex(/^(claude|codex)\/[A-Za-z0-9._\/-]{1,100}$/),
  worktree: z.string().min(2).refine((p) => p.startsWith('/'), '절대경로'),
  baseSha: z.string().regex(/^[0-9a-f]{40}$/, '전체 40자 SHA'),
  allowedFiles: z.array(relPath).min(1).max(200),
  conflictGroups: z.array(z.string().regex(/^[a-z0-9:._-]{1,64}$/)).max(20).default([]),
  goal: z.string().min(1).max(500),
  prompt: z.string().max(8000).default(''),
  mockScenario: z.enum(MOCK_SCENARIOS).default('success'),
  requiresExperiment: z.boolean().default(false),
}).superRefine((t, ctx) => {
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

export function isForbidden(f: string) {
  return FORBIDDEN_PREFIXES.some((p) => f === p.slice(0, -1) || f.startsWith(p)) || FORBIDDEN_FILES.includes(f) || /(^|\/)labels[^/]*\.jsonl$/.test(f);
}

/** 정확한 파일 또는 "dir/" 접두어 사이의 겹침. */
export function pathsOverlap(a: string, b: string) {
  if (a === b) return true;
  const ad = a.endsWith('/'), bd = b.endsWith('/');
  if (ad && b.startsWith(a)) return true;
  if (bd && a.startsWith(b)) return true;
  return false;
}

export function effectiveGroups(t: Pick<TaskInputT, 'allowedFiles' | 'conflictGroups'>) {
  const g = new Set(t.conflictGroups);
  if (t.allowedFiles.some((f) => SHARED_CONFIG.some((s) => pathsOverlap(f, s)))) g.add('shared-config');
  return [...g];
}

export function needsDevelopLock(t: Pick<TaskInputT, 'allowedFiles'>) {
  return t.allowedFiles.some((f) => DEVELOP_LOCK_PREFIXES.some((p) => pathsOverlap(f, p)));
}

export interface ConflictReason { kind: 'files' | 'group' | 'worktree' | 'branch'; detail: string; otherTask: string }

export function conflicts(a: TaskInputT, b: TaskInputT): ConflictReason[] {
  const out: ConflictReason[] = [];
  for (const fa of a.allowedFiles) for (const fb of b.allowedFiles) {
    if (pathsOverlap(fa, fb)) out.push({ kind: 'files', detail: `${fa} ↔ ${fb}`, otherTask: b.taskId });
  }
  const gb = new Set(effectiveGroups(b));
  for (const g of effectiveGroups(a)) if (gb.has(g)) out.push({ kind: 'group', detail: g, otherTask: b.taskId });
  if (a.worktree === b.worktree) out.push({ kind: 'worktree', detail: a.worktree, otherTask: b.taskId });
  if (a.branch === b.branch) out.push({ kind: 'branch', detail: a.branch, otherTask: b.taskId });
  return out;
}

export function isAllowed(file: string, allowed: string[]) {
  return allowed.some((a) => (a.endsWith('/') ? file.startsWith(a) : file === a));
}

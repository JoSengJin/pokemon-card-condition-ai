// task 계약 검증과 동시 실행 충돌 규칙.
// 허용 파일 목록은 사후 diff 검사로만 확인한다. 실행 중 파일 쓰기를 막는 격리 장치는 아니다.
import { z } from 'zod';

export const AGENTS = ['codex', 'claude'] as const;
/** mock = 모델 요청 없는 mock 프로세스. real = 도구가 실제 CLI를 구독 로그인으로 실행(무과금 가드 통과 필요). manual = 도구는 에이전트를 실행하지 않고, 사용자가 에이전트 세션에서 작업(소유권·검사·인계만 관리). */
export const MODES = ['mock', 'real', 'manual'] as const;
export type Agent = (typeof AGENTS)[number];

export const MOCK_SCENARIOS = ['success', 'fail', 'hang', 'spawn-child', 'touch-forbidden', 'paid-message', 'slow-success', 'edit-contract'] as const;

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

/**
 * 허용 파일 경로. 정리된 표기만 받는다: "./"·"."(저장소 전체), "./docs/", "a//b", "a/./b"는 거부한다.
 * 경로 비교(isAllowed·isForbidden·pathsOverlap)는 글자 그대로의 접두어 비교라, 정리되지 않은 표기는 어떤 파일과도 맞지 않거나
 * 금지·충돌 검사를 지나쳐 버린다.
 */
const scopePath = relPath
  .refine((p) => p !== '.' && p !== './' && !p.startsWith('./') && !p.includes('//') && !p.includes('/./') && !p.endsWith('/.'),
    '정리되지 않은 경로: "./"·"."(저장소 전체)·"./docs/" 표기는 거부합니다. 정확한 파일 또는 "디렉터리/"만 쓰세요');

/** 검사 명령에 허용하는 실행 파일. 셸·임의 경로는 받지 않는다. .venv/bin/python은 해당 checkout의 자체 가상환경. */
export const CHECK_EXECUTABLES = ['git', 'node', '.venv/bin/python'] as const;
/** 검사로 실행하면 안 되는 진입점(학습·실험 기록·자동 교차 검토·잠금 우회). */
const DENIED_CHECK_ARGS = /experiment_record|cross_review|workspace_lock|(^|\s)(train|predict|infer)(\s|$)/;
export const CHECK_PLACEHOLDERS = ['{base}', '{contract}', '{head}'];

export const CheckSpec = z.object({
  id: z.string().regex(/^[a-z0-9][a-z0-9_-]{0,31}$/),
  name: z.string().min(1).max(80),
  executable: z.enum(CHECK_EXECUTABLES),
  args: z.array(z.string().max(500).refine((a) => !a.includes('\0'))).max(40).default([]),
  cwd: relPath.default('.'),
}).superRefine((c, ctx) => {
  if (DENIED_CHECK_ARGS.test(c.args.join(' '))) ctx.addIssue({ code: 'custom', message: `검사 '${c.name}': 학습·실험·자동 검토 진입점은 검사로 실행할 수 없음`, path: ['args'] });
});
export type CheckSpecT = z.infer<typeof CheckSpec>;

/** 실행 환경 요구: none(파이썬 불필요) / python(자체 .venv, 표준 라이브러리) / python-project(자체 .venv + 프로젝트 import·추가 모듈). */
export const ENV_PROFILES = ['none', 'python', 'python-project'] as const;

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

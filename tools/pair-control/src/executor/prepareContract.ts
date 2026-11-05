import { TaskInput } from './contract.ts';
import { SCOPE_PRESET } from './scope.ts';
import { listTracked } from './prepareTracked.ts';
import type { Executor } from './executor.ts';
import type { PrepareInputT } from './prepareInput.ts';

export async function planContract(ex: Executor, input: PrepareInputT, taskId: string, branch: string, worktree: string, baseSha: string, add: (name: string, ok: boolean, detail: string) => void, warnings: string[]) {
  const repo = ex.cfg.repo;
  // 허용 파일: 비우면 기본 범위. 데이터·라벨·산출물·공용 설정은 기본 범위에 없고, 직접 적어도 금지 경로 규칙이 막는다.
  const scopeDefault = !input.allowedFiles.length;
  const allowed = scopeDefault ? [...SCOPE_PRESET.files] : input.allowedFiles;
  if (scopeDefault) add('허용 파일', true, `비워 두어 기본 범위 적용: ${allowed.join(', ')}`);
  const tracked = await listTracked(repo, baseSha);
  const missing = allowed.filter((f) => !(f.endsWith('/') ? tracked.dirs.has(f) : tracked.files.has(f)));
  if (missing.length) warnings.push(`기준 커밋에 없는 경로(새 파일로 간주): ${missing.join(', ')}`);

  // 실행 환경 자동 판단: Python 파일·모델 경로·.venv 검사가 있으면 자체 가상환경이 필요하다.
  const envAuto = input.env === 'auto';
  const usesPython = allowed.some((f) => f.endsWith('.py') || /^(card_condition|tests|tools\/experiments)(\/|$)/.test(f))
    || [...input.checks, ...input.postChecks].some((c: any) => c?.executable === '.venv/bin/python');
  const envProfile = envAuto ? (usesPython ? 'python' : 'none') : input.env;
  const task = { taskId, agent: input.agent, mode: input.mode, mockScenario: input.mockScenario, branch, worktree, baseSha,
    allowedFiles: allowed, conflictGroups: input.conflictGroups, goal: input.goal, prompt: input.prompt,
    doneCriteria: input.doneCriteria, readDocs: input.readDocs, checks: input.checks, postChecks: input.postChecks, env: envProfile, requiredModules: input.requiredModules };
  const v = TaskInput.safeParse(task);
  if (!v.success) add('계약 규칙', false, v.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join(' / '));
  else add('계약 규칙', true, '금지 경로·브랜치 접두어·검사 명령 형식 통과');
  if (v.success && !v.data.checks.length) warnings.push('작업 테스트가 없으면 승인할 수 없음(미실행은 통과가 아님)');
  const missingDocs = input.readDocs.filter((f) => !tracked.files.has(f));
  if (missingDocs.length) add('읽을 문서', false, `기준 커밋에 없는 문서: ${missingDocs.join(', ')} (커밋된 문서만 에이전트가 볼 수 있음)`);
  if (scopeDefault && input.mode !== 'mock') warnings.push('허용 파일이 기본 범위(폴더 전체)입니다 — 메인이 정한 정확한 파일 경로로 좁히면 겹침과 범위 이탈을 줄일 수 있음');
  if (!input.doneCriteria.length && !input.readDocs.length && input.mode !== 'mock') {
    warnings.push('완료 조건과 읽을 문서가 없으면 에이전트가 구현 대상을 못 정하고 보고서만 쓰고 끝날 수 있음 — 2번 단계의 "메인에게 계약 작성 요청"으로 계약을 채우세요');
  }

  return { v, envAuto, scopeDefault };
}

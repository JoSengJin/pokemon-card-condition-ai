// 에이전트 세션에 붙여 넣을 시작 프롬프트. 규칙 기반 조립이며 LLM을 쓰지 않는다.
// 로컬 절대경로는 복사 시점에만 넣고 어떤 파일에도 커밋하지 않는다(PAIR_CODING §2).
import * as G from './git.ts';
import type { Task } from './executor.ts';

export interface PromptOptions {
  /** 사용자가 자리에 없는 장시간 작업(사람 정답 추정·재요청 금지 문구를 넣는다). */
  unattended?: boolean;
  /** 계약 외에 먼저 읽을 문서(저장소 상대경로). 시작 HEAD에 있는 파일만 허용한다. */
  extraDocs?: string[];
}

export const AGENT_LABEL = { codex: 'Codex', claude: 'Claude' } as const;

export async function validateExtraDocs(worktree: string, docs: string[]): Promise<string[]> {
  const out: string[] = [];
  for (const d of docs.map((x) => x.trim()).filter(Boolean)) {
    if (d.startsWith('/') || d.split('/').includes('..') || d.includes('\0') || /[*?[\]]/.test(d)) throw new Error(`읽을 문서 경로가 올바르지 않음: ${d}`);
    const r = await G.git(worktree, 'cat-file', '-e', `HEAD:${d}`);
    if (r.code !== 0) throw new Error(`시작 HEAD에 없는 문서: ${d}`);
    out.push(d);
  }
  return [...new Set(out)];
}

type Ctx = { t: Task; head: string; extra: string[]; main: string; impl: string };

/** 1~2절: 작업 식별, 먼저 확인할 것. 위치·브랜치·SHA 줄은 붙여 넣는 사람이 바로 알아보도록 맨 위에 그대로 둔다. */
function identitySections({ t, head, extra, main, impl }: Ctx): string[] {
  return [
    '작업 위치:', t.worktree, '', `브랜치: ${t.branch}`, `시작 HEAD: ${head}`, `기준 SHA: ${t.baseSha} (계약 커밋 ${t.contractSha})`, '',
    `너는 이 프로젝트의 구현 담당 ${impl}다. 메인 담당 ${main}가 정한 아래 작업 계약 범위에서만 구현하고, 결과를 ${main}가 검토·통합할 수 있게 전달한다.`, '',
    '## 1. 작업 식별', `- task_id: ${t.taskId}`, `- task 문서(계약): ${t.contractPath}`, `- branch: ${t.branch}`, '- worktree: 위 작업 위치', `- base_sha: ${t.baseSha}`, '',
    '## 2. 먼저 확인할 것',
    `- AGENTS.md와 PAIR_CODING.md를 읽고, ${t.contractPath}(작업 계약)${extra.length ? ` 및 ${extra.join(', ')}` : ''}를 따르세요.`,
    '- 현재 branch, HEAD, git status, 수정 대상과 관련 호출자·테스트를 확인하세요.',
    '- 문서와 실제 상태가 다르면 추정해서 진행하지 말고 차이를 보고하세요. 기존 미커밋·미추적 작업을 임의로 삭제하거나 reset/stash/rebase하지 마세요.',
    '- 계약 파일은 수정하지 마세요.' + (t.prompt.trim() ? ' 상세 지시는 계약 파일의 "상세 지시" 절에 있습니다.' : ''), '',
  ];
}

/**
 * ./develop 안내. 수동 세션은 AGENTS.md대로 `./develop -- <수정 명령>` 안에서 직접 수정한다.
 * 관제 실행부가 시작하는 에이전트(real·mock)는 이미 실행기가 worktree의 ./develop 잠금으로 감싼 상태이므로 중첩 실행을 요구하지 않는다.
 */
function developLine(t: Task): string {
  if (t.mode === 'manual') return '- card_condition/·tools/experiments/ 파일 수정은 `./develop -- <수정 명령>` 안에서 수행하세요(AGENTS.md). 이 worktree의 자체 `.venv/bin/python`이 필요합니다.';
  return '- 이 실행은 관제 도구가 worktree의 `./develop` 잠금을 획득한 상태로 시작했습니다. `./develop`을 직접 실행하지 말고, 계약의 허용 파일만 Edit/Write로 수정하세요. 잠금 밖에서 별도 프로세스를 만들어 편집하지 마세요.';
}

/** 3~5절: 목표·완료 조건, 파일 소유권, 구현·실행 제한. */
function scopeSections({ t, main }: Ctx): string[] {
  return [
    '## 3. 목표와 완료 조건', '목표:', t.goal, '',
    ...(t.doneCriteria.length ? ['완료 조건:', ...t.doneCriteria.map((c) => `- ${c}`), ''] : []),
    '## 4. 파일 소유권',
    `허용 파일 ${t.allowedFiles.length}개만 변경하세요:`, ...t.allowedFiles.map((f) => `- ${f}`),
    '이 밖의 파일, 다른 worktree, 기본 checkout, 다른 브랜치는 읽기 전용입니다. 허용 범위 밖 변경이 필요하면 이유와 필요한 파일을 보고하세요.',
    '임의 기능 추가, 관련 없는 리팩터링, 새 의존성 추가를 하지 마세요.', '',
    '## 5. 구현·실행 제한',
    '- 배정된 worktree에서만 구현합니다.',
    ...(t.usesDevelopLock ? [developLine(t)] : []),
    '- PAIR_CODING의 구조 기준을 지키세요: 파일당 함수 정의 최대 7개, 주요 호출 전이 최대 4회.',
    '- 합성 fixture·mock으로 가능한 검증을 수행합니다. 사람 라벨·평가 기준·진척 배점은 바꾸지 않습니다.',
    `- 금지: 실제 학습·모델 비교·사진 추론·라벨 수정·외부 AI 호출·자동 교차 검토, 의존성 설치·모델 다운로드, push. main 수정·통합·push는 ${main}가 담당합니다.`, '',
  ];
}

/** 6~8절: 검증, 진행 방식, 산출물·커밋, 최종 인계 형식. */
function deliverySections({ t, main }: Ctx, o: PromptOptions): string[] {
  const html = t.allowedFiles.some((f) => 'docs/collaboration/'.startsWith(f) || f.startsWith('docs/collaboration/'));
  return [
    '## 6. 검증',
    ...(t.checks.length ? ['검사 (에이전트 종료 후 실행기가 별도로 실행하며, 미실행·실패는 통과가 아닙니다):', ...t.checks.map((c) => `- ${c.name}: ${[c.executable, ...c.args].join(' ')}`)] : []),
    '- `git diff --check`, 변경 파일과 허용 파일 대조, 함수 수와 파일 경계를 넘는 주요 호출 경로 확인.',
    '- 실제 데이터가 필요해 실행하지 못한 검사는 이유를 기록하세요. 합성 테스트 통과를 실제 모델 성능 개선으로 보고하지 마세요.', '',
    '## 7. 진행 방식',
    '단계별로 커밋하고 다음 단계로 계속 진행하세요. 어떤 항목이 막히면 사유를 기록하고 독립 작업을 이어가세요.',
    '문서 검토·상태 보고서만으로 끝내지 마세요. 계약과 읽을 문서에서 구현할 단일 대상을 정하고 코드·테스트·커밋까지 진행하세요.',
    '이 worktree에는 data·artifacts가 없습니다. 그 내용이 필요한 근거는 계약·읽을 문서에 있는 것만 쓰고, 정답·수치를 추정하지 마세요.',
    '구현할 대상을 정할 근거가 계약에 없으면 임의로 기능을 만들지 말고, 필요한 계약 보완을 한 줄로 보고한 뒤 종료하세요(보고서를 여러 개 만들지 마세요).',
    '모르는 사실이나 사람 판단이 필요한 항목은 그 항목만 미해결로 남기고 독립 단계는 계속하세요. 커밋은 의미 단위로 하고 `git add .`로 전체를 올리지 마세요.',
    '이미 있는 untracked 파일을 빈 작업물로 보고 삭제·초기화하지 마세요. 인계에는 함수 수·호출 깊이 제한 대비 변경 전·후 수치를 적고, 정적으로 확정하지 못한 것은 미확인으로 적으세요.',
    ...(o.unattended ? ['사용자는 자리에 없습니다. 사람 정답을 추정하거나 재요청하지 마세요.'] : []), '',
    '## 8. 산출물·커밋·최종 인계',
    '- 허용된 파일만 명시적으로 `git add` 하고, 완료 후 같은 브랜치에 추가 커밋을 하지 마세요.',
    ...(html ? ['- 허용 범위 안에서 실제 결과·미검증·리스크를 docs/collaboration/reports/ 아래에 기록하고, docs/collaboration/HTML_REPORTING.md가 요구하면 HTML 경로와 열기·렌더 확인 결과를 구분해 적으세요.'] : []),
    `완료하면 아래를 한 번에 인계하세요. main 통합과 push는 ${main}가 담당합니다.`,
    '- task_id / branch / base_sha, 최종 전체 커밋 SHA와 적용 순서, 변경 파일 목록',
    '- 핵심 diff와 변경 이유, 파일별 함수 수 전·후와 주요 호출 전이',
    '- 실행한 검사 명령과 실제 결과, 미실행·미검증 항목과 이유',
    `- 리스크와 사이드이펙트, 롤백 방법, ${main}가 통합 후 확인해야 할 항목`,
  ];
}

export async function buildStartPrompt(t: Task, mainAgent: 'codex' | 'claude', o: PromptOptions = {}) {
  const head = await G.revParse(t.worktree, 'HEAD');
  if (!head) throw new Error('worktree HEAD를 읽지 못함');
  const extra = await validateExtraDocs(t.worktree, [...(t.readDocs ?? []), ...(o.extraDocs ?? [])]);
  const c: Ctx = { t, head, extra, main: AGENT_LABEL[mainAgent], impl: AGENT_LABEL[t.agent] };
  return { text: [...identitySections(c), ...scopeSections(c), ...deliverySections(c, o)].join('\n'), head, extraDocs: extra };
}

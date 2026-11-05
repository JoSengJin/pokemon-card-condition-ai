import type { Task } from './executor.ts';

export type Ctx = { t: Task; head: string; extra: string[]; main: string; impl: string };

export function identitySections({ t, head, extra, main, impl }: Ctx): string[] {
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

export function developLine(t: Task): string {
  if (t.mode === 'manual') return '- card_condition/·tools/experiments/ 파일 수정은 `./develop -- <수정 명령>` 안에서 수행하세요(AGENTS.md). 이 worktree의 자체 `.venv/bin/python`이 필요합니다.';
  return '- 이 실행은 관제 도구가 worktree의 `./develop` 잠금을 획득한 상태로 시작했습니다. `./develop`을 직접 실행하지 말고, 계약의 허용 파일만 Edit/Write로 수정하세요. 잠금 밖에서 별도 프로세스를 만들어 편집하지 마세요.';
}

export function scopeSections({ t, main }: Ctx): string[] {
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

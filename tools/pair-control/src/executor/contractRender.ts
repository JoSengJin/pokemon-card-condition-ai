import type { CheckSpecT, TaskInputT } from './contract.ts';

export function checkLine(c: CheckSpecT) {
  return `- \`${c.id}\` ${c.name}: \`${[c.executable, ...c.args].join(' ')}\` (cwd \`${c.cwd}\`)`;
}

export function renderContract(t: TaskInputT): string {
  const machine = {
    task_id: t.taskId, owner: t.agent, branch: t.branch, base_sha: t.baseSha, mode: t.mode, goal: t.goal,
    done_criteria: t.doneCriteria, allowed_files: t.allowedFiles, conflict_groups: t.conflictGroups, env: t.env,
    required_modules: t.requiredModules, checks: t.checks, post_checks: t.postChecks,
    // 값이 있을 때만 넣어, 읽을 문서가 없는 기존 계약의 내용(해시)은 바뀌지 않는다.
    ...(t.readDocs?.length ? { read_docs: t.readDocs } : {}),
  };
  const list = (xs: string[], empty: string) => (xs.length ? '- ' + xs.join('\n- ') : `- ${empty}`);
  return `# 작업 계약: ${t.taskId}

pair-control이 작업 준비 시 작업 브랜치에 커밋한 계약이다. 실행·검사·승인은 이 파일의 커밋 SHA와 내용 해시를 기준으로 한다.
에이전트는 이 파일을 수정하지 않는다(수정하면 Git 계약 검사가 실패한다).

- task_id: \`${t.taskId}\`
- owner: ${t.agent}
- branch: \`${t.branch}\`
- base_sha: \`${t.baseSha}\`
- worktree: 로컬 경로는 커밋하지 않음
- 실행 환경: ${t.env}${t.requiredModules.length ? ` (필요 모듈: ${t.requiredModules.join(', ')})` : ''}

## 목표

${t.goal}

## 완료 조건

${list(t.doneCriteria, '(지정 없음)')}

${t.readDocs?.length ? `## 읽을 문서

${list(t.readDocs.map((f) => `\`${f}\``), '')}

` : ''}## allowed_files

${list(t.allowedFiles.map((f) => `\`${f}\``), '(없음)')}

이 목록 밖 파일은 수정하지 않는다. 데이터·라벨·모델·비밀 설정은 다루지 않는다.

## 작업 테스트 (에이전트 종료 후 실행기가 별도 실행)

${t.checks.length ? t.checks.map(checkLine).join('\n') : '- (지정 없음 — 승인 불가)'}

## 통합 후 검사 (통합 checkout에서 실행)

${t.postChecks.length ? t.postChecks.map(checkLine).join('\n') : '- (지정 없음 — 통합 후 검사 미실행으로 표시)'}

## 상세 지시

${t.prompt.trim() || '(없음)'}

## 금지

학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토·외부 AI 호출·의존성 설치·push를 하지 않는다.

## 기계 판독용

\`\`\`json
${JSON.stringify(machine, null, 2)}
\`\`\`
`;
}

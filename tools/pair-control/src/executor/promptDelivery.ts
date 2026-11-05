import type { Ctx } from './promptIdentityScope.ts';
import type { PromptOptions } from './promptBuild.ts';

export function deliverySections({ t, main }: Ctx, o: PromptOptions): string[] {
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

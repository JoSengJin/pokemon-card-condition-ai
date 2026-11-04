import * as G from './git.ts';
import type { Task } from './executor.ts';

export async function handoffText(t: Task, head: string, main: 'codex' | 'claude'): Promise<string> {
  const log = (await G.run('git', ['log', '--reverse', '--format=%H%x09%P%x09%s', `${t.contractSha}..${head}`], t.worktree)).stdout.trim().split('\n').filter(Boolean);
  const rows = log.map((l, i) => { const [sha, parents, subject] = l.split('\t'); return `${i + 1}. \`${sha}\` ← \`${parents || '-'}\` ${subject}`; });
  const r = t.result!;
  const v = t.verification && t.verification.sha === head && t.verification.contractHash === t.contractHash ? t.verification : null;
  const rv = t.review && t.review.sha === head ? t.review : null;
  return `# 인계: ${t.taskId}

- 구현 담당: ${t.agent} → 메인(확인·통합·푸시 담당): ${main}
- 브랜치: \`${t.branch}\`
- 작업 위치(로컬 경로, 커밋하지 않음): ${t.worktree}
- 기준 SHA: \`${t.baseSha}\`
- 계약: \`${t.contractPath}\` @ \`${t.contractSha}\` (해시 \`${t.contractHash.slice(0, 16)}…\`)
- 인계 대상 전체 SHA: \`${head}\`

## 커밋 순서 (전체 SHA ← 부모, 계약 커밋 이후)

${rows.join('\n') || '(없음)'}

## 변경 파일 (계약 커밋 이후)

${r.changedFiles.map((f) => `- ${f}`).join('\n') || '- (없음)'}

## 검사 결과

- Git 계약 검사: ${r.checksPassed ? '통과' : '**실패**'} — 형식(브랜치·계약 불변·허용 파일·미커밋 없음)만 확인하며 코드의 정확성을 뜻하지 않음
${r.checks.map((c) => `  - ${c.ok ? '✓' : '✗'} ${c.name}: ${c.detail}`).join('\n')}
- 작업 테스트: ${v ? `${v.status} (SHA ${v.sha.slice(0, 12)})` : '**미실행 또는 이전 SHA 결과 — 통과가 아님**'}
${v ? v.items.map((i) => `  - ${i.name}: ${i.status} code ${i.exitCode ?? '-'}`).join('\n') : ''}
- 독립 리뷰: ${rv ? `${rv.status}${rv.verdict ? ` / ${rv.verdict}` : ''} (${rv.reviewer}, ${rv.mode})` : '미실행'}

## 미검증·한계

${t.agent === main ? '- **구현 담당과 메인이 같은 에이전트다 — 이 확인은 독립 확인이 아니다.**\n' : ''}- 이 문서는 도구가 만든 상태 요약이다. 에이전트의 서술 보고서(있다면 \`docs/collaboration/reports/\` 아래)는 읽지 않았다.
- 실제 학습·추론·성능 평가는 이 단계에서 하지 않았다.

## 롤백

- 통합 전: 작업 브랜치는 그대로 두고 거절하면 된다(삭제하지 않음).
- 통합 후: \`./develop -- git revert <통합 커밋 SHA>\` (PAIR_CODING §5).

## 메인(${main})이 할 일

1. \`git diff ${t.baseSha}..${head}\` 로 계약 대조(허용 파일, 완료 조건).
2. 이 SHA·계약 해시가 바뀌면 이 인계는 낡은 것이다. 새 인계를 받는다.
3. 통합·푸시는 사용자가 /pair 화면에서 승인한 SHA만 진행한다.
`;
}

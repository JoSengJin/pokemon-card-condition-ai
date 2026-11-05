import { limitOf } from './executorLookup.ts';
import { taskLine } from './mainRoleTaskLine.ts';
import { turnOf } from './executorView.ts';
import type { Executor } from './executor.ts';

export function memo(ex: Executor, from: 'codex' | 'claude', to: 'codex' | 'claude', reason: string, at: string): string {
  const tasks = Object.values(ex.state.tasks).sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  const open = tasks.filter((t) => !['integrated', 'rejected', 'abandoned', 'cancelled'].includes(t.status));
  const reHandoff = tasks.filter((t) => t.handoff && !t.handoff.cancelledAt && t.handoff.to === from && t.status === 'review_pending');
  const pushes = Object.values(ex.state.pushes ?? {}).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 5);
  const openLines = [];
  for (const task of open) openLines.push(taskLine(task, turnOf(task)));
  return `# 메인 역할 이양: ${from} → ${to}

- 시각: ${at}
- 사유: ${reason || '(미기재)'}
- 주의: 이 기록은 도구의 표시일 뿐이며 권한을 강제하지 않는다. PAIR_CODING.md/AGENTS.md가 정한 역할 규칙은 바뀌지 않았다. 새 메인(${to})에게는 사용자가 한 줄로 알려야 한다.
- 한도 상태: ${limitOf(ex)?.detail ?? '도달 없음'}

## 진행 중인 작업

${openLines.join('\n') || '- 없음'}

## 새 메인에게 다시 전달해야 하는 인계

${reHandoff.map((t) => `- \`${t.taskId}\`: 이전 메인(${from})에게 인계됨 → ${to}에게 인계 안내문을 다시 전달(작업 화면의 "안내문 복사")`).join('\n') || '- 없음'}

## 최근 푸시·되돌림

${pushes.map((p) => `- ${p.kind} ${p.status} ${p.preRemoteHead.slice(0, 12)} → ${p.pushedSha.slice(0, 12)} (${p.at})${p.revert ? ` · 되돌림 준비 ${p.revert.pushedAs ? '완료' : '대기'}` : ''}`).join('\n') || '- 없음'}

## 새 메인이 확인할 것

1. 위 작업의 diff·검사 결과는 /pair 화면에서 확인한다(인계 문서는 상태 폴더에 있음).
2. 실제 학습·모델 비교·사진 추론은 기본 checkout에서 한 명만 실행한다(AGENTS.md). 이양 시점에 실행 중인 것이 없음을 도구가 확인했다.
`;
}

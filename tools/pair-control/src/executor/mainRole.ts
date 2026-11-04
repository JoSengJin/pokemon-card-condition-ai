import { turnOf } from './executorView.ts';
// 메인 역할(통합·푸시·실험 단일 담당) 표시와 이양 기록.
// 이 도구는 누가 클릭하는지 모르므로 권한을 강제하지 못한다. 하는 일: 이양 전 안전 확인, 이양 기록, 인계 메모, 이후 인계·프롬프트 문구에 현재 메인 반영.
// PAIR_CODING.md·AGENTS.md는 main 통합·실험을 Codex로 정해 두었다. 그 규칙은 바꾸지 않으며, 이양은 사용자가 규칙을 바꾸거나 한시적으로 허용했을 때만 의미가 있다.
import fs from 'node:fs';
import path from 'node:path';
import { run } from './git.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { UserError, type Executor, type MainRole } from './executor.ts';

export const MAIN_CHOICES = ['codex', 'claude'] as const;

/** 이양을 막는 상태. 하나라도 있으면 이양하지 않는다(진행 중인 일의 책임자가 바뀌면 안 됨). */
export async function swapBlockers(ex: Executor): Promise<string[]> {
  const b: string[] = [];
  for (const t of Object.values(ex.state.tasks)) {
    if (['integrating', 'starting', 'collecting', 'cancelling'].includes(t.status)) b.push(`작업 ${t.taskId}: ${t.status} 진행 중`);
    if (t.verification?.status === 'running') b.push(`작업 ${t.taskId}: 작업 테스트 실행 중`);
    if (t.review?.status === 'running') b.push(`작업 ${t.taskId}: 리뷰 실행 중`);
  }
  for (const e of Object.values(ex.state.executions)) {
    if (['running', 'cancelling'].includes(e.status)) b.push(`프로세스 실행 중: ${e.kind ?? 'agent'} ${e.taskId} (PID ${e.pid})`);
  }
  const lock = ex.locks.holder('integration');
  if (lock) b.push(`통합·푸시·되돌림 진행 중: ${JSON.stringify({ kind: lock.kind, taskId: lock.taskId })}`);
  for (const r of Object.values(ex.state.pushes ?? {})) if (r.status === 'push_unverified') b.push(`푸시 결과 불명(${r.id.slice(0, 8)}) — 원격 확인 후 이양`);
  // 기본 checkout의 ./develop 잠금(실험·검토·편집 공용). 사용 중이면 이양하지 않는다.
  const cwd = ex.cfg.integration.checkout;
  if (cwd && fs.existsSync(path.join(cwd, 'develop')) && fs.existsSync(path.join(cwd, '.venv', 'bin', 'python'))) {
    const r = await run(path.join(cwd, 'develop'), ['--check'], cwd, 20_000, sanitizedChildEnv());
    if (r.code === 1) b.push('기본 checkout의 ./develop 잠금이 사용 중(실험·검토·편집 진행 중)');
    else if (r.code !== 0) b.push(`./develop 잠금을 확인하지 못함(code ${r.code})`);
  }
  return b;
}

function memo(ex: Executor, from: 'codex' | 'claude', to: 'codex' | 'claude', reason: string, at: string): string {
  const tasks = Object.values(ex.state.tasks).sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  const line = (t: (typeof tasks)[number]) => {
    const turn = turnOf(t);
    const h = t.handoff && !t.handoff.cancelledAt ? ` · 인계 대상 ${t.handoff.to}${t.handoff.confirmedAt ? '(확인됨)' : '(확인 전)'}` : '';
    return `- \`${t.taskId}\` [${t.agent}/${t.mode}] ${t.status} · 차례: ${turn.label} → ${turn.next}${h}`;
  };
  const open = tasks.filter((t) => !['integrated', 'rejected', 'abandoned', 'cancelled'].includes(t.status));
  const reHandoff = tasks.filter((t) => t.handoff && !t.handoff.cancelledAt && t.handoff.to === from && t.status === 'review_pending');
  const pushes = Object.values(ex.state.pushes ?? {}).sort((a, b) => b.at.localeCompare(a.at)).slice(0, 5);
  return `# 메인 역할 이양: ${from} → ${to}

- 시각: ${at}
- 사유: ${reason || '(미기재)'}
- 주의: 이 기록은 도구의 표시일 뿐이며 권한을 강제하지 않는다. PAIR_CODING.md/AGENTS.md가 정한 역할 규칙은 바뀌지 않았다. 새 메인(${to})에게는 사용자가 한 줄로 알려야 한다.
- 한도 상태: ${ex.limit ? ex.limit.detail : '도달 없음'}

## 진행 중인 작업

${open.map(line).join('\n') || '- 없음'}

## 새 메인에게 다시 전달해야 하는 인계

${reHandoff.map((t) => `- \`${t.taskId}\`: 이전 메인(${from})에게 인계됨 → ${to}에게 인계 안내문을 다시 전달(작업 화면의 "안내문 복사")`).join('\n') || '- 없음'}

## 최근 푸시·되돌림

${pushes.map((p) => `- ${p.kind} ${p.status} ${p.preRemoteHead.slice(0, 12)} → ${p.pushedSha.slice(0, 12)} (${p.at})${p.revert ? ` · 되돌림 준비 ${p.revert.pushedAs ? '완료' : '대기'}` : ''}`).join('\n') || '- 없음'}

## 새 메인이 확인할 것

1. 위 작업의 diff·검사 결과는 /pair 화면에서 확인한다(인계 문서는 상태 폴더에 있음).
2. 실제 학습·모델 비교·사진 추론은 기본 checkout에서 한 명만 실행한다(AGENTS.md). 이양 시점에 실행 중인 것이 없음을 도구가 확인했다.
`;
}

export async function setMain(ex: Executor, agent: string, reason = '') {
  ex.assertMainActive('메인 표시 변경');
  if (!MAIN_CHOICES.includes(agent as 'codex')) throw new UserError('메인은 codex 또는 claude 중 하나');
  const to = agent as 'codex' | 'claude';
  const from = ex.mainAgent;
  if (to === from) throw new UserError(`이미 ${from}이(가) 메인임`);
  const blockers = await swapBlockers(ex);
  if (blockers.length) throw new UserError(`이양할 수 없음: ${blockers.join(' / ')}`);
  const at = new Date().toISOString();
  const role: MainRole = { agent: to, since: at, reason: reason.slice(0, 300), history: [...(ex.state.main?.history ?? []), { agent: from, until: at }] };
  const file = path.join(ex.cfg.stateDir, 'main-handoffs', `${at.replace(/[:.]/g, '-')}-${from}-to-${to}.md`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const text = memo(ex, from, to, role.reason ?? '', at);
  fs.writeFileSync(file, text);
  role.memoFile = file;
  ex.state.main = role;
  ex.audit('main_swapped', { from, to, reason: role.reason, memoFile: file });
  ex.store.save();
  return { role, memo: text };
}

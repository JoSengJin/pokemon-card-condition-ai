import { memo } from './mainRoleMemo.ts';
import { assertMainActive } from './executorPolicy.ts';
// 메인 역할(통합·푸시·실험 단일 담당) 표시와 이양 기록.
// 이 도구는 누가 클릭하는지 모르므로 권한을 강제하지 못한다. 하는 일: 이양 전 안전 확인, 이양 기록, 인계 메모, 이후 인계·프롬프트 문구에 현재 메인 반영.
// 표시 변경은 실행 세션 인수가 아니다. 실제 메인 교대는 PAIR_CODING.md §7의 체크포인트·세대·승인 승계 절차를 따른다.
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


export async function setMain(ex: Executor, agent: string, reason = '') {
  assertMainActive(ex, '메인 표시 변경');
  const generation = ex.runtime.generation, previous = ex.state.main;
  if (!MAIN_CHOICES.includes(agent as 'codex')) throw new UserError('메인은 codex 또는 claude 중 하나');
  const to = agent as 'codex' | 'claude';
  const from = ex.mainAgent;
  if (to === from) throw new UserError(`이미 ${from}이(가) 메인임`);
  const blockers = await swapBlockers(ex);
  if (blockers.length) throw new UserError(`이양할 수 없음: ${blockers.join(' / ')}`);
  assertMainActive(ex, '메인 표시 변경', generation);
  if (ex.state.main !== previous) throw new UserError('준비 중 메인 표시가 바뀜 — 다시 확인하세요');
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

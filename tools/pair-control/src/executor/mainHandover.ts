// 메인 역할 교대: 새 배정·상태 변경 정지 → 체크포인트 저장 → 새 메인 프로세스 실행 → 인수 확인(체크포인트·실제 Git 대조) → 승인 범위 안의 다음 행동.
// "교대 완료"는 인수 확인과 다음 행동 수행 근거가 있을 때만 표시한다(completed). 표시 이름 변경이나 프로세스 시작만으로는 완료가 아니다.
// 실패(실행 불가·한도·확인 불일치·결과 불명)는 상태와 복구 지점(체크포인트)을 남기고 끝낸다. 자동 재시도 루프는 없다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import { inheritable } from './mainApprovals.ts';
import { applyActions } from './mainActions.ts';
import { saveCheckpoint } from './mainCheckpoint.ts';
import { parseResult, tokenHash, verifyAck, writeBundle, type TakeoverResult } from './mainTakeover.ts';
import { swapBlockers } from './mainRole.ts';
import { UserError, type Execution, type Executor } from './executor.ts';
import type { Agent, MainSession } from './mainTypes.ts';

/** 일반 교대를 막는 상태. 기존 이양 차단 조건에서 "진행 중인 구현 에이전트"만 뺀다(중단하지 않고 담당·결과를 인수하므로). */
export async function handoverBlockers(ex: Executor): Promise<string[]> {
  return (await swapBlockers(ex)).filter((b) => !b.startsWith('프로세스 실행 중: agent '));
}

function failSession(ex: Executor, s: MainSession, reason: string) {
  const rt = ex.runtime;
  s.status = 'failed'; s.failure = reason;
  rt.history.push(s); rt.session = null; rt.frozen = false;
  rt.failures.push({ at: new Date().toISOString(), reason, checkpointFile: s.checkpointFile });
  ex.audit('main_handover_failed', { session: s.id, to: s.agent, reason, checkpointFile: s.checkpointFile });
  ex.store.save();
  return { ok: false as const, status: 'failed' as const, detail: reason, sessionId: s.id, checkpointFile: s.checkpointFile };
}

/**
 * 메인을 `to`로 교대한다. limit=true는 지금 메인이 한도로 더 못 일하는 경우(마지막 인계문 없이 저장된 상태에서 복구)이며 기다리지 않는다.
 * 새 메인 프로세스가 시작되면 'launching'을 돌려주고, 인수 확인은 프로세스 종료 때(onMainEnd) 이어진다.
 */
export async function handoverMain(ex: Executor, toRaw: string, opts: { reason?: string; limit?: boolean } = {}) {
  if (toRaw !== 'codex' && toRaw !== 'claude') throw new UserError('메인은 codex 또는 claude 중 하나');
  const to = toRaw as Agent, from = ex.mainAgent, rt = ex.runtime;
  if (to === from) throw new UserError(`이미 ${from}이(가) 메인임`);
  if (rt.frozen || rt.session?.status === 'launching') throw new UserError('메인 교대가 이미 진행 중 — 끝난 뒤 다시 시도');
  const now = new Date().toISOString();
  if (opts.limit) rt.limited[from] ??= { at: now, detail: opts.reason || '메인 한도 소진 보고(사용자)' };
  const lim = rt.limited[to] ?? ex.limit;
  if (lim) {
    rt.failures.push({ at: now, reason: `대상 ${to} 사용 불가(한도): ${lim.detail}` });
    ex.audit('main_handover_blocked', { to, detail: lim.detail, bothLimited: !!(rt.limited[from] && rt.limited[to]) });
    ex.store.save();
    return { ok: false as const, status: rt.limited[from] && rt.limited[to] ? 'blocked_both_limited' as const : 'blocked_target_limited' as const, detail: lim.detail };
  }
  if (!opts.limit) { const b = await handoverBlockers(ex); if (b.length) throw new UserError(`교대할 수 없음: ${b.join(' / ')}`); }
  rt.frozen = true; // 이 줄부터 이전 메인의 배정·승인·통합은 받지 않는다
  const cp = await saveCheckpoint(ex, opts.limit ? 'limit-recovery' : 'handover');
  const token = crypto.randomUUID();
  const s: MainSession = { id: crypto.randomUUID(), agent: to, from, generation: rt.generation + 1, status: 'launching', startedAt: now, limitRecovery: !!opts.limit,
    checkpointFile: cp.file, checkpointHash: cp.hash, tokenHash: tokenHash(token), actionResults: [] };
  rt.session = s;
  ex.audit('main_handover_started', { session: s.id, from, to, generation: s.generation, limitRecovery: s.limitRecovery, checkpointFile: cp.file });
  ex.store.save();
  try {
    const b = writeBundle(ex, s, token, [...new Set(inheritable(ex, s.id).flatMap((a) => a.actions))]);
    s.execId = await ex.launchMainProcess({ agent: to, bundleDir: b.bundleDir, prompt: b.prompt, sessionId: s.id });
  } catch (e) { return failSession(ex, s, `새 메인 실행 실패: ${(e as Error).message}`); }
  ex.store.save();
  return { ok: true as const, status: 'launching' as const, sessionId: s.id, generation: s.generation, checkpointFile: cp.file };
}

/** 인수 확인이 끝난 뒤: 메인을 바꾸고 세대를 올리고 정지를 풀며, 새 메인이 낸 행동을 수행해 completed/idle로 마무리한다. */
async function ackSession(ex: Executor, s: MainSession, res: TakeoverResult) {
  const rt = ex.runtime, at = new Date().toISOString();
  ex.state.main = { agent: s.agent, since: at, reason: s.limitRecovery ? '한도 소진 복구' : '교대', history: [...(ex.state.main?.history ?? []), { agent: s.from, until: at }], memoFile: s.checkpointFile, generation: s.generation };
  rt.generation = s.generation; rt.frozen = false; s.status = 'taken_over'; s.ackedAt = at;
  ex.audit('main_taken_over', { session: s.id, agent: s.agent, generation: s.generation });
  ex.store.save();
  const results = await applyActions(ex, s, res.actions ?? []);
  const did = results.some((r) => r.ok && r.type !== 'note');
  s.status = did ? 'completed' : 'idle';
  if (did) s.completedAt = new Date().toISOString();
  ex.audit('main_handover_finished', { session: s.id, status: s.status, actions: results.length, done: results.filter((r) => r.ok).length });
  ex.store.save();
}

/** 새 메인 프로세스가 끝났을 때(감시 루프가 호출). 이전 세대의 늦은 결과는 아무것도 바꾸지 못한다. */
export async function onMainEnd(ex: Executor, exec: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
  const rt = ex.runtime, s = rt.session;
  if (!s || s.execId !== exec.execId || s.status !== 'launching') { ex.audit('main_stale_result_rejected', { execId: exec.execId, session: exec.runId }); ex.store.save(); return; }
  if (rt.limited[s.agent] && rt.limited[s.agent]!.at >= s.startedAt) { failSession(ex, s, `새 메인(${s.agent}) 한도 소진 — 상태·체크포인트 보존, 재시도하지 않음`); return; }
  if (r.unknown || r.cancelled || r.code !== 0) { failSession(ex, s, r.unknown ? '새 메인 프로세스가 종료 기록 없이 사라짐(결과 불명) — 같은 요청을 다시 보내지 않음' : r.cancelled ? '새 메인 실행이 중단됨' : `새 메인 종료코드 ${r.code}`); return; }
  const res = parseResult(fs.existsSync(exec.logPath) ? fs.readFileSync(exec.logPath, 'utf8') : '');
  if (!res) { failSession(ex, s, '새 메인의 결과 JSON을 읽지 못함 — 인수하지 않음'); return; }
  const cp = JSON.parse(fs.readFileSync(s.checkpointFile, 'utf8')) as { tasks: { taskId: string }[] };
  const bad = await verifyAck(ex, s, res, cp.tasks);
  if (bad.length) { failSession(ex, s, `인수 확인 불일치: ${bad.join('; ')}`); return; }
  await ackSession(ex, s, res);
}

/** 메인 세션 프로세스가 한도 문구를 냈을 때: 그 에이전트만 막는다. 진행 중인 구현 에이전트는 중단하지 않는다. */
export function onMainLimit(ex: Executor, agent: Agent, detail: string) {
  ex.runtime.limited[agent] ??= { at: new Date().toISOString(), detail };
  ex.audit('main_limit', { agent, detail });
  ex.store.save();
}

/** 사용자가 그 에이전트의 한도가 풀렸음을 확인했을 때만 호출한다. */
export function clearAgentLimit(ex: Executor, agent: Agent) {
  if (!ex.runtime.limited[agent]) throw new UserError(`${agent}은(는) 한도 상태가 아님`);
  delete ex.runtime.limited[agent];
  ex.audit('main_limit_cleared', { agent });
  ex.store.save();
}

// 메인 역할 교대: 새 배정·상태 변경 정지 → 체크포인트 저장 → 새 메인 프로세스 실행 → 인수 확인(체크포인트·실제 Git 대조, mainAck.ts) → 승인 범위 안의 다음 행동.
// "교대 완료"는 인수 확인과 다음 행동 수행 근거가 있을 때만 표시한다(completed). 표시 이름 변경이나 프로세스 시작만으로는 완료가 아니다.
// 실패(실행 불가·한도·확인 불일치·결과 불명)는 상태와 복구 지점(체크포인트)을 남기고 끝낸다. 자동 재시도 루프는 없다.
import crypto from 'node:crypto';
import { modelActions } from './mainApprovals.ts';
import { saveCheckpoint } from './mainCheckpoint.ts';
import { lock } from './mainSerial.ts';
import { tokenHash, writeBundle } from './mainTakeover.ts';
import { swapBlockers } from './mainRole.ts';
import { UserError, type Executor } from './executor.ts';
import type { Agent, MainSession } from './mainTypes.ts';

export { clearAgentLimit } from './limitScope.ts';

/** 일반 교대를 막는 상태. 기존 이양 차단 조건에서 "진행 중인 구현 에이전트"만 뺀다(중단하지 않고 담당·결과를 인수하므로). */
export async function handoverBlockers(ex: Executor): Promise<string[]> {
  return (await swapBlockers(ex)).filter((b) => !b.startsWith('프로세스 실행 중: agent '));
}

export function failSession(ex: Executor, s: MainSession, reason: string) {
  const rt = ex.runtime;
  s.status = 'failed'; s.failure = reason;
  rt.history.push(s); rt.session = null; rt.frozen = false;
  rt.failures.push({ at: new Date().toISOString(), reason, checkpointFile: s.checkpointFile });
  ex.audit('main_handover_failed', { session: s.id, to: s.agent, reason, checkpointFile: s.checkpointFile });
  ex.store.save();
  return { ok: false as const, status: 'failed' as const, detail: reason, sessionId: s.id, checkpointFile: s.checkpointFile };
}

/**
 * 교대를 시작해도 되는지. 막히면 결과(차단 사유)를, 시작할 수 있으면 {to, from}을 돌려준다.
 * 대상 공급자의 한도(runtime.limited[to]) 또는 출처 불명의 전역 한도가 있으면 막는다. 다른 공급자의 worker 한도는 막지 않는다.
 * limit=true는 지금 메인이 한도로 더 못 일하는 경우(마지막 인계문 없이 저장된 상태에서 복구)이며 기다리지 않는다.
 */
async function handoverGate(ex: Executor, toRaw: string, opts: { reason?: string; limit?: boolean }) {
  if (toRaw !== 'codex' && toRaw !== 'claude') throw new UserError('메인은 codex 또는 claude 중 하나');
  const to = toRaw as Agent, from = ex.mainAgent, rt = ex.runtime;
  if (to === from) throw new UserError(`이미 ${from}이(가) 메인임`);
  if (rt.frozen || rt.session?.status === 'launching') throw new UserError('메인 교대가 이미 진행 중 — 끝난 뒤 다시 시도');
  if (opts.limit) rt.limited[from] ??= { at: new Date().toISOString(), detail: opts.reason || '메인 한도 소진 보고(사용자)' };
  const lim = rt.limited[to] ?? ex.limit;
  if (lim) {
    rt.failures.push({ at: new Date().toISOString(), reason: `대상 ${to} 사용 불가(한도): ${lim.detail}` });
    ex.audit('main_handover_blocked', { to, detail: lim.detail, bothLimited: !!(rt.limited[from] && rt.limited[to]) });
    ex.store.save();
    return { ok: false as const, status: rt.limited[from] && rt.limited[to] ? 'blocked_both_limited' as const : 'blocked_target_limited' as const, detail: lim.detail };
  }
  if (!opts.limit) { const b = await handoverBlockers(ex); if (b.length) throw new UserError(`교대할 수 없음: ${b.join(' / ')}`); }
  return { to, from };
}

/** 새 메인 세션을 기록하고 입력 묶음을 만들어 프로세스를 시작한다. 시작하지 못하면 세션을 실패로 남긴다(체크포인트 보존). */
async function launchSession(ex: Executor, who: { to: Agent; from: Agent }, cp: { file: string; hash: string }, opts: { limit?: boolean }) {
  const rt = ex.runtime, token = crypto.randomUUID();
  const s: MainSession = { id: crypto.randomUUID(), agent: who.to, from: who.from, generation: rt.generation + 1, status: 'launching', startedAt: new Date().toISOString(), limitRecovery: !!opts.limit,
    checkpointFile: cp.file, checkpointHash: cp.hash, tokenHash: tokenHash(token), actionResults: [] };
  rt.session = s;
  ex.audit('main_handover_started', { session: s.id, from: who.from, to: who.to, generation: s.generation, limitRecovery: s.limitRecovery, checkpointFile: cp.file });
  ex.store.save();
  try {
    const b = writeBundle(ex, s, token, modelActions(ex, s.id));
    s.execId = await ex.launchMainProcess({ agent: who.to, bundleDir: b.bundleDir, prompt: b.prompt, sessionId: s.id });
  } catch (e) { return failSession(ex, s, `새 메인 실행 실패: ${(e as Error).message}`); }
  ex.store.save();
  return { ok: true as const, status: 'launching' as const, sessionId: s.id, generation: s.generation, checkpointFile: cp.file };
}

/**
 * 메인을 `to`로 교대한다(교대는 lock으로 행동 수행과 한 줄에 선다).
 * 새 메인 프로세스가 시작되면 'launching'을 돌려주고, 인수 확인은 프로세스 종료 때(onMainEnd) 이어진다.
 */
export async function handoverMain(ex: Executor, toRaw: string, opts: { reason?: string; limit?: boolean } = {}) {
  const release = await lock(ex);
  try {
    const gate = await handoverGate(ex, toRaw, opts);
    if ('status' in gate) return gate;
    ex.runtime.frozen = true; // 이 줄부터 이전 메인의 배정·승인·통합은 받지 않는다
    return await launchSession(ex, gate, await saveCheckpoint(ex, opts.limit ? 'limit-recovery' : 'handover'), opts);
  } finally { release(); }
}

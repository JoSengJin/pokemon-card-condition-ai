// 메인 역할 교대: 새 배정·상태 변경 정지 → 체크포인트 저장 → 새 메인 프로세스 실행 → 인수 확인(체크포인트·실제 Git 대조, mainAck.ts) → 승인 범위 안의 다음 행동.
// "교대 완료"는 인수 확인과 다음 행동 수행 근거가 있을 때만 표시한다(completed). 표시 이름 변경이나 프로세스 시작만으로는 완료가 아니다.
// 실패(실행 불가·한도·확인 불일치·결과 불명)는 상태와 복구 지점(체크포인트)을 남기고 끝낸다. 자동 재시도 루프는 없다.
import crypto from 'node:crypto';
import { modelActions } from './mainApprovals.ts';
import { saveCheckpoint } from './mainCheckpoint.ts';
import { manualGate } from './mainHandoverGate.ts';
import { lock } from './mainSerial.ts';
import { tokenHash, writeBundle } from './mainTakeover.ts';
import { swapBlockers } from './mainRole.ts';
import type { Executor } from './executor.ts';
import type { Agent, MainSession } from './mainTypes.ts';

export { clearAgentLimit } from './limitScope.ts';

/** UI에 일반 교대 차단 사유를 보여 준다. 진행 중 구현 에이전트는 인수 대상이므로 제외한다. */
export async function handoverBlockers(ex: Executor): Promise<string[]> {
  return (await swapBlockers(ex)).filter((reason) => !reason.startsWith('프로세스 실행 중: agent '));
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

/** 새 메인 세션과 입력 묶음을 저장한다. CLI 확인과 실행은 다음 감시 틱의 launchStage가 각각 진행한다. */
export function prepareSession(ex: Executor, who: { to: Agent; from: Agent }, cp: { file: string; hash: string }, opts: { limit?: boolean }) {
  const rt = ex.runtime, token = crypto.randomUUID();
  const s: MainSession = { id: crypto.randomUUID(), agent: who.to, from: who.from, generation: rt.generation + 1, status: 'launching', startedAt: new Date().toISOString(), limitRecovery: !!opts.limit,
    checkpointFile: cp.file, checkpointHash: cp.hash, tokenHash: tokenHash(token), actionResults: [], launchStage: 'probe', launchLifetime: ex.lifetime };
  rt.session = s;
  ex.audit('main_handover_started', { session: s.id, from: who.from, to: who.to, generation: s.generation, limitRecovery: s.limitRecovery, checkpointFile: cp.file });
  const b = writeBundle(ex, s, token, modelActions(ex, s.id));
  s.bundleDir = b.bundleDir; s.launchPrompt = b.prompt;
  ex.store.save();
  ex.ensureWatcher();
  return { ok: true as const, status: 'launching' as const, sessionId: s.id, generation: s.generation, checkpointFile: cp.file };
}

/**
 * 메인을 `to`로 교대한다(교대는 lock으로 행동 수행과 한 줄에 선다).
 * 새 메인 프로세스가 시작되면 'launching'을 돌려주고, 인수 확인은 프로세스 종료 때(onMainEnd) 이어진다.
 */
export async function handoverMain(ex: Executor, toRaw: string, _opts: { reason?: string } = {}) {
  const release = await lock(ex);
  try {
    const gate = await manualGate(ex, toRaw);
    if ('status' in gate) return gate;
    ex.runtime.frozen = true; // 이 줄부터 이전 메인의 배정·승인·통합은 받지 않는다
    return prepareSession(ex, gate, await saveCheckpoint(ex, 'handover'), {});
  } finally { release(); }
}

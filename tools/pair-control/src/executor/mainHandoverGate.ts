// 메인 교대 대상과 공급자별 한도를 한 곳에서 판정한다. 일반 교대만 추가 작업 차단 상태를 확인한다.
import { swapBlockers } from './mainRole.ts';
import { UserError, type Executor } from './executor.ts';
import type { Agent } from './mainTypes.ts';

export async function targetGate(ex: Executor, toRaw: string, limitReason?: string) {
  if (toRaw !== 'codex' && toRaw !== 'claude') throw new UserError('메인은 codex 또는 claude 중 하나');
  const to = toRaw as Agent, from = ex.mainAgent, rt = ex.runtime;
  if (to === from) throw new UserError(`이미 ${from}이(가) 메인임`);
  if (rt.frozen || rt.session?.status === 'launching') throw new UserError('메인 교대가 이미 진행 중 — 끝난 뒤 다시 시도');
  if (limitReason !== undefined) rt.limited[from] ??= { at: new Date().toISOString(), detail: limitReason || '메인 한도 소진 보고(사용자)' };
  const lim = rt.limited[to] ?? ex.limit;
  if (!lim) return { to, from };
  rt.failures.push({ at: new Date().toISOString(), reason: `대상 ${to} 사용 불가(한도): ${lim.detail}` });
  ex.audit('main_handover_blocked', { to, detail: lim.detail, bothLimited: !!(rt.limited[from] && rt.limited[to]) });
  ex.store.save();
  return { ok: false as const, status: rt.limited[from] && rt.limited[to] ? 'blocked_both_limited' as const : 'blocked_target_limited' as const, detail: lim.detail };
}

export async function manualGate(ex: Executor, toRaw: string) {
  const target = await targetGate(ex, toRaw);
  if ('status' in target) return target;
  const blockers = (await swapBlockers(ex)).filter((reason) => !reason.startsWith('프로세스 실행 중: agent '));
  if (blockers.length) throw new UserError(`교대할 수 없음: ${blockers.join(' / ')}`);
  return target;
}

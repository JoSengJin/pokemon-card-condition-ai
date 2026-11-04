// 메인 한도 복구 전용 진입점. 일반 교대의 작업 차단 조회는 건너뛰되 공급자별 한도·잠금·체크포인트는 동일하게 보존한다.
import { saveCheckpoint } from './mainCheckpoint.ts';
import { launchSession } from './mainHandover.ts';
import { targetGate } from './mainHandoverGate.ts';
import { lock } from './mainSerial.ts';
import { mark } from './pipelineState.ts';
import type { Executor } from './executor.ts';

export async function handoverAfterLimit(ex: Executor, to: string, keys: string[], reason: string) {
  const release = await lock(ex);
  try {
    const gate = await targetGate(ex, to, reason);
    if ('status' in gate) {
      mark(ex, keys, 'held', { reason: `한도: ${gate.status}` });
      await saveCheckpoint(ex, 'both-limited');
      return gate;
    }
    ex.runtime.frozen = true;
    const result = await launchSession(ex, gate, await saveCheckpoint(ex, 'limit-recovery'), { limit: true });
    if (result.status !== 'launching') {
      mark(ex, keys, 'held', { reason: `한도: ${result.status}` });
      await saveCheckpoint(ex, 'both-limited');
    }
    return result;
  } finally { release(); }
}

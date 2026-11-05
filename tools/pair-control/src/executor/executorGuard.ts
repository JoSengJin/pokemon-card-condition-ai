import { FreeGuard, type Alert } from './freeGuard.ts';
import { cancelAll } from './taskCancel.ts';
import { onLimitHit } from './limitScope.ts';
import type { Executor } from './executor.ts';

export function createExecutorGuard(ex: Executor, opts: { onTrip?: (alert: Alert) => void }) {
  return new FreeGuard(ex.cfg.stateDir, (alert) => {
    ex.guardAlert = alert;
    ex.audit('free_guard_trip', { ...alert });
    cancelAll(ex, '무료 가드 발동');
    opts.onTrip?.(alert);
  }, (alert) => onLimitHit(ex, alert));
}

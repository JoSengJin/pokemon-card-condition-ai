import { authorize } from './executor/approvalGate.ts';
import { UserError, type Executor } from './executor/executor.ts';
import type { RuntimeOrigin } from './runtimeRequests.ts';

/** 저장 이후 바뀐 메인·승인 장부를 실행 직전에 다시 확인한다. */
export function validateOrigin(ex: Executor, origin?: RuntimeOrigin) {
  if (ex.stopped) throw new UserError('실행기가 정지됨');
  if (!origin) return;
  authorize(ex, origin.sessionId, origin.action, origin.target, origin.sha, origin);
}

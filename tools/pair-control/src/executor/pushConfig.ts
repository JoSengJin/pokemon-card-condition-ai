import { UserError, type Executor } from './executor.ts';

export function checkout(ex: Executor) {
  const c = ex.cfg.integration.checkout;
  if (!c) throw new UserError('config.integration.checkout 미설정');
  return c;
}

export const remoteName = (ex: Executor) => ex.cfg.integration.remote || 'origin';

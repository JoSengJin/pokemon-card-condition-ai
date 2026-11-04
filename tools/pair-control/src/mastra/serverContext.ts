import { refreshProbes } from '../executor/executorView.ts';
import { loadConfig } from '../executor/config.ts';
import { Executor } from '../executor/executor.ts';
import { notifyUser } from '../executor/freeGuard.ts';

export const cfg = loadConfig();
export const HOST = '127.0.0.1';
export const ALLOWED_HOSTS = new Set([`127.0.0.1:${cfg.port}`, `localhost:${cfg.port}`]);
export const ALLOWED_ORIGINS = [`http://127.0.0.1:${cfg.port}`, `http://localhost:${cfg.port}`];

export const executor = new Executor(cfg, {
  onTrip: (alert) => {
    notifyUser('유료 전환 신호 감지 — 서비스 종료', alert.detail);
    setTimeout(() => process.exit(3), 3500).unref?.();
  },
});
executor.guard.checkEnv();
void refreshProbes(executor);

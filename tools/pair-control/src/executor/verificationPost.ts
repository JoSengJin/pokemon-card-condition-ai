import crypto from 'node:crypto';
import path from 'node:path';
import { resolveCheck } from './checkCommand.ts';
import { runLogged } from './logstream.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import type { Executor, Task, CheckRun } from './executor.ts';

export async function runPostChecks(ex: Executor, t: Task, checkout: string, develop: string, vars: { base: string; contract: string; head: string }) {
  const items: CheckRun[] = [];
  if (!t.postChecks.length) return { status: 'not_run' as const, items };
  for (const c of t.postChecks) {
    const r = resolveCheck(checkout, c, vars);
    const item: CheckRun = { id: c.id, name: c.name, display: ['./develop', '--', ...r.display], cwd: '.', status: 'running', sha: vars.head, startedAt: new Date().toISOString() };
    // 화면이 실행 중에도 로그를 이어받도록: 실행 중 항목을 먼저 통합 기록에 남기고, 출력은 줄 단위로 가려 바로 파일에 쓴다.
    item.logPath = path.join(ex.cfg.stateDir, 'runs', `post-${crypto.randomUUID()}.log`);
    t.integration = { ...(t.integration ?? { at: item.startedAt!, outcome: 'integrating', detail: '통합 후 검사 실행 중' }), postStatus: 'running', postChecks: [...items, item] };
    ex.store.save();
    const res = await runLogged(develop, ['--', r.command, ...r.args], checkout, 600_000, sanitizedChildEnv(), item.logPath, redact);
    item.status = res.code === 0 ? 'passed' : 'failed'; item.exitCode = res.code; item.endedAt = new Date().toISOString();
    items.push(item);
  }
  return { status: items.every((i) => i.status === 'passed') ? 'passed' as const : 'failed' as const, items };
}

const SECRET_PATTERNS = [/sk-ant-[A-Za-z0-9_-]{8,}/g, /sk-[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{20,}/g, /Bearer\s+[A-Za-z0-9._-]{16,}/g];
function redact(s: string) { for (const re of SECRET_PATTERNS) s = s.replace(re, '[REDACTED]'); return s; }

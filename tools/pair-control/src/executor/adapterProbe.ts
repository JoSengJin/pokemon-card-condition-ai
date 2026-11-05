import fs from 'node:fs';
import path from 'node:path';
import { run } from './git.ts';
import type { Agent } from './contract.ts';
import type { PairConfig } from './config.ts';

export interface Probe {
  agent: Agent;
  installed: boolean;
  binary: string | null;
  version: string | null;
  verifiedFlags: string[];
  missingFlags: string[];
  note: string;
  checkedAt: string;
  /** 줄 단위 이벤트 출력 옵션(claude --output-format·--verbose, codex --json)이 --help에서 확인됨 */
  stream?: boolean;
  /** codex만: `codex login status` 출력 한 줄(모델 요청 없음). */
  loginStatus?: string;
}

export const REQUIRED: Record<'codex' | 'claude', { help: string[]; flags: string[] }> = {
  codex: { help: ['exec', '--help'], flags: ['--cd', '--sandbox'] },
  claude: { help: ['--help'], flags: ['--print', '--permission-mode', '--allowedTools'] },
};

export const STREAM_FLAGS = { codex: ['--json'], claude: ['--output-format', '--verbose'] };

export async function probe(agent: 'codex' | 'claude', cfg: PairConfig): Promise<Probe> {
  const checkedAt = new Date().toISOString();
  let binary = cfg.cli[agent] || null;
  if (!binary) {
    for (const dir of (process.env.PATH ?? '').split(path.delimiter)) {
      const candidate = path.join(dir, agent);
      try { fs.accessSync(candidate, fs.constants.X_OK); binary = candidate; break; } catch { /* next */ }
    }
  }
  const base = { agent, binary, checkedAt, verifiedFlags: [] as string[], missingFlags: REQUIRED[agent].flags };
  if (!binary) return { ...base, installed: false, version: null, note: 'PATH/설정에서 실행 파일을 찾지 못함(미설치)' };
  const ver = await run(binary, ['--version'], cfg.toolRoot, 10_000);
  if (ver.code !== 0) return { ...base, installed: false, version: null, note: `--version 실행 실패(code ${ver.code}): ${ver.stderr.slice(0, 120)}` };
  const help = await run(binary, REQUIRED[agent].help, cfg.toolRoot, 10_000);
  const text = help.stdout + help.stderr;
  const seen = (f: string) => new RegExp(`(^|[\\s,])${f.replace(/-/g, '\\-')}(?=[\\s=,]|$)`, 'm').test(text);
  const verified = REQUIRED[agent].flags.filter(seen);
  const login = agent === 'codex' ? await run(binary, ['login', 'status'], cfg.toolRoot, 10_000) : null;
  return {
    ...base, installed: true, version: ver.stdout.trim().slice(0, 80), verifiedFlags: verified,
    missingFlags: REQUIRED[agent].flags.filter((f) => !verified.includes(f)), stream: STREAM_FLAGS[agent].every(seen),
    note: help.code === 0 ? '--help 확인 완료(모델 요청 없음)' : `--help 실패(code ${help.code})`,
    ...(login ? { loginStatus: (login.stdout + login.stderr).trim().split('\n')[0].slice(0, 120) } : {}),
  };
}

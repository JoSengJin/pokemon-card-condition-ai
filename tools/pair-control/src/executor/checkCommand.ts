import path from 'node:path';
import type { CheckSpecT } from './contract.ts';
import { UserError } from './errors.ts';

export function resolveCheck(checkout: string, c: CheckSpecT, vars: { base: string; contract: string; head: string }) {
    const command = c.executable === 'node' ? process.execPath : c.executable === 'git' ? 'git' : path.join(checkout, '.venv', 'bin', 'python');
    const args = c.args.map((a) => a.replaceAll('{base}', vars.base).replaceAll('{contract}', vars.contract).replaceAll('{head}', vars.head));
    const cwd = path.resolve(checkout, c.cwd);
    if (cwd !== checkout && !cwd.startsWith(checkout + path.sep)) throw new UserError(`검사 cwd가 checkout 밖: ${c.cwd}`);
    return { command, args, cwd, display: [c.executable, ...args] };
  }

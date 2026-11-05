import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { lineWriter, type Redact } from './logWriter.ts';
import { attachLoggedOutput } from './loggedOutput.ts';

/**
 * 셸 없이 명령을 실행하며 stdout·stderr를 터미널처럼 섞어 로그 파일에 즉시 쓴다. 시간 제한을 넘기면 SIGKILL.
 * 결과의 stdout/stderr는 비어 있다(출력은 로그 파일에만 있다).
 */
export function runLogged(cmd: string, args: string[], cwd: string, timeoutMs: number, env: NodeJS.ProcessEnv, logPath: string, redact: Redact): Promise<{ code: number; timedOut: boolean }> {
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  fs.writeFileSync(logPath, '');
  return new Promise((resolve) => {
    const w = lineWriter(logPath, redact);
    let timedOut = false, done = false;
    const child = spawn(cmd, args, { cwd, env, stdio: ['ignore', 'pipe', 'pipe'] });
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeoutMs);
    const finish = (code: number) => { if (done) return; done = true; clearTimeout(timer); w.end(); resolve({ code, timedOut }); };
    attachLoggedOutput(child, w);
    child.on('error', (err) => { w.push(`[실행 실패] ${err.message}\n`); finish(127); });
    child.on('close', (code) => finish(typeof code === 'number' ? code : 1));
  });
}

// 실행 중인 명령의 출력을 줄 단위로 비밀 패턴을 가린 뒤 로그 파일에 바로 쓴다(실시간 화면용), 그리고 파일을 이어서 읽는다.
// 청크 경계에 걸친 비밀이 가려지지 않는 일을 막으려고 완성된 줄만 가려서 쓰고, 남은 조각은 끝날 때 쓴다.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

export type Redact = (s: string) => string;

/** 줄 단위로 가려서 파일에 덧붙이는 기록기. push(청크) 후 end()로 남은 조각을 쓴다. */
export function lineWriter(logPath: string, redact: Redact) {
  let rest = '';
  const write = (s: string) => { if (s) fs.appendFileSync(logPath, redact(s)); };
  return {
    push(chunk: string) {
      rest += chunk;
      const cut = rest.lastIndexOf('\n') + 1;
      if (cut) { write(rest.slice(0, cut)); rest = rest.slice(cut); }
    },
    end() { write(rest); rest = ''; },
  };
}

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
    child.stdout.on('data', (b) => w.push(String(b)));
    child.stderr.on('data', (b) => w.push(String(b)));
    child.on('error', (err) => { w.push(`[실행 실패] ${err.message}\n`); finish(127); });
    child.on('close', (code) => finish(typeof code === 'number' ? code : 1));
  });
}

/** 로그 파일을 from 바이트부터 이어서 읽는다. 너무 크면 끝쪽 max 바이트만. 파일이 아직 없으면 빈 결과. */
export function tailFile(file: string, from = 0, max = 64_000) {
  try {
    const size = fs.statSync(file).size;
    const start = Math.max(from, size - max);
    const fd = fs.openSync(file, 'r');
    try {
      const buf = Buffer.alloc(size - start);
      fs.readSync(fd, buf, 0, buf.length, start);
      return { text: buf.toString(), next: size };
    } finally { fs.closeSync(fd); }
  } catch { return { text: '', next: from }; }
}

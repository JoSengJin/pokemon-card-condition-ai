#!/usr/bin/env node
// 실행기가 detached로 띄우는 감독 프로세스. 새 프로세스 그룹의 리더가 되어 CLI 하나를 실행하고
// 출력(비밀값 가림)을 로그에 쓰고, 종료 결과를 exit.json에 원자적으로 기록한다.
// 서버가 재시작돼도 이 프로세스와 exit.json이 실제 실행 결과의 근거로 남는다.
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// spec: { execId, token, cwd, command, args, env, logPath, exitPath }

const SECRET_PATTERNS = [
  /sk-ant-[A-Za-z0-9_-]{8,}/g, /sk-[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{20,}/g,
  /xox[abpr]-[A-Za-z0-9-]{10,}/g, /AIza[0-9A-Za-z_-]{20,}/g, /Bearer\s+[A-Za-z0-9._-]{16,}/g,
];
const redact = (s) => SECRET_PATTERNS.reduce((acc, re) => acc.replace(re, '[REDACTED]'), s);

const log = fs.openSync(spec.logPath, 'a');
const write = (prefix, chunk) => fs.writeSync(log, redact(chunk.toString()).replace(/^(?=.)/gm, prefix));

let cancelRequested = false;
const writeExit = (result) => {
  const tmp = spec.exitPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify({ execId: spec.execId, token: spec.token, endedAt: new Date().toISOString(), cancelRequested, ...result }));
  fs.renameSync(tmp, spec.exitPath);
};

const child = spawn(spec.command, spec.args, { cwd: spec.cwd, env: spec.env, stdio: ['ignore', 'pipe', 'pipe'] });
child.stdout.on('data', (c) => write('', c));
child.stderr.on('data', (c) => write('[stderr] ', c));
// 그룹 SIGTERM은 자식에게도 전달된다. 감독자는 자식 종료를 기다렸다가 결과를 남긴다.
process.on('SIGTERM', () => { cancelRequested = true; });
process.on('SIGINT', () => { cancelRequested = true; });
child.on('error', (err) => { write('[supervisor] ', `실행 실패: ${err.code ?? err.message}\n`); writeExit({ code: null, signal: null, spawnError: String(err.code ?? err.message) }); process.exit(0); });
child.on('close', (code, signal) => {
  write('[supervisor] ', `종료 code=${code} signal=${signal}\n`);
  writeExit({ code, signal });
  process.exit(0);
});

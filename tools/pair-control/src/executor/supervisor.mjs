#!/usr/bin/env node
// 실행기가 detached로 띄우는 감독 프로세스. 새 프로세스 그룹의 리더가 되어 CLI 하나를 실행하고
// 출력(비밀값 가림)을 로그에 쓰고, 종료 결과를 exit.json에 원자적으로 기록한다.
// 서버가 재시작돼도 이 프로세스와 exit.json이 실제 실행 결과의 근거로 남는다.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import { writeLog, createLogBuffer, writeChunk, finishLog, recordExit } from './supervisorIO.mjs';

const spec = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
// spec: { execId, token, cwd, command, args, env, logPath, exitPath }

const log = fs.openSync(spec.logPath, 'a');
const state = { cancelRequested: false };
const out = createLogBuffer(log, ''), err = createLogBuffer(log, '[stderr] ');

const child = spawn(spec.command, spec.args, { cwd: spec.cwd, env: spec.env, stdio: ['ignore', 'pipe', 'pipe'] });
child.stdout.on('data', (c) => writeChunk(out, c));
child.stderr.on('data', (c) => writeChunk(err, c));
// 그룹 SIGTERM은 자식에게도 전달된다. 감독자는 자식 종료를 기다렸다가 결과를 남긴다.
process.on('SIGTERM', () => { state.cancelRequested = true; });
process.on('SIGINT', () => { state.cancelRequested = true; });
child.on('error', (error) => { finishLog(out); finishLog(err); writeLog(log, '[supervisor] ', `실행 실패: ${error.code ?? error.message}\n`); recordExit(spec, state.cancelRequested, { code: null, signal: null, spawnError: String(error.code ?? error.message) }); process.exit(0); });
child.on('close', (code, signal) => {
  finishLog(out); finishLog(err);
  writeLog(log, '[supervisor] ', `종료 code=${code} signal=${signal}\n`);
  recordExit(spec, state.cancelRequested, { code, signal });
  process.exit(0);
});

import fs from 'node:fs';
import { StringDecoder } from 'node:string_decoder';

const SECRET_PATTERNS = [
  /sk-ant-[A-Za-z0-9_-]{8,}/g, /sk-[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{20,}/g,
  /xox[abpr]-[A-Za-z0-9-]{10,}/g, /AIza[0-9A-Za-z_-]{20,}/g, /Bearer\s+[A-Za-z0-9._-]{16,}/g,
];
const redact = (s) => SECRET_PATTERNS.reduce((acc, re) => acc.replace(re, '[REDACTED]'), s);

export function writeLog(log, prefix, chunk) {
  fs.writeSync(log, redact(chunk.toString()).replace(/^(?=.)/gm, prefix));
}

/** 스트림별 UTF-8/줄 버퍼. 함수 값 대신 데이터만 보관한다. */
export function createLogBuffer(log, prefix) {
  return { log, prefix, decoder: new StringDecoder('utf8'), rest: '' };
}

export function writeChunk(state, chunk) {
  state.rest += state.decoder.write(chunk);
  const cut = state.rest.lastIndexOf('\n') + 1;
  if (cut) { writeLog(state.log, state.prefix, state.rest.slice(0, cut)); state.rest = state.rest.slice(cut); }
}

export function finishLog(state) {
  state.rest += state.decoder.end();
  if (state.rest) writeLog(state.log, state.prefix, state.rest + '\n');
  state.rest = '';
}

export function recordExit(spec, cancelRequested, result) {
  const tmp = spec.exitPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify({ execId: spec.execId, token: spec.token, endedAt: new Date().toISOString(), cancelRequested, ...result }));
  fs.renameSync(tmp, spec.exitPath);
}

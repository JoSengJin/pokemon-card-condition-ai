import fs from 'node:fs';

const SECRET_PATTERNS = [
  /sk-ant-[A-Za-z0-9_-]{8,}/g, /sk-[A-Za-z0-9_-]{16,}/g, /gh[pousr]_[A-Za-z0-9]{20,}/g,
  /xox[abpr]-[A-Za-z0-9-]{10,}/g, /AIza[0-9A-Za-z_-]{20,}/g, /Bearer\s+[A-Za-z0-9._-]{16,}/g,
];
const redact = (s) => SECRET_PATTERNS.reduce((acc, re) => acc.replace(re, '[REDACTED]'), s);

export function writeLog(log, prefix, chunk) {
  fs.writeSync(log, redact(chunk.toString()).replace(/^(?=.)/gm, prefix));
}

export function recordExit(spec, cancelRequested, result) {
  const tmp = spec.exitPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify({ execId: spec.execId, token: spec.token, endedAt: new Date().toISOString(), cancelRequested, ...result }));
  fs.renameSync(tmp, spec.exitPath);
}

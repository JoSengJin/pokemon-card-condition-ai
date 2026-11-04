import fs from 'node:fs';
import type { Executor, Execution } from './executor.ts';

export function readNewLog(taskExecutor: Executor, ex: Execution) {
  const off = taskExecutor.logOffsets.get(ex.execId) ?? 0;
  try {
    const size = fs.statSync(ex.logPath).size;
    if (size <= off) return;
    const fd = fs.openSync(ex.logPath, 'r');
    const buf = Buffer.alloc(Math.min(size - off, 1_000_000));
    fs.readSync(fd, buf, 0, buf.length, off); fs.closeSync(fd);
    // 줄 단위 이벤트(JSON)가 읽는 중간에 잘렸으면 그 줄은 다음 주기에 이어 읽는다(조각이 일반 글로 검사되지 않게).
    let text = buf.toString(), used = buf.length;
    const cut = text.lastIndexOf('\n') + 1;
    if (text.slice(cut).startsWith('{') && size - off <= 1_000_000) { text = text.slice(0, cut); used = Buffer.byteLength(text); }
    taskExecutor.logOffsets.set(ex.execId, off + used);
    return text;
  } catch { /* log not yet created */ }
  return '';
}

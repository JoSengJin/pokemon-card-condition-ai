import fs from 'node:fs';
import type { Executor, Execution } from './executor.ts';

export function readNewLog(taskExecutor: Executor, ex: Execution) {
  const off = taskExecutor.logOffsets.get(ex.execId) ?? 0;
  try {
    const size = fs.statSync(ex.logPath).size;
    if (size <= off) return;
    const fd = fs.openSync(ex.logPath, 'r');
    try {
      let buf = Buffer.alloc(Math.min(size - off, 1_000_000));
      const count = fs.readSync(fd, buf, 0, buf.length, off);
      buf = buf.subarray(0, count);
      let used = buf.length;
      const cut = buf.lastIndexOf(10) + 1;
      if (buf[cut] === 123) {
        // JSON 한 줄은 1MB 경계를 넘어도 온전히 전달한다. 완성 전이면 이전 byte 위치를 유지한다.
        const parts: Buffer[] = [buf];
        let position = off + used, complete = false;
        while (position < size) {
          const next = Buffer.alloc(Math.min(size - position, 1_000_000));
          const read = fs.readSync(fd, next, 0, next.length, position);
          if (!read) break;
          const newline = next.subarray(0, read).indexOf(10);
          const take = newline < 0 ? read : newline + 1;
          parts.push(next.subarray(0, take)); used += take; position += read;
          if (newline >= 0) { complete = true; break; }
        }
        if (complete) buf = Buffer.concat(parts);
        else { buf = buf.subarray(0, cut); used = cut; }
      } else {
        // 일반 텍스트도 끝의 UTF-8 문자 조각만 다음 읽기로 넘긴다. ASCII 과금 문구는 즉시 읽는다.
        let lead = used - 1;
        while (lead >= 0 && (buf[lead] & 0xc0) === 0x80) lead--;
        if (lead >= 0) {
          const byte = buf[lead], width = byte >= 0xf0 && byte <= 0xf4 ? 4 : byte >= 0xe0 && byte <= 0xef ? 3 : byte >= 0xc2 && byte <= 0xdf ? 2 : 1;
          if (used - lead < width) used = lead;
        }
        buf = buf.subarray(0, used);
      }
      taskExecutor.logOffsets.set(ex.execId, off + used);
      return buf.toString();
    } finally { fs.closeSync(fd); }
  } catch { /* log not yet created */ }
  return '';
}

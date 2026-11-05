import fs from 'node:fs';

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

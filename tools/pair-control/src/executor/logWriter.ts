import fs from 'node:fs';

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

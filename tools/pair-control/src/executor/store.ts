// 원자적 JSON 상태 저장(tmp + rename)과 이벤트 기록(jsonl).
import fs from 'node:fs';
import path from 'node:path';

export function writeJsonAtomic(file: string, value: unknown) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2));
  fs.renameSync(tmp, file);
}

export function readJson<T>(file: string, fallback: T): T {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')) as T; } catch { return fallback; }
}

export class Store<T extends object> {
  data: T;
  constructor(private file: string, initial: T) {
    this.data = readJson(file, initial);
  }
  save() {
    fs.mkdirSync(path.dirname(this.file), { recursive: true });
    const tmp = `${this.file}.${process.pid}.${Date.now()}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(this.data, null, 2));
    fs.renameSync(tmp, this.file);
  }
}

export function appendEvent(dir: string, event: Record<string, unknown>) {
  fs.mkdirSync(dir, { recursive: true });
  fs.appendFileSync(path.join(dir, 'events.jsonl'), JSON.stringify({ at: new Date().toISOString(), ...event }) + '\n');
}

// 메인 교대용 체크포인트: 이전 메인의 대화 기억 없이도 새 메인이 이어받을 수 있게, 도구에 저장된 상태와 실제 Git 헤드에서 만든다.
// 마지막 인계문이 없어도(한도 소진 직후) 상태 파일과 Git만으로 다시 만들 수 있다. 추정값은 넣지 않는다.
// 내용 구성(Git 헤드 대조 포함)은 checkpointBuild.ts, 이 파일은 내용 해시와 저장을 맡는다.
import { sha256 } from './contentHash.ts';
import fs from 'node:fs';
import path from 'node:path';
import type { buildCheckpoint } from './checkpointBuild.ts';
import type { Executor } from './executor.ts';

/** JSON의 toJSON·누락·null 규칙을 먼저 적용하고 객체 키를 반복 순회로 정렬한다. */
export function stable(v: unknown): string {
  const json = JSON.stringify(v);
  if (json === undefined) return 'null';
  const holder: { value: unknown } = { value: null };
  const pending: { target: any; key: string | number; value: any }[] = [{ target: holder, key: 'value', value: JSON.parse(json) }];
  while (pending.length) {
    const { target, key, value } = pending.pop()!;
    if (!value || typeof value !== 'object') { target[key] = value; continue; }
    const sorted: any = Array.isArray(value) ? [] : Object.create(null);
    target[key] = sorted;
    const keys = Array.isArray(value) ? Object.keys(value) : Object.keys(value).sort();
    for (let i = keys.length - 1; i >= 0; i--) pending.push({ target: sorted, key: keys[i], value: value[keys[i]] });
  }
  return JSON.stringify(holder.value);
}
export const hashOf = (v: unknown) => sha256(stable(v));

/** 체크포인트를 파일로 저장하고 내용 해시를 돌려준다. 해시는 파일 내용(해시 필드 제외) 기준이다. */
export function saveCheckpoint(ex: Executor, data: Awaited<ReturnType<typeof buildCheckpoint>>) {
  const why = data.why;
  const canonical = stable(data), hash = sha256(canonical);
  const file = path.join(ex.cfg.stateDir, 'main-checkpoints', `${data.at.replace(/[:.]/g, '-')}-${why}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify({ ...data, contentHash: hash }, null, 2));
  ex.runtime.lastCheckpoint = file;
  ex.store.save();
  return { file, hash, data };
}

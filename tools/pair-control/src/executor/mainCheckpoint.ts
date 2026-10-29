// 메인 교대용 체크포인트: 이전 메인의 대화 기억 없이도 새 메인이 이어받을 수 있게, 도구에 저장된 상태와 실제 Git 헤드에서 만든다.
// 마지막 인계문이 없어도(한도 소진 직후) 상태 파일과 Git만으로 다시 만들 수 있다. 추정값은 넣지 않는다.
// 내용 구성(Git 헤드 대조 포함)은 checkpointBuild.ts, 이 파일은 내용 해시와 저장을 맡는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { buildCheckpoint } from './checkpointBuild.ts';
import type { Executor } from './executor.ts';

/** 키 순서와 무관한 JSON 문자열(같은 내용은 같은 해시). 직접 재귀하지 않고 JSON.stringify의 순회에 키 정렬만 얹는다. */
export const stable = (v: unknown): string => JSON.stringify(v, (_k, x) => (x && typeof x === 'object' && !Array.isArray(x) ? Object.fromEntries(Object.keys(x).sort().map((k) => [k, x[k]])) : x)) ?? 'null';
export const hashOf = (v: unknown) => crypto.createHash('sha256').update(stable(v)).digest('hex');

/** 체크포인트를 파일로 저장하고 내용 해시를 돌려준다. 해시는 파일 내용(해시 필드 제외) 기준이다. */
export async function saveCheckpoint(ex: Executor, why: string) {
  const data = await buildCheckpoint(ex, why);
  const hash = hashOf(data);
  const file = path.join(ex.cfg.stateDir, 'main-checkpoints', `${data.at.replace(/[:.]/g, '-')}-${why}.json`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify({ ...data, contentHash: hash }, null, 2));
  ex.runtime.lastCheckpoint = file;
  ex.store.save();
  return { file, hash, data };
}

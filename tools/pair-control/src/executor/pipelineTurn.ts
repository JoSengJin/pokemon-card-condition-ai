// 현재 메인에게 모델 턴 한 번을 준다(launchTurn). 한도에 닿으면 상대 공급자로 기존 한도 교대를 연결한다(handleLimit).
// 턴 종료 처리(응답 검증·행동 적용)는 pipelineEnd.ts. 같은 이벤트는 같은 세대에 한 번만 턴을 받는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import { modelActions } from './mainApprovals.ts';
import { probe } from './adapters.ts';
import { saveCheckpoint } from './mainCheckpoint.ts';
import { tokenHash } from './mainTakeover.ts';
import { mark, pipe } from './pipelineState.ts';
import { eventRow, turnDir, writeTurnBundle } from './turnBundle.ts';
import type { Executor } from './executor.ts';
import type { MainSession, MainTurn, PipelineEvent } from './mainTypes.ts';

export async function launchTurn(ex: Executor, s: MainSession, events: PipelineEvent[]) {
  const cp = await saveCheckpoint(ex, 'turn'), token = crypto.randomUUID(), keys = events.map((e) => e.key);
  const t: MainTurn = { id: crypto.randomUUID(), sessionId: s.id, generation: s.generation, agent: s.agent, status: 'launching', eventKeys: keys, startedAt: new Date().toISOString(),
    lifetime: ex.lifetime, tokenHash: tokenHash(token), checkpointFile: cp.file, checkpointHash: cp.hash, actionResults: [] };
  pipe(ex).turns[t.id] = t;
  const request = pipe(ex).launch;
  if (request?.sessionId === s.id && request.generation === s.generation) request.turnId = t.id;
  for (const e of events) { e.tried.push(s.generation); e.turnId = t.id; }
  mark(ex, keys, 'launched');
  ex.audit('pipeline_turn_started', { turn: t.id, agent: t.agent, generation: t.generation, events: keys });
  try {
    fs.mkdirSync(turnDir(ex, t), { recursive: true });
    const rows = [];
    for (const e of events) rows.push(await eventRow(ex, e, turnDir(ex, t)));
    const b = writeTurnBundle(ex, t, token, rows, modelActions(ex, s.id));
    ex.probes[t.agent] = await probe(t.agent, ex.cfg);
    t.execId = await ex.launchMainProcess({ agent: t.agent, bundleDir: b.bundleDir, prompt: b.prompt, sessionId: t.id });
    t.status = 'launched';
  } catch (e) { t.status = 'failed'; t.failure = `턴 실행 실패: ${(e as Error).message}`; mark(ex, keys, 'held', { reason: `실행 실패: ${t.failure}` }); }
  ex.store.save();
}

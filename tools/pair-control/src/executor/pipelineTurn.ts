// 현재 메인에게 모델 턴 한 번을 주고(launchTurn), 끝나면 응답을 검증해 제안된 행동을 기존 승인 검사로 수행한다(onTurnEnd).
// 같은 이벤트는 같은 세대에 한 번만 턴을 받는다. 한도·지연·결과 불명·형식 오류는 상태를 남기고 끝내며 자동 재시도하지 않는다.
import crypto from 'node:crypto';
import { inheritable } from './mainApprovals.ts';
import { applyActions } from './mainActions.ts';
import { saveCheckpoint } from './mainCheckpoint.ts';
import { badResponse } from './mainGuard.ts';
import { handoverMain } from './mainHandover.ts';
import { parseResult, tokenHash, verifyAck } from './mainTakeover.ts';
import { mark, pipe } from './pipelineState.ts';
import fs from 'node:fs';
import { eventRow, turnDir, writeTurnBundle } from './turnBundle.ts';
import type { Execution, Executor } from './executor.ts';
import type { Agent, MainSession, MainTurn, PipelineEvent } from './mainTypes.ts';

export async function launchTurn(ex: Executor, s: MainSession, events: PipelineEvent[]) {
  const cp = await saveCheckpoint(ex, 'turn'), token = crypto.randomUUID(), keys = events.map((e) => e.key);
  const t: MainTurn = { id: crypto.randomUUID(), sessionId: s.id, generation: s.generation, agent: s.agent, status: 'launching', eventKeys: keys, startedAt: new Date().toISOString(),
    lifetime: ex.lifetime, tokenHash: tokenHash(token), checkpointFile: cp.file, checkpointHash: cp.hash, actionResults: [] };
  pipe(ex).turns[t.id] = t;
  for (const e of events) { e.tried.push(s.generation); e.turnId = t.id; }
  mark(ex, keys, 'launched');
  ex.audit('pipeline_turn_started', { turn: t.id, agent: t.agent, generation: t.generation, events: keys });
  try {
    fs.mkdirSync(turnDir(ex, t), { recursive: true });
    const rows = [];
    for (const e of events) rows.push(await eventRow(ex, e, turnDir(ex, t)));
    const b = writeTurnBundle(ex, t, token, rows, [...new Set(inheritable(ex, s.id).flatMap((a) => a.actions))]);
    t.execId = await ex.launchMainProcess({ agent: t.agent, bundleDir: b.bundleDir, prompt: b.prompt, sessionId: t.id });
    t.status = 'launched';
  } catch (e) { t.status = 'failed'; t.failure = `턴 실행 실패: ${(e as Error).message}`; mark(ex, keys, 'held', { reason: `실행 실패: ${t.failure}` }); }
  ex.store.save();
}

/** 한도: 그 에이전트는 기록돼 있고, 상대 에이전트로 기존 한도 교대를 연결한다. 양쪽이 막히면 의존 이벤트를 보류하고 복구 지점을 남긴다. */
export async function handleLimit(ex: Executor, agent: Agent, keys: string[]) {
  const other: Agent = agent === 'codex' ? 'claude' : 'codex';
  const r = await handoverMain(ex, other, { limit: true, reason: `${agent} 메인 한도 — 승인된 교대 절차 연결` });
  if (r.status === 'launching') return;
  mark(ex, keys, 'held', { reason: `한도: ${r.status}` });
  await saveCheckpoint(ex, 'both-limited');
}

async function apply(ex: Executor, t: MainTurn, res: NonNullable<ReturnType<typeof parseResult>>) {
  t.status = 'applying'; ex.store.save();
  t.actionResults = await applyActions(ex, ex.runtime.session!, res.actions ?? []);
  t.status = 'applied';
  mark(ex, t.eventKeys, 'applied', { reason: `행동 ${t.actionResults.filter((r) => r.ok).length}/${t.actionResults.length} 성공` });
  ex.audit('pipeline_turn_finished', { turn: t.id, ok: t.actionResults.filter((r) => r.ok).length, total: t.actionResults.length });
}

async function accept(ex: Executor, t: MainTurn, exec: Execution) {
  const res = parseResult(fs.existsSync(exec.logPath) ? fs.readFileSync(exec.logPath, 'utf8') : '');
  const shape = res ? badResponse(res) : '결과 JSON을 읽지 못함';
  if (shape) throw new Error(`응답 형식 오류: ${shape}`);
  const tasks = (JSON.parse(fs.readFileSync(t.checkpointFile, 'utf8')) as { tasks: { taskId: string }[] }).tasks;
  const probe = { ...ex.runtime.session!, id: t.id, generation: t.generation, tokenHash: t.tokenHash, checkpointHash: t.checkpointHash } as MainSession;
  const bad = await verifyAck(ex, probe, res!, tasks);
  if (bad.length) throw new Error(`확인 불일치: ${bad.join('; ')}`);
  await apply(ex, t, res!);
}

export async function onTurnEnd(ex: Executor, t: MainTurn, exec: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }) {
  const rt = ex.runtime, end = (status: MainTurn['status'], ev: 'pending' | 'held' | 'unknown', why: string) => { t.status = status; t.failure = why; mark(ex, t.eventKeys, ev, { reason: why }); };
  if (t.status !== 'launched' || t.execId !== exec.execId) { ex.audit('main_stale_result_rejected', { execId: exec.execId, turn: t.id }); return; }
  if (rt.session?.id !== t.sessionId || rt.generation !== t.generation || rt.frozen) return end('stale', 'pending', '이전 세대/세션의 늦은 응답 — 상태를 바꾸지 않음(새 메인이 다시 판단)');
  if (rt.limited[t.agent] && rt.limited[t.agent]!.at >= t.startedAt) { end('limited', 'pending', `메인(${t.agent}) 한도`); return handleLimit(ex, t.agent, t.eventKeys); }
  if (r.unknown) return end('unknown', 'unknown', '턴 프로세스가 종료 기록 없이 사라짐(결과 불명) — 재시도하지 않음');
  if (r.cancelled || r.code !== 0) return end('failed', 'held', r.cancelled ? '턴이 중단됨' : `턴 종료코드 ${r.code}`);
  try { await accept(ex, t, exec); } catch (e) {
    if ((t.status as MainTurn['status']) === 'applying') end('unknown', 'unknown', `행동 적용 중 예외 — 일부 수행됐을 수 있어 재시도하지 않음: ${(e as Error).message}`);
    else end('failed', 'held', (e as Error).message);
  }
  ex.store.save();
}

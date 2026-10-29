// 턴 종료 처리: 응답을 검증(형식·확인 대조)한 뒤 제안된 행동을 기존 승인 검사로 수행한다.
// 지연·이전 세대·한도·결과 불명·형식 오류는 상태를 남기고 끝내며 자동 재시도하지 않는다.
import fs from 'node:fs';
import { applyActions } from './mainActions.ts';
import { badResponse } from './mainGuard.ts';
import { parseResult, verifyAck } from './mainTakeover.ts';
import { handleLimit } from './pipelineTurn.ts';
import { mark } from './pipelineState.ts';
import type { Execution, Executor } from './executor.ts';
import type { MainSession, MainTurn } from './mainTypes.ts';

/** 응답 형식과 확인(세션·세대·토큰·체크포인트·실제 Git 헤드)을 검증해 통과한 응답을 돌려준다. 어긋나면 던진다(행동은 아직 적용하지 않음). */
async function verifyResponse(ex: Executor, t: MainTurn, exec: Execution) {
  const res = parseResult(fs.existsSync(exec.logPath) ? fs.readFileSync(exec.logPath, 'utf8') : '');
  const shape = res ? badResponse(res) : '결과 JSON을 읽지 못함';
  if (shape) throw new Error(`응답 형식 오류: ${shape}`);
  const tasks = (JSON.parse(fs.readFileSync(t.checkpointFile, 'utf8')) as { tasks: { taskId: string }[] }).tasks;
  const probe = { ...ex.runtime.session!, id: t.id, generation: t.generation, tokenHash: t.tokenHash, checkpointHash: t.checkpointHash } as MainSession;
  const bad = await verifyAck(ex, probe, res!, tasks);
  if (bad.length) throw new Error(`확인 불일치: ${bad.join('; ')}`);
  return res!;
}

/** 턴을 끝내고 이벤트 상태를 맞춘다. */
function end(ex: Executor, t: MainTurn, status: MainTurn['status'], ev: 'pending' | 'held' | 'unknown', why: string) {
  t.status = status; t.failure = why;
  mark(ex, t.eventKeys, ev, { reason: why });
}

export async function onTurnEnd(ex: Executor, t: MainTurn, exec: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }) {
  const rt = ex.runtime;
  if (t.status !== 'launched' || t.execId !== exec.execId) { ex.audit('main_stale_result_rejected', { execId: exec.execId, turn: t.id }); return; }
  if (rt.session?.id !== t.sessionId || rt.generation !== t.generation || rt.frozen) return end(ex, t, 'stale', 'pending', '이전 세대/세션의 늦은 응답 — 상태를 바꾸지 않음(새 메인이 다시 판단)');
  if (rt.limited[t.agent] && rt.limited[t.agent]!.at >= t.startedAt) { end(ex, t, 'limited', 'pending', `메인(${t.agent}) 한도`); return handleLimit(ex, t.agent, t.eventKeys); }
  if (r.unknown) return end(ex, t, 'unknown', 'unknown', '턴 프로세스가 종료 기록 없이 사라짐(결과 불명) — 재시도하지 않음');
  if (r.cancelled || r.code !== 0) return end(ex, t, 'failed', 'held', r.cancelled ? '턴이 중단됨' : `턴 종료코드 ${r.code}`);
  let res: Awaited<ReturnType<typeof verifyResponse>>;
  try { res = await verifyResponse(ex, t, exec); } catch (e) { return end(ex, t, 'failed', 'held', (e as Error).message); }
  t.status = 'applying'; ex.store.save(); // 적용이 시작되면 재시작 뒤에도 다시 적용하지 않는다(결과 불명으로 보존)
  try { t.actionResults = await applyActions(ex, rt.session!, res.actions ?? []); } catch (e) { return end(ex, t, 'unknown', 'unknown', `행동 적용 중 예외 — 일부 수행됐을 수 있어 재시도하지 않음: ${(e as Error).message}`); }
  let ok = 0;
  for (const r of t.actionResults) if (r.ok) ok++;
  t.status = 'applied';
  mark(ex, t.eventKeys, 'applied', { reason: `행동 ${ok}/${t.actionResults.length} 성공` });
  ex.audit('pipeline_turn_finished', { turn: t.id, ok, total: t.actionResults.length });
  ex.store.save();
}

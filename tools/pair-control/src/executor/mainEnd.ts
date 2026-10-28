// 새 메인 프로세스 종료 처리: 응답 전체를 먼저 검증하고, 인수 확인을 통과했을 때만 인수한다.
// 어떤 실패도 감시 루프로 예외를 내보내지 않고 세션 실패(체크포인트 보존)로 기록한다.
import fs from 'node:fs';
import { badResponse } from './mainGuard.ts';
import { ackSession, failSession } from './mainHandover.ts';
import { parseResult, verifyAck } from './mainTakeover.ts';
import { pipe } from './pipelineState.ts';
import { onTurnEnd } from './pipelineTurn.ts';
import type { Execution, Executor } from './executor.ts';

/** 새 메인 프로세스가 끝났을 때(감시 루프가 호출). 이전 세대의 늦은 결과는 아무것도 바꾸지 못한다. */
export async function onMainEnd(ex: Executor, exec: Execution, r: { code: number | null; cancelled: boolean; unknown: boolean }): Promise<void> {
  const rt = ex.runtime, s = rt.session, turn = pipe(ex).turns[exec.runId];
  if (turn) { try { await onTurnEnd(ex, turn, exec, r); } catch (e) { ex.audit('pipeline_turn_error', { turn: turn.id, error: (e as Error).message }); } return; }
  if (!s || s.execId !== exec.execId || s.status !== 'launching') { ex.audit('main_stale_result_rejected', { execId: exec.execId, session: exec.runId }); ex.store.save(); return; }
  if (rt.limited[s.agent] && rt.limited[s.agent]!.at >= s.startedAt) { failSession(ex, s, `새 메인(${s.agent}) 한도 소진 — 상태·체크포인트 보존, 재시도하지 않음`); return; }
  if (r.unknown || r.cancelled || r.code !== 0) { failSession(ex, s, r.unknown ? '새 메인 프로세스가 종료 기록 없이 사라짐(결과 불명) — 같은 요청을 다시 보내지 않음' : r.cancelled ? '새 메인 실행이 중단됨' : `새 메인 종료코드 ${r.code}`); return; }
  try {
    const res = parseResult(fs.existsSync(exec.logPath) ? fs.readFileSync(exec.logPath, 'utf8') : '');
    if (!res) { failSession(ex, s, '새 메인의 결과 JSON을 읽지 못함 — 인수하지 않음'); return; }
    const shape = badResponse(res);
    if (shape) { failSession(ex, s, `새 메인의 응답 형식 오류: ${shape} — 인수하지 않음`); return; }
    const cp = JSON.parse(fs.readFileSync(s.checkpointFile, 'utf8')) as { tasks: { taskId: string }[] };
    const bad = await verifyAck(ex, s, res, cp.tasks);
    if (bad.length) { failSession(ex, s, `인수 확인 불일치: ${bad.join('; ')}`); return; }
    await ackSession(ex, s, res);
  } catch (e) {
    if (rt.session === s && s.status === 'launching') failSession(ex, s, `인수 처리 중 예외: ${(e as Error).message} — 인수하지 않음`);
    else ex.audit('main_end_error', { session: s.id, error: (e as Error).message });
  }
}

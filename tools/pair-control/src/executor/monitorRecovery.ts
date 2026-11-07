import { ensureWatcher } from './monitorSchedule.ts';
import { alive, groupAlive, ownsLeader } from './processIdentity.ts';
import fs from 'node:fs';
import { setStatus, releaseExecLocks } from './taskState.ts';
import type { Executor, Task, Execution } from './executor.ts';

export function recover(taskExecutor: Executor, ) {
  for (const ex of Object.values(taskExecutor.state.executions)) {
    if (ex.status !== 'running' && ex.status !== 'cancelling') continue;
    if (ex.serverLifetime === taskExecutor.lifetime) continue;
    ex.observedAfterRestart = true;
    const t = taskExecutor.state.tasks[ex.taskId];
    if ((ex.kind ?? 'agent') !== 'agent') {
      // 작업 테스트·리뷰: 살아 있으면 관찰만, 종료 기록이 있으면 tick에서 기록만 하고 다음 검사를 이어 실행하지 않는다.
      if (!fs.existsSync(ex.exitPath) && !groupAlive(taskExecutor, ex.pgid)) { ex.status = 'unknown'; ex.completion = { stage: 'observed', code: null, cancelled: false, unknown: true }; }
      continue;
    }
    if (fs.existsSync(ex.exitPath)) { /* tick에서 exit_observed로 정리 */ }
    else if (alive(taskExecutor, ex.pid) && ownsLeader(taskExecutor, ex)) setStatus(taskExecutor, t, 'orphan_running', '서버 재시작 전 시작된 프로세스가 아직 실행 중(관찰만 함)');
    else if (groupAlive(taskExecutor, ex.pgid)) setStatus(taskExecutor, t, 'orphan_running', '감독자는 없고 같은 그룹 자식 프로세스만 남음');
    else { ex.status = 'unknown'; setStatus(taskExecutor, t, 'unknown', '재시작 후 프로세스·종료 기록 모두 없음(결과 불명)'); }
  }
  for (const t of Object.values(taskExecutor.state.tasks)) {
    if (t.status === 'starting') setStatus(taskExecutor, t, 'unknown', '시작 도중 서버 종료(결과 불명)');
    if (t.status === 'integrating') setStatus(taskExecutor, t, 'unknown', '통합 도중 서버 종료(통합 checkout을 직접 확인)');
  }
  taskExecutor.store.save();
  ensureWatcher(taskExecutor, );
}

export async function observeExit(taskExecutor: Executor, ex: Execution) {
  const t = taskExecutor.state.tasks[ex.taskId];
  let res: any = {};
  try { res = JSON.parse(fs.readFileSync(ex.exitPath, 'utf8')); } catch { return; }
  if (res.token !== ex.token) {
    ex.status = 'unknown';
    if ((ex.kind ?? 'agent') !== 'agent') { ex.completion = { stage: 'observed', code: null, cancelled: false, unknown: true }; taskExecutor.store.save(); }
    else setStatus(taskExecutor, t, 'unknown', 'exit.json 토큰 불일치');
    return;
  }
  if (groupAlive(taskExecutor, ex.pgid)) {
    const leader = ownsLeader(taskExecutor, ex);
    if (leader !== true && groupAlive(taskExecutor, ex.pgid)) {
      ex.status = 'unknown';
      if ((ex.kind ?? 'agent') !== 'agent') { ex.completion = { stage: 'observed', code: null, cancelled: false, unknown: true }; taskExecutor.store.save(); }
      else setStatus(taskExecutor, t, 'unknown', '종료 기록은 있으나 남은 프로세스 그룹 소유권 미확인 — 정리/자동 결과 반영 보류');
      return;
    }
    if (leader === true) { try { process.kill(-ex.pgid, 'SIGKILL'); } catch { /* gone */ } }
  }
  const cancelled = ex.cancelRequested || res.cancelRequested;
  ex.exitCode = res.code; ex.signal = res.signal; ex.spawnError = res.spawnError ?? null; ex.endedAt = res.endedAt;
  ex.status = cancelled ? 'cancelled' : 'exited';
  if ((ex.kind ?? 'agent') !== 'agent') { ex.completion = { stage: 'observed', code: res.code, cancelled, unknown: false }; taskExecutor.store.save(); return; }
  releaseExecLocks(taskExecutor, t, ex.execId);
  taskExecutor.audit('exec_ended', { execId: ex.execId, taskId: t.taskId, code: res.code, signal: res.signal, cancelled, afterRestart: ex.observedAfterRestart });
  if (ex.observedAfterRestart) {
    // 서버 재시작 전후로 이어진 실행: 결과를 자동 반영하지 않고 사용자 확인을 기다린다.
    setStatus(taskExecutor, t, 'exit_observed', `재시작 후 종료 관찰(code ${res.code}). '결과 반영'으로 await-exit 단계를 재개`);
    return;
  }
  // 최종 상태(검토 대기/실패/중단)는 workflow collect 단계가 정한다.
  setStatus(taskExecutor, t, 'collecting', `종료 확인(code ${res.code}${cancelled ? ', 중단' : ''}) · 결과 수집 중`);
  await resume(taskExecutor, t, ex, { execId: ex.execId, exitCode: res.code, signal: res.signal, cancelled });
}

export async function resume(taskExecutor: Executor, t: Task, ex: Execution, data: Record<string, unknown>) {
  if (!taskExecutor.resumer || !ex.runId) return;
  try { await taskExecutor.resumer(ex.runId, 'await-exit', data); }
  catch (err) { taskExecutor.audit('resume_error', { taskId: t.taskId, error: (err as Error).message }); t.statusReason = `workflow 재개 실패: ${(err as Error).message}`; taskExecutor.store.save(); }
}

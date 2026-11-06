import { observeExit, resume } from './monitorRecovery.ts';
import { readNewLog } from './processLog.ts';
import { alive, groupAlive } from './processIdentity.ts';
import fs from 'node:fs';
import { onTurnEnd } from './pipelineEnd.ts';
import { onMainEnd } from './mainEnd.ts';
import { onReviewEnd } from './reviewEnd.ts';
import { onAuxEnd, startNextCheck } from './verificationLifecycle.ts';
import { setStatus, releaseExecLocks } from './taskState.ts';
import { outputSignals } from './streamGuard.ts';
import { cancelAll } from './taskCancel.ts';
import { mark, pipe } from './pipelineState.ts';
import { pipelineTick } from './pipelineTick.ts';
import { advancePushAction } from './actionPush.ts';
import { dispatchAction } from './actionDispatch.ts';
import { actionsDone } from './actionState.ts';
import { finishApplied } from './pipelineApply.ts';
import { finishSession } from './mainSessionApply.ts';
import type { MainTurn } from './mainTypes.ts';
import { autoSteps } from './pipelineSteps.ts';
import { scanEvents, wanted } from './pipelineEvents.ts';
import { launchTurn } from './pipelineTurn.ts';
import { turnHold } from './approvalScope.ts';
import { advanceSessionLaunch } from './mainSessionLaunch.ts';
import { handoverAfterLimit } from './mainLimit.ts';
import type { Executor } from './executor.ts';

export async function tick(taskExecutor: Executor, ) {
  if (taskExecutor.ticking) return;
  taskExecutor.ticking = true;
  try {
    // 관찰과 취소 실행을 같은 진입점에서 순서대로 처리한다. 가드 콜백은 저장만 한다.
    for (const execution of Object.values(taskExecutor.state.executions)) {
      if (!['running', 'cancelling'].includes(execution.status)) continue;
      const log = readNewLog(taskExecutor, execution);
      if (!log) continue;
      for (const signal of outputSignals(log, 'exec:' + execution.execId)) {
        if (signal.kind === 'paid') taskExecutor.guard.trip(signal.reason, signal.detail, signal.source);
        else taskExecutor.guard.reportLimit(signal.alert);
      }
    }
    for (const request of taskExecutor.state.guardCancellations ?? []) {
      if (request.stage === 'dispatching') { request.stage = 'unknown'; taskExecutor.store.save(); continue; }
      if (request.stage !== 'pending') continue;
      request.stage = 'dispatching'; request.lifetime = taskExecutor.lifetime; taskExecutor.store.save();
      cancelAll(taskExecutor, request.reason, request.agent);
      request.stage = 'sent'; taskExecutor.store.save();
    }
    const pending = Object.values(taskExecutor.state.executions).find((row) => row.completion && row.completion.stage !== 'done');
    if (pending?.completion?.stage === 'observed') {
      pending.completion.stage = 'routing'; pending.completion.lifetime = taskExecutor.lifetime; taskExecutor.store.save(); return;
    }
    if (pending?.completion?.stage === 'routing') {
      const saved = pending.completion, stale = saved.lifetime !== taskExecutor.lifetime;
      const result = stale ? { code: null, cancelled: false, unknown: true } : { code: saved.code, cancelled: saved.cancelled, unknown: saved.unknown };
      const turn = pending.kind === 'main' ? pipe(taskExecutor).turns[pending.runId] : undefined;
      const task = taskExecutor.state.tasks[pending.taskId];
      const check = pending.kind === 'check' ? task?.verification?.items.find((item) => item.execId === pending.execId) : undefined;
      const alreadyHandled = !!(stale && ((turn && turn.status !== 'launched') || (pending.kind === 'main' && !turn && taskExecutor.runtime.session?.status !== 'launching') || (pending.kind === 'check' && check?.status !== 'running') || (pending.kind === 'review' && task?.review?.status !== 'running')));
      if (!alreadyHandled) {
        if (turn) await onTurnEnd(taskExecutor, turn, pending, result);
        else if (pending.kind === 'main') await onMainEnd(taskExecutor, pending, result);
        else if (pending.kind === 'review') await onReviewEnd(taskExecutor, task, pending, result);
        else await onAuxEnd(taskExecutor, pending, result);
      }
      saved.stage = 'done'; taskExecutor.store.save(); return;
    }
  for (const ex of Object.values(taskExecutor.state.executions)) {
    if (ex.status !== 'running' && ex.status !== 'cancelling') continue;
    if (fs.existsSync(ex.exitPath)) { await observeExit(taskExecutor, ex); continue; }
    if (!alive(taskExecutor, ex.pid)) {
      await new Promise((r) => setTimeout(r, 200));
      if (fs.existsSync(ex.exitPath)) { await observeExit(taskExecutor, ex); continue; }
      if (groupAlive(taskExecutor, ex.pgid)) continue; // 리더만 죽고 자식이 남은 경우: 정리 전까지 실행 중으로 본다
      const t = taskExecutor.state.tasks[ex.taskId];
      if ((ex.kind ?? 'agent') !== 'agent') {
        ex.status = ex.cancelRequested ? 'cancelled' : 'unknown'; ex.endedAt = new Date().toISOString();
        ex.completion = { stage: 'observed', code: null, cancelled: ex.cancelRequested, unknown: !ex.cancelRequested };
        taskExecutor.store.save();
        continue;
      }
      if (ex.cancelRequested) {
        ex.status = 'cancelled'; ex.endedAt = new Date().toISOString();
        releaseExecLocks(taskExecutor, t, ex.execId);
        setStatus(taskExecutor, t, 'collecting', '사용자 중단(강제 종료로 종료 기록 없음) · 결과 수집 중');
        await resume(taskExecutor, t, ex, { execId: ex.execId, exitCode: null, signal: 'SIGKILL', cancelled: true });
      } else {
        ex.status = 'unknown';
        setStatus(taskExecutor, t, 'unknown', '감독 프로세스가 종료 기록 없이 사라짐(결과 불명). 잠금 유지.');
      }
    }
  }
  if (taskExecutor.guardAlert || taskExecutor.stopped) return;
  if (Object.values(taskExecutor.state.executions).some((execution) => execution.completion && execution.completion.stage !== 'done')) return;
  for (const t of Object.values(taskExecutor.state.tasks)) {
    const v = t.verification;
    if (v?.status !== 'running' || v.items.some((item) => item.status === 'running')) continue;
    await startNextCheck(taskExecutor, t);
    return;
  }
  const launching = taskExecutor.runtime.session;
  if (launching?.status === 'launching' && launching.launchStage) { await advanceSessionLaunch(taskExecutor, launching); return; }
  const limited = Object.values(pipe(taskExecutor).turns).find((turn) => turn.status === 'limited' && turn.limitHandledAt && !turn.limitHandoverDoneAt);
  if (limited) {
    if (!limited.limitHandoverStartedAt) { limited.limitHandoverStartedAt = new Date().toISOString(); limited.limitHandoverLifetime = taskExecutor.lifetime; taskExecutor.store.save(); return; }
    if (limited.limitHandoverLifetime !== taskExecutor.lifetime) {
      limited.limitHandoverDoneAt = new Date().toISOString(); limited.failure = '서버 재시작 전 한도 교대 시작 — 결과 불명, 재시도하지 않음';
      mark(taskExecutor, limited.eventKeys, 'unknown', { reason: limited.failure }); taskExecutor.store.save(); return;
    }
    const other = limited.agent === 'codex' ? 'claude' : 'codex';
    await handoverAfterLimit(taskExecutor, other, limited.eventKeys, `${limited.agent} 메인 한도 — 승인된 교대 절차 연결`);
    limited.limitHandoverDoneAt = new Date().toISOString(); taskExecutor.store.save(); return;
  }
  // 저장된 push 작업은 실행 감시가 직접 진행한다. 턴 적용과 별개로 한 단계만 수행한다.
  const session = taskExecutor.runtime.session;
  if (!taskExecutor.stopped && session && !taskExecutor.runtime.frozen) {
    const owners = session.status === 'applying' && session.actionLifetime === taskExecutor.lifetime
      ? [session] : Object.values(pipe(taskExecutor).turns);
    for (const owner of owners) {
      if (owner.status !== 'applying') continue;
      if ('lifetime' in owner && owner.lifetime !== taskExecutor.lifetime) continue;
      for (const work of owner.actionWork ?? []) {
        if (work.status === 'done') continue;
        if (work.status === 'authorized') await dispatchAction(taskExecutor, session, work);
        else if (work.status === 'dispatching' && work.action.type === 'push_main' && work.dispatchLifetime === taskExecutor.lifetime && work.pushStage) await advancePushAction(taskExecutor, session, work);
        else break;
        if (actionsDone(owner)) {
          if (owner === session) finishSession(taskExecutor, session); else finishApplied(taskExecutor, owner as MainTurn);
        }
        return;
      }
    }
  }
  const request = pipe(taskExecutor).launch;
  if (request && !taskExecutor.stopped && !taskExecutor.runtime.frozen) {
    const valid = session?.id === request.sessionId && taskExecutor.runtime.generation === request.generation && ['completed', 'idle'].includes(session.status);
    const knownTurn = request.turnId && pipe(taskExecutor).turns[request.turnId];
    if (knownTurn) { delete pipe(taskExecutor).launch; taskExecutor.store.save(); return; } // 종료 관찰·턴 복구가 실제 실행 기록을 처리한다.
    if (!valid || request.stage === 'launching') {
      mark(taskExecutor, request.eventKeys, valid ? 'unknown' : 'pending', { reason: valid ? '턴 실행 시작 뒤 결과 기록 없음 — 재시도하지 않음' : '저장된 턴 요청의 세션·세대가 바뀜' });
    } else {
      const events = [];
      for (const key of request.eventKeys) {
        const event = pipe(taskExecutor).events[key], task = event && taskExecutor.state.tasks[event.taskId];
        if (!event || !task) continue;
        const current = wanted(taskExecutor, task);
        if (!current || current.kind !== event.kind || current.sha !== event.sha) {
          mark(taskExecutor, [key], 'held', { reason: '대상 상태 변경: 저장된 이벤트가 현재 작업 상태·SHA와 다름' }); continue;
        }
        const hold = turnHold(taskExecutor, session!.id, task, event.kind);
        if (hold) { mark(taskExecutor, [key], 'held', { reason: hold }); continue; }
        events.push(event);
      }
      if (!events.length) { delete pipe(taskExecutor).launch; taskExecutor.store.save(); return; }
      request.stage = 'launching'; request.lifetime = taskExecutor.lifetime; taskExecutor.store.save();
      await launchTurn(taskExecutor, session!, events);
    }
    delete pipe(taskExecutor).launch; taskExecutor.store.save(); return;
  }
  if (session) await autoSteps(taskExecutor, session.id);
  scanEvents(taskExecutor);
  await pipelineTick(taskExecutor); // 교대 뒤 연속 처리: 상태를 읽고 새 이벤트가 있을 때만 현재 메인에게 턴을 준다
  } finally { taskExecutor.ticking = false; }
}

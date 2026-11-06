// 작업 테스트도 stop/과금 가드 뒤 새 프로세스를 시작하지 않는다. 임시 저장소의 git 검사만 사용.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { execFileSync } from 'node:child_process';
import { assign } from '../src/executor/taskAssign.ts';
import { runChecks } from '../src/executor/verificationStart.ts';
import { startNextCheck } from '../src/executor/verificationLifecycle.ts';
import { tick } from '../src/executor/monitorTick.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { setup, task } from './helpers.ts';

async function ready() {
  const e = setup();
  const t = await assign(e.ex, task(e,'task-a',{mode:'manual'}));
  t.status = 'review_pending';
  t.result = {headSha:execFileSync('/usr/bin/git',['rev-parse','HEAD'],{cwd:t.worktree,encoding:'utf8'}).trim(),checks:[],checksPassed:true} as any;
  return {e,t};
}

for (const route of ['tick-stop','direct-stop','direct-guard']) test(`대기 검사: ${route}이면 새 프로세스 없음`, async () => {
  const {e,t} = await ready();
  try {
    await runChecks(e.ex,t.taskId);
    stop(e.ex);
    if(route==='direct-guard') {e.ex.stopped=false;e.ex.guardAlert={detail:'synthetic billing signal'} as any;}
    if(route==='tick-stop') await tick(e.ex); else await startNextCheck(e.ex,t);
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(t.verification!.items[0].status,'pending');
  } finally {e.cleanup();}
});

for (const changed of ['stop','guard']) test(`검사 준비 대기 중 ${changed}이면 새 검사 등록 거절`, async () => {
  const {e,t} = await ready();
  try {
    const originalTimer = e.ex.timer;
    const pending = runChecks(e.ex,t.taskId);
    if(changed==='stop')stop(e.ex);else e.ex.guardAlert={detail:'synthetic billing signal'} as any;
    await assert.rejects(pending);
    assert.equal(t.verification,undefined);
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(e.ex.timer,changed==='stop'?null:originalTimer);
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`),null);
  } finally {e.cleanup();}
});

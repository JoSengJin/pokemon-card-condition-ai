// 합성 응답과 임시 Git 대기만 사용. 실제 모델/CLI 호출 없음.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {onMainEnd} from '../src/executor/mainEnd.ts';
import {onTurnEnd} from '../src/executor/pipelineEnd.ts';
import {tokenHash} from '../src/executor/mainTakeover.ts';
import {pipe} from '../src/executor/pipelineState.ts';
import {applyVerified,finishApplied} from '../src/executor/pipelineApply.ts';
import {pipelineTick} from '../src/executor/pipelineTick.ts';
import {setup,waitFor} from './helpers.ts';
import {gitGate} from './api-git-gate.ts';

function fixture(kind:'main'|'turn',badHead=false){
 const e=setup();if(e.ex.timer){clearInterval(e.ex.timer);e.ex.timer=null;}
 const w=e.fixture.worktrees['task-a'],sha=execFileSync('/usr/bin/git',['rev-parse','HEAD'],{cwd:w.path,encoding:'utf8'}).trim(),file=path.join(e.dir,'checkpoint.json'),log=path.join(e.dir,'response.log'),hash='a'.repeat(64),token='synthetic-nonce';
 e.ex.state.tasks['task-a']={taskId:'task-a',branch:w.branch,worktree:w.path,status:'review_pending'} as any;
 e.ex.state.main={agent:'codex',since:'before',generation:1};e.ex.runtime.generation=1;e.ex.runtime.frozen=kind==='main';
 const session:any={id:'owner',agent:kind==='main'?'claude':'codex',from:'codex',generation:kind==='main'?2:1,status:kind==='main'?'launching':'idle',execId:'synthetic',startedAt:'2000-01-01T00:00:00Z',limitRecovery:false,tokenHash:tokenHash(token),checkpointFile:file,checkpointHash:hash,actionResults:[]};e.ex.runtime.session=session;
 const turn:any={id:'turn',sessionId:session.id,generation:1,agent:'codex',execId:'synthetic',status:'launched',eventKeys:['event'],tokenHash:tokenHash(token),checkpointFile:file,checkpointHash:hash,startedAt:session.startedAt,actionResults:[]};
 pipe(e.ex).events.event={key:'event',kind:'result_ready',taskId:'task-a',sha,at:'now',state:'launched',tried:[1],turnId:turn.id};pipe(e.ex).turns[turn.id]=turn;
 fs.writeFileSync(file,JSON.stringify({tasks:[{taskId:'task-a'}]}));fs.writeFileSync(log,JSON.stringify({session_id:kind==='main'?session.id:turn.id,generation:kind==='main'?2:1,token,checkpoint_hash:hash,observed:{heads:{'task-a':badHead?'0'.repeat(40):sha}},actions:[{id:'synthetic-note',type:'note'}]})+'\n');
 const record:any={execId:'synthetic',runId:session.id,logPath:log};return {e,w,session,turn,record,result:{code:0,cancelled:false,unknown:false}};
}

for(const change of ['replace','replace-error','generation','stop','guard','limit'])test(`인수 확인 Git 대기 중 ${change}: 이전 응답이 메인을 바꾸지 못함`,async()=>{
 const f=fixture('main',change==='replace-error'),{e,session}=f,gate=gitGate(f.w.path,['rev-parse','--verify','--quiet']);let pending:Promise<unknown>|undefined;
 try{pending=onMainEnd(e.ex,f.record,f.result);await waitFor(()=>fs.existsSync(gate.entered),'ack gate');
  if(change.startsWith('replace')){e.ex.runtime.session={...session,id:'new-owner',generation:3,status:'idle'};e.ex.runtime.generation=3;e.ex.runtime.frozen=false;e.ex.state.main={agent:'codex',since:'new-owner',generation:3};}
  if(change==='generation')e.ex.runtime.generation=2;if(change==='stop')e.ex.stopped=true;if(change==='guard')e.ex.guardAlert={detail:'synthetic guard'} as any;if(change==='limit')e.ex.runtime.limited.claude={at:new Date().toISOString(),detail:'synthetic limit'};
  const before=JSON.stringify(e.ex.state.main),generation=e.ex.runtime.generation;fs.writeFileSync(gate.release,'go');await pending;assert.equal(JSON.stringify(e.ex.state.main),before);assert.equal(e.ex.runtime.generation,generation);assert.equal(session.ackedAt,undefined);assert.equal(session.pendingActions,undefined);
 }finally{fs.writeFileSync(gate.release,'cleanup');try{await pending;}catch{}gate.close();e.cleanup();}
});

for(const change of ['generation','session','frozen','limit','terminal','transferred-error'])test(`턴 확인 Git 대기 중 ${change}: 이전 결과가 현재 이벤트를 덮지 못함`,async()=>{
 const f=fixture('turn',change==='transferred-error'),{e,turn}=f,gate=gitGate(f.w.path,['rev-parse','--verify','--quiet']);let pending:Promise<unknown>|undefined;
 try{pending=onTurnEnd(e.ex,turn,f.record,f.result);await waitFor(()=>fs.existsSync(gate.entered),'turn gate');
  if(change==='terminal'){turn.status='unknown';turn.failure='already unknown';}
  else if(change==='session')e.ex.runtime.session={...f.session,id:'new-owner'};
  else if(change==='frozen')e.ex.runtime.frozen=true;
  else if(change==='limit')e.ex.runtime.limited.codex={at:new Date().toISOString(),detail:'synthetic limit'};
  else e.ex.runtime.generation=2;
  if(change==='transferred-error'){e.ex.runtime.session={...f.session,id:'new-owner',generation:2};pipe(e.ex).events.event.turnId='new-turn';pipe(e.ex).events.event.state='applied';}
  fs.writeFileSync(gate.release,'go');await pending;assert.equal(turn.status,change==='terminal'?'unknown':change==='limit'?'limited':'stale');assert.equal(turn.pendingActions,undefined);if(change==='transferred-error'){assert.equal(pipe(e.ex).events.event.state,'applied');assert.equal(pipe(e.ex).events.event.turnId,'new-turn');}
 }finally{fs.writeFileSync(gate.release,'cleanup');try{await pending;}catch{}gate.close();e.cleanup();}
});

for(const stage of ['response','verified','finish','recovery'])test(`이미 다른 턴이 적용한 이벤트는 늦은 ${stage} 처리가 덮지 않음`,async()=>{
 const f=fixture('turn');try{
  pipe(f.e.ex).events.event.turnId='new-turn';pipe(f.e.ex).events.event.state='applied';
  if(stage==='response'){f.e.ex.runtime.generation=2;await onTurnEnd(f.e.ex,f.turn,f.record,f.result);assert.equal(f.turn.status,'stale');}
  if(stage==='verified'){f.e.ex.runtime.generation=2;f.turn.status='verified';f.turn.pendingActions=[];applyVerified(f.e.ex);assert.equal(f.turn.status,'stale');}
  if(stage==='finish'){f.turn.status='applying';finishApplied(f.e.ex,f.turn);assert.equal(f.turn.status,'applied');}
  if(stage==='recovery'){f.turn.status='applying';f.turn.lifetime='previous';await pipelineTick(f.e.ex);assert.equal(f.turn.status,'unknown');}
  assert.equal(pipe(f.e.ex).events.event.state,'applied');assert.equal(pipe(f.e.ex).events.event.turnId,'new-turn');
 }finally{f.e.cleanup();}
});

for(const kind of ['main','turn'] as const)test(`변경 없는 ${kind} 응답은 검증 상태와 행동 제안을 저장`,async()=>{
 const f=fixture(kind);try{if(kind==='main'){await onMainEnd(f.e.ex,f.record,f.result);assert.equal(f.session.status,'taken_over');assert.equal(f.e.ex.mainAgent,'claude');assert.equal(f.session.pendingActions.length,1);}else{await onTurnEnd(f.e.ex,f.turn,f.record,f.result);assert.equal(f.turn.status,'verified');assert.equal(f.turn.pendingActions.length,1);}assert.equal(f.e.ex.runtime.processed['synthetic-note'],undefined);}finally{f.e.cleanup();}
});

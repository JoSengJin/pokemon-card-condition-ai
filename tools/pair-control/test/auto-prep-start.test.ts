// 자동 준비 중 바뀐 승인/세션/중단은 검사·인계 저장 직전에 거절한다. 실제 모델 호출 없음.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {assign} from '../src/executor/taskAssign.ts';
import {grantApproval,revokeApproval} from '../src/executor/mainApprovals.ts';
import {autoSteps} from '../src/executor/pipelineSteps.ts';
import {setup,task} from './helpers.ts';

for(const kind of ['checks','handoff']) for(const change of ['none','approval','session','frozen','stop','guard','task-status','task-sha']) test(`자동 ${kind}: 준비 중 ${change} 최종 검사`,async()=>{
 const e=setup();
 try{
  const t=await assign(e.ex,task(e,'task-a',{mode:'manual'}));
  const head=execFileSync('/usr/bin/git',['rev-parse','HEAD'],{cwd:t.worktree,encoding:'utf8'}).trim();
  t.status='review_pending';t.result={headSha:head,commits:[{sha:head}],changedFiles:[],checks:[],checksPassed:true} as any;
  if(kind==='handoff')t.verification={runId:'passed',sha:head,contractHash:t.contractHash,status:'passed',items:[],startedAt:'now'};
  const initial=t.verification;
  e.ex.runtime.session={id:'owner',agent:'codex',from:'claude',generation:1,status:'idle',startedAt:'now',limitRecovery:false,checkpointFile:'',checkpointHash:'',tokenHash:'',actionResults:[]};e.ex.runtime.generation=1;
  const a=grantApproval(e.ex,{basis:'합성: 자동 준비',actions:['prepare_checks'],targets:['task-a']});
  const pending=autoSteps(e.ex,'owner');
  if(change==='approval')revokeApproval(e.ex,a.id);
  if(change==='session')e.ex.runtime.session={...e.ex.runtime.session!,id:'replacement'};
  if(change==='frozen')e.ex.runtime.frozen=true;
  if(change==='stop')e.ex.stopped=true;
  if(change==='guard')e.ex.guardAlert={detail:'synthetic billing signal'} as any;
  if(change==='task-status')t.status='rejected';
  if(change==='task-sha')t.result!.headSha='f'.repeat(40);
  await pending;
  if(change==='none'){
   if(kind==='checks')assert.equal(t.verification!.status,'running');else assert.ok(t.handoff);
  }else{
   assert.equal(t.verification,initial,'검사 새 등록 없음');assert.equal(t.handoff,undefined,'인계 새 등록 없음');
   assert.equal(fs.existsSync(path.join(e.cfg.stateDir,'handoffs')),false);
   const step=Object.values(e.ex.runtime.pipeline!.steps)[0];assert.equal(step.ok,false);assert.match(step.detail,/실패/);
  }
  assert.deepEqual(e.ex.state.executions,{});
 }finally{e.cleanup();}
});

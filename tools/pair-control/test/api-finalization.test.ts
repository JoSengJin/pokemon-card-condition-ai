import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {assign} from '../src/executor/taskAssign.ts';
import {approve,reject} from '../src/executor/taskApproval.ts';
import {integrate} from '../src/executor/taskIntegration.ts';
import {confirmAction} from '../src/executor/mainDispatch.ts';
import {handoffToMain} from '../src/executor/handoffCreate.ts';
import {confirmHandoff} from '../src/executor/handoffRecords.ts';
import {createWorktree} from '../src/executor/prepareWorktree.ts';
import {setMain} from '../src/executor/mainRole.ts';
import {runPostChecks} from '../src/executor/verificationPost.ts';
import {grantApproval,revokeApproval} from '../src/executor/mainApprovals.ts';
import {setup,task,verify,waitFor,type Env} from './helpers.ts';
import {gitGate} from './api-git-gate.ts';
import {serviceTick} from '../src/runtimeServiceTick.ts';
import {dispatchAction} from '../src/executor/actionDispatch.ts';

const git=(cwd:string,...args:string[])=>execFileSync('/usr/bin/git',['-c','user.name=synthetic','-c','user.email=s@local',...args],{cwd,encoding:'utf8'}).trim();
function owner(e:Env){
 if(e.ex.timer){clearInterval(e.ex.timer);e.ex.timer=null;}
 e.ex.runtime.session={id:'owner',agent:'codex',from:'claude',generation:1,status:'idle',startedAt:'now',limitRecovery:false,checkpointFile:'',checkpointHash:'',tokenHash:'',actionResults:[]};e.ex.runtime.generation=1;
 const approval=grantApproval(e.ex,{basis:'합성: API 최종 변경',actions:['approve_task','integrate_task','assign_task','confirm_handoff'],targets:['task-a']});
 return {approval,origin:(action:string)=>({sessionId:'owner',generation:1,lifetime:e.ex.lifetime,action,target:'task-a'})};
}
async function ready(){
 const e=setup();const t=await assign(e.ex,task(e,'task-a',{mode:'manual'}));
 fs.writeFileSync(path.join(t.worktree,'src_a','race.txt'),'synthetic\n');git(t.worktree,'add','src_a/race.txt');git(t.worktree,'commit','-qm','synthetic task');
 const sha=git(t.worktree,'rev-parse','HEAD');t.status='review_pending';t.result={headSha:sha,commits:[{sha}],changedFiles:['src_a/race.txt'],checks:[],checksPassed:true} as any;
 await verify(e,t.taskId);await handoffToMain(e.ex,t.taskId);
 const o=owner(e);return {e,t,sha,...o};
}

for(const change of ['frozen','generation','stop','guard','revoke','reject','verification','handoff'])test(`승인 저장 직전 ${change}이면 승인 기록 없음`,async()=>{
 const {e,t,sha,approval,origin}=await ready();confirmHandoff(e.ex,t.taskId,'합성 확인');
 const gate=gitGate(e.fixture.repo,['rev-parse','--verify','--quiet','refs/heads/main^{commit}']);let pending:Promise<unknown>|undefined;
 try{
  pending=approve(e.ex,t.taskId,sha,{requireHandoff:true,origin:origin('approve_task')} as any);await waitFor(()=>fs.existsSync(gate.entered),'approve final gate');
  if(change==='frozen')e.ex.runtime.frozen=true;if(change==='generation')e.ex.runtime.generation=2;if(change==='stop')e.ex.stopped=true;if(change==='guard')e.ex.guardAlert={detail:'synthetic guard'} as any;
  if(change==='revoke')revokeApproval(e.ex,approval.id);if(change==='reject')reject(e.ex,t.taskId,'synthetic reject');if(change==='verification')t.verification!.status='failed';if(change==='handoff')t.handoff!.cancelledAt='now';
  fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.ok(!t.approval);assert.notEqual(t.status,'approved');
 }finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const change of ['frozen','revoke','verification'])test(`인계 확인 직전 ${change}이면 확인 기록 없음`,async()=>{
 const {e,t,sha,approval,origin}=await ready();
 const a={id:'confirm',type:'confirm_handoff',sha,reviewedFiles:t.result!.changedFiles,note:'synthetic review',diffHash:crypto.createHash('sha256').update(execFileSync('/usr/bin/git',['diff','--binary',t.baseSha,sha],{cwd:t.worktree})).digest('hex')};
 const gate=gitGate(t.worktree,['diff','--binary']);let pending:Promise<unknown>|undefined;
 try{pending=confirmAction(e.ex,a,t.taskId,false,origin('confirm_handoff'));await waitFor(()=>fs.existsSync(gate.entered),'confirm final gate');if(change==='frozen')e.ex.runtime.frozen=true;else if(change==='verification')t.verification!.status='failed';else revokeApproval(e.ex,approval.id);fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.equal(t.handoff!.confirmedAt,undefined);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const change of ['frozen','revoke','verification'])test(`cherry-pick 직전 ${change}이면 통합 checkout 불변`,async()=>{
 const {e,t,sha,approval,origin}=await ready();confirmHandoff(e.ex,t.taskId,'합성 확인');await approve(e.ex,t.taskId,sha,{requireHandoff:true});
 const head=git(e.fixture.repo,'rev-parse','HEAD'),gate=gitGate(t.worktree,['rev-list','--reverse']);let pending:Promise<any>|undefined;
 try{pending=integrate(e.ex,t.taskId,origin('integrate_task'));await waitFor(()=>fs.existsSync(gate.entered),'integration final gate');if(change==='frozen')e.ex.runtime.frozen=true;else if(change==='verification')t.verification!.status='failed';else revokeApproval(e.ex,approval.id);fs.writeFileSync(gate.release,'go');const result=await pending;assert.notEqual(result.outcome,'integrated');assert.equal(git(e.fixture.repo,'rev-parse','HEAD'),head);assert.equal(e.ex.locks.holder('integration'),null);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const change of ['frozen','revoke'])test(`계약 쓰기 직전 ${change}이면 새 계약/배정 없음`,async()=>{
 const e=setup(),{approval,origin}=owner(e),input=task(e,'task-a',{mode:'manual'});const head=git(input.worktree,'rev-parse','HEAD'),gate=gitGate(input.worktree,['config','user.email']);let pending:Promise<unknown>|undefined;
 try{pending=assign(e.ex,input,origin('assign_task'));await waitFor(()=>fs.existsSync(gate.entered),'contract final gate');if(change==='frozen')e.ex.runtime.frozen=true;else revokeApproval(e.ex,approval.id);fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.equal(e.ex.state.tasks['task-a'],undefined);assert.equal(fs.existsSync(path.join(input.worktree,'docs/collaboration/tasks/task-a.md')),false);assert.equal(git(input.worktree,'rev-parse','HEAD'),head);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

test('계약 커밋 뒤 동결되면 등록만 차단하고 계약 커밋 보존',async()=>{
 const e=setup(),{origin}=owner(e),input=task(e,'task-a',{mode:'manual'});const head=git(input.worktree,'rev-parse','HEAD'),gate=gitGate(e.fixture.repo,['worktree','list','--porcelain'],2);let pending:Promise<unknown>|undefined;
 try{pending=assign(e.ex,input,origin('assign_task'));await waitFor(()=>fs.existsSync(gate.entered),'registration gate');e.ex.runtime.frozen=true;fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.equal(e.ex.state.tasks['task-a'],undefined);assert.notEqual(git(input.worktree,'rev-parse','HEAD'),head);assert.equal(fs.existsSync(path.join(input.worktree,'docs/collaboration/tasks/task-a.md')),true);const committed=git(input.worktree,'rev-parse','HEAD');e.ex.runtime.frozen=false;const resumed=await assign(e.ex,input,origin('assign_task'));assert.equal(resumed.contractSha,committed);assert.equal(git(input.worktree,'rev-parse','HEAD'),committed);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const change of ['frozen','revoke'])test(`worktree 생성 직전 ${change}이면 새 경로 없음`,async()=>{
 const e=setup(),{approval,origin}=owner(e),input={...task(e,'task-a'),branch:'claude/new-path',worktree:path.join(e.dir,'new-path')};const gate=gitGate(e.fixture.repo,['show-ref','--verify','--quiet']);let pending:Promise<unknown>|undefined;
 try{pending=createWorktree(e.ex,input as any,origin('assign_task'));await waitFor(()=>fs.existsSync(gate.entered),'worktree final gate');if(change==='frozen')e.ex.runtime.frozen=true;else revokeApproval(e.ex,approval.id);fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.equal(fs.existsSync(input.worktree),false);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const change of ['frozen','generation'])test(`표시 이양 준비 중 ${change}이면 메인 표시 불변`,async()=>{
 const e=setup();owner(e);try{const pending=setMain(e.ex,'claude','synthetic');if(change==='frozen')e.ex.runtime.frozen=true;else e.ex.runtime.generation=2;await assert.rejects(pending);assert.equal(e.ex.mainAgent,'codex');}finally{e.cleanup();}
});

test('stop 뒤 통합 후 검사를 새로 시작하지 않음',async()=>{
 const e=setup();try{const t=await assign(e.ex,task(e,'task-a'));const marker=path.join(e.dir,'executed');t.postChecks=[{id:'post',name:'synthetic',executable:'node',args:['-e','require("fs").writeFileSync(process.argv[1],"ran")',marker],cwd:'.'}];e.ex.stopped=true;const result=await runPostChecks(e.ex,t,e.fixture.repo,path.join(e.fixture.repo,'develop'),{base:t.baseSha,head:t.baseSha,contract:t.contractSha});assert.equal(fs.existsSync(marker),false);assert.equal(result.status,'failed');assert.equal(result.items[0].status,'not_run');}finally{e.cleanup();}
});

for(const service of ['worktree','assign','integrate'] as const)test(`서비스 ${service} 경로가 최종 변경까지 origin을 전달`,async()=>{
 const prepared=service==='integrate'?await ready():null;
 const e=prepared?.e??setup(),o=prepared??owner(e);
 const input={...task(e,'task-a',{mode:'manual'}),...(service==='worktree'?{branch:'claude/service-new',worktree:path.join(e.dir,'service-new')}:{})};
 if(prepared){confirmHandoff(e.ex,'task-a','합성 확인');await approve(e.ex,'task-a',prepared.sha,{requireHandoff:true});}
 const cwd=service==='integrate'?prepared!.t.worktree:service==='assign'?input.worktree:e.fixture.repo;
 const args=service==='integrate'?['rev-list','--reverse']:service==='assign'?['config','user.email']:['show-ref','--verify','--quiet'];
 const head=git(e.fixture.repo,'rev-parse','HEAD'),gate=gitGate(cwd,args);let pending:Promise<unknown>|undefined;
 const origin=o.origin(service==='integrate'?'integrate_task':'assign_task');
 e.ex.state.workflowRequests={parent:{id:'parent',kind:'start',workflow:'prepareTaskWorkflow',stage:'dispatching',lifetime:e.ex.lifetime}};
 const request:any={id:'service',parentId:'parent',service,stage:'queued',origin,payload:{raw:input,taskId:'task-a'}};e.ex.state.serviceRequests={service:request};
 try{pending=serviceTick(e.ex);await waitFor(()=>fs.existsSync(gate.entered),'service final gate');revokeApproval(e.ex,o.approval.id);fs.writeFileSync(gate.release,'go');await pending;assert.equal(git(e.fixture.repo,'rev-parse','HEAD'),head);
  if(service==='integrate')assert.notEqual(request.result?.outcome,'integrated');else{assert.equal(request.stage,'failed');assert.equal(e.ex.state.tasks['task-a'],undefined);if(service==='worktree')assert.equal(fs.existsSync(input.worktree),false);else assert.equal(fs.existsSync(path.join(input.worktree,'docs/collaboration/tasks/task-a.md')),false);}
 }finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

for(const type of ['approve_task','confirm_handoff'])test(`행동 ${type} 경로가 최종 변경까지 origin을 전달`,async()=>{
 const {e,t,sha,approval}=await ready();if(type==='approve_task')confirmHandoff(e.ex,t.taskId,'합성 확인');
 e.ex.resumer=async()=>({} as any);
 const action={id:type,type,taskId:t.taskId,sha,note:'synthetic review',reviewedFiles:t.result!.changedFiles,diffHash:crypto.createHash('sha256').update(execFileSync('/usr/bin/git',['diff','--binary',t.baseSha,sha],{cwd:t.worktree})).digest('hex')};
 const work:any={action,status:'authorized',target:t.taskId};
 const gate=gitGate(type==='approve_task'?e.fixture.repo:t.worktree,type==='approve_task'?['rev-parse','--verify','--quiet','refs/heads/main^{commit}']:['diff','--binary']);let pending:Promise<unknown>|undefined;
 try{pending=dispatchAction(e.ex,e.ex.runtime.session!,work);await waitFor(()=>fs.existsSync(gate.entered),'action final gate');revokeApproval(e.ex,approval.id);fs.writeFileSync(gate.release,'go');await pending;assert.equal(work.result.ok,false);if(type==='approve_task')assert.ok(!t.approval);else assert.equal(t.handoff!.confirmedAt,undefined);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

test('계약 준비 대기 중 생긴 다른 파일을 덮어쓰지 않음',async()=>{
 const e=setup(),{origin}=owner(e),input=task(e,'task-a',{mode:'manual'}),head=git(input.worktree,'rev-parse','HEAD'),gate=gitGate(input.worktree,['config','user.email']);let pending:Promise<unknown>|undefined;
 const file=path.join(input.worktree,'docs/collaboration/tasks/task-a.md');
 try{pending=assign(e.ex,input,origin('assign_task'));await waitFor(()=>fs.existsSync(gate.entered),'foreign contract gate');fs.mkdirSync(path.dirname(file),{recursive:true});fs.writeFileSync(file,'foreign contract');fs.writeFileSync(gate.release,'go');await assert.rejects(pending);assert.equal(fs.readFileSync(file,'utf8'),'foreign contract');assert.equal(git(input.worktree,'rev-parse','HEAD'),head);assert.equal(e.ex.state.tasks['task-a'],undefined);}
 finally{fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate.close();e.cleanup();}
});

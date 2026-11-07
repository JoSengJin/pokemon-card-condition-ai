// 가짜 ps와 신호 기록만 사용한다. 실제 프로세스/모델에는 신호·요청을 보내지 않는다.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {setTimeout as delay} from 'node:timers/promises';
import {cancelRunning} from '../src/executor/processCancel.ts';
import {observeExit} from '../src/executor/monitorRecovery.ts';

function fixture(){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pair-owner-')),mode=path.join(dir,'mode'),spec=path.join(dir,'spec.json'),exit=path.join(dir,'exit.json'),pgid=2147483000;
 fs.writeFileSync(path.join(dir,'package.json'),'{"type":"module"}');fs.writeFileSync(mode,'owned');
 const ps=path.join(dir,'ps');fs.writeFileSync(ps,`#!${process.execPath}\nimport fs from 'node:fs';const mode=fs.readFileSync(${JSON.stringify(mode)},'utf8');if(mode==='gone'){fs.writeFileSync(${JSON.stringify(mode)},'group-gone');process.exit(1);}if(mode==='unknown')process.exit(1);console.log(${pgid}+' node '+(mode==='owned'?${JSON.stringify(spec)}:'foreign-supervisor'));`);fs.chmodSync(ps,0o755);
 const savedPath=process.env.PATH,savedKill=process.kill,signals:any[]=[],audits:any[]=[];
 process.env.PATH=dir+path.delimiter+savedPath;
 process.kill=((pid:number,signal?:string|number)=>{assert.equal(pid,-pgid,'가짜 그룹만 호출');if(signal===0&&fs.readFileSync(mode,'utf8')==='group-gone'){const error:any=new Error('gone');error.code='ESRCH';throw error;}if(signal!==0)signals.push(signal);return true;}) as typeof process.kill;
 const execution:any={execId:'synthetic',taskId:'task-a',kind:'check',status:'running',startedAt:'now',pid:pgid,pgid,specPath:spec,exitPath:exit,token:'synthetic',cancelRequested:false};
 let saves=0;const owner:any={state:{tasks:{'task-a':{taskId:'task-a',status:'review_pending'}},executions:{synthetic:execution}},store:{save(){saves++;}},audit(...args:any[]){audits.push(args);}};
 fs.writeFileSync(exit,JSON.stringify({token:'synthetic',code:0,signal:null,cancelRequested:false,endedAt:'now'}));
 return {dir,mode,execution,owner,signals,audits,cleanup(){process.env.PATH=savedPath;process.kill=savedKill;fs.rmSync(dir,{recursive:true,force:true});}};
}

for(const phase of ['initial-unknown','foreign','unknown','completed','replaced','gone','owned'])test(`중단 예약: ${phase} 소유 상태를 신호 직전에 대조`,async()=>{
 const f=fixture();try{
  if(phase==='initial-unknown')fs.writeFileSync(f.mode,'unknown');
  const result=await cancelRunning(f.owner,'task-a');
  if(phase==='foreign'||phase==='unknown'||phase==='gone')fs.writeFileSync(f.mode,phase);
  if(phase==='completed')f.execution.status='exited';
  if(phase==='replaced')f.owner.state.executions.synthetic={...f.execution};
  await delay(3200);
  assert.equal(result.ok,phase!=='initial-unknown');
  assert.deepEqual(f.signals,phase==='initial-unknown'?[]:phase==='owned'?['SIGTERM','SIGKILL']:['SIGTERM']);
  if(phase==='gone')assert.equal(f.execution.status,'cancelling','이미 사라진 그룹은 종료 관찰이 처리');
  if(phase==='foreign'||phase==='unknown'){assert.equal(f.execution.status,'unknown');assert.equal(f.execution.completion.unknown,true);} 
 }finally{f.cleanup();}
});

for(const phase of ['foreign','unknown','gone','owned'])test(`종료 기록: ${phase} 남은 그룹의 소유를 확인한 뒤 정리`,async()=>{
 const f=fixture();try{fs.writeFileSync(f.mode,phase);await observeExit(f.owner,f.execution);
  assert.deepEqual(f.signals,phase==='owned'?['SIGKILL']:[]);assert.equal(f.execution.status,phase==='owned'||phase==='gone'?'exited':'unknown');assert.equal(f.execution.completion.unknown,phase!=='owned'&&phase!=='gone');
 }finally{f.cleanup();}
});

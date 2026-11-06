// Git 밖 입력 묶음 회귀. 모든 CLI는 임시 stub이며 실제 모델 요청 없음.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {probe} from '../src/executor/adapterProbe.ts';
import {handoverMain} from '../src/executor/mainHandover.ts';
import {assign} from '../src/executor/taskAssign.ts';
import {startReviewJob} from '../src/executor/reviewStart.ts';
import {startTask} from '../src/runtime.ts';
import {fakeCli,setup,task,waitFor,type Env} from './helpers.ts';

function strictCli(e:Env,support=true){
 const dir=path.join(e.dir,'strict-cli'),binary=path.join(dir,'codex'),invoked=path.join(dir,'invoked');fs.mkdirSync(dir);fs.writeFileSync(path.join(dir,'package.json'),'{}');
 fs.writeFileSync(binary,`#!${process.execPath}\nconst fs=require('node:fs'),{spawnSync}=require('node:child_process'),a=process.argv.slice(2);
if(a.includes('--version')){console.log('strict fake codex');process.exit(0);}
if(a.includes('--help')){console.log('--cd --sandbox --json ${support?'--skip-git-repo-check':''}');process.exit(0);}
if(a[0]==='login'&&a[1]==='status'){console.log('Logged in using ChatGPT');process.exit(0);}
fs.writeFileSync(${JSON.stringify(invoked)},JSON.stringify(a));const cwd=a[a.indexOf('--cd')+1],git=spawnSync('git',['rev-parse','--show-toplevel'],{cwd});
if(git.status!==0&&!a.includes('--skip-git-repo-check')){console.error('Not inside a trusted directory and --skip-git-repo-check was not specified.');process.exit(77);}
const r=spawnSync(${JSON.stringify(process.execPath)},[${JSON.stringify(fakeCli.codex)},...a],{cwd,env:process.env,stdio:'inherit'});process.exit(r.status??1);
`);fs.chmodSync(binary,0o755);e.cfg.cli.codex=binary;return {binary,invoked};
}

for(const kind of ['main','review'])test(`Git 밖 Codex ${kind} 입력 묶음은 읽기 전용으로 실행`,async()=>{
 const e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{...fakeCli}});const f=strictCli(e);
 try{
  let run;
  if(kind==='main'){
   e.ex.state.main={agent:'claude',since:'synthetic'};await handoverMain(e.ex,'codex');
   const session=await waitFor(()=>e.ex.runtime.session&&['idle','completed'].includes(e.ex.runtime.session.status)?e.ex.runtime.session:e.ex.runtime.history.at(-1)?.status==='failed'?e.ex.runtime.history.at(-1):null,'main end');
   assert.equal(session!.status,'idle');assert.equal(e.ex.mainAgent,'codex');run=e.ex.state.executions[session!.execId!];
  }else{
   await assign(e.ex,task(e,'task-a'));await startTask('task-a');await waitFor(()=>e.ex.state.tasks['task-a'].status==='review_pending','result');
   await startReviewJob(e.ex,'task-a',{mode:'real',reviewer:'codex'});const review=await waitFor(()=>{const r=e.ex.state.tasks['task-a'].review;return r&&r.status!=='running'?r:null;},'review end');
   assert.equal(review.status,'done');assert.equal(review.verdict,'approve');run=e.ex.state.executions[review.execId!];
  }
  assert.throws(()=>execFileSync('git',['rev-parse','--show-toplevel'],{cwd:JSON.parse(fs.readFileSync(run.specPath,'utf8')).cwd,stdio:'pipe'}));
  const args=JSON.parse(fs.readFileSync(f.invoked,'utf8'));assert.ok(args.includes('--skip-git-repo-check'));assert.equal(args[args.indexOf('--sandbox')+1],'read-only');
 }finally{e.cleanup();}
});

test('Git 밖 실행 옵션을 지원하지 않는 Codex는 모델 시작 전에 차단',async()=>{
 const e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true});const f=strictCli(e,false);
 try{e.ex.probes.codex=await probe('codex',e.cfg);assert.ok(e.ex.probes.codex.missingFlags.includes('--skip-git-repo-check'));await assert.rejects(e.ex.launchMainProcess({agent:'codex',bundleDir:e.dir,prompt:'synthetic never dispatched',sessionId:'synthetic'}),/확인되지 않은 옵션/);assert.equal(fs.existsSync(f.invoked),false);assert.deepEqual(e.ex.state.executions,{});}finally{e.cleanup();}
});

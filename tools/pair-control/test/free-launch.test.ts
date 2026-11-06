// 무료 조건 변경 반례. 모든 CLI는 이 파일이 만든 stub이며 실제 모델 요청 없음.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { assign } from '../src/executor/taskAssign.ts';
import { launch } from '../src/executor/taskLaunch.ts';
import { startReviewJob } from '../src/executor/reviewStart.ts';
import { stop } from '../src/executor/monitorSchedule.ts';
import { setup, task, waitFor } from './helpers.ts';

function cli(agent: 'codex'|'claude', gated=false) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pair-free-launch-'));
  const binary=path.join(dir,agent), marker=path.join(dir,'probe'), release=path.join(dir,'release'), invoked=path.join(dir,'invoked');
  fs.writeFileSync(binary,`#!${process.execPath}\nimport fs from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const a=process.argv.slice(2);
if(a.includes('--version')) { if(${gated}) { fs.writeFileSync(${JSON.stringify(marker)},'probe'); while(!fs.existsSync(${JSON.stringify(release)})) await delay(10); } console.log('fake ${agent} 1'); process.exit(0); }
if(a.includes('--help')) { console.log('--cd --sandbox --json --print --permission-mode --allowedTools'); process.exit(0); }
if(a[0]==='login'&&a[1]==='status') { console.log('Logged in using ChatGPT'); process.exit(0); }
fs.writeFileSync(${JSON.stringify(invoked)},'fake model command'); process.exit(0);
`);fs.chmodSync(binary,0o755);
  return {dir,binary,marker,release,invoked,cleanup:()=>fs.rmSync(dir,{recursive:true,force:true})};
}

function setting(dir:string, provider:'claude'|'codex', profile=false) {
  fs.mkdirSync(path.join(dir,`.${provider}`),{recursive:true});
  fs.writeFileSync(path.join(dir,`.${provider}`,provider==='claude'?'settings.json':'config.toml'),provider==='claude'?JSON.stringify({apiKeyHelper:'synthetic-helper'}):profile?'profile = "unverified-profile"\n':'model_provider = "unverified-provider"\n');
}

for(const change of ['env','settings','profile']) test(`구현: probe 대기 중 ${change} 변경은 실제 시작 전에 차단`,async()=>{
  const agent=change==='settings'?'claude':'codex',f=cli(agent,true),e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{[agent]:f.binary}});
  const previous=process.env.OPENAI_API_KEY;
  let pending:Promise<unknown>|undefined;
  try {
    const t=await assign(e.ex,task(e,agent==='claude'?'task-a':'task-b',{mode:'real',allowedFiles:[agent==='claude'?'src_a/':'src_b/']}));
    pending=launch(e.ex,t.taskId,'synthetic');
    await waitFor(()=>fs.existsSync(f.marker),'probe entered');
    if(change==='env') process.env.OPENAI_API_KEY='synthetic-not-a-key';
    else setting(e.cfg.homeDir!,agent,change==='profile');
    fs.writeFileSync(f.release,'continue');
    const result=await pending as {ok:boolean;reason?:string};
    assert.equal(result.ok,false,result.reason ?? '실행은 거절되어야 함');
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(fs.existsSync(f.invoked),false);
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`),null);
  } finally {
    if(previous===undefined) delete process.env.OPENAI_API_KEY;else process.env.OPENAI_API_KEY=previous;
    fs.writeFileSync(f.release,'cleanup');await pending?.catch(()=>{});e.cleanup();f.cleanup();
  }
});

function gitGate(worktree:string) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pair-fingerprint-gate-')),marker=path.join(dir,'fingerprint'),release=path.join(dir,'release');
  const original=process.env.PATH,realGit=execFileSync('/usr/bin/which',['git'],{encoding:'utf8'}).trim(),binary=path.join(dir,'git');
  fs.writeFileSync(binary,`#!${process.execPath}\nimport fs from 'node:fs';
import { spawnSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
const a=process.argv.slice(2);
if(process.cwd()===${JSON.stringify(worktree)}&&a[0]==='status'&&a.includes('--porcelain=v1')) { fs.writeFileSync(${JSON.stringify(marker)},'fingerprint'); while(!fs.existsSync(${JSON.stringify(release)})) await delay(10); }
const r=spawnSync(${JSON.stringify(realGit)},a,{cwd:process.cwd(),env:process.env});process.stdout.write(r.stdout??'');process.stderr.write(r.stderr??'');process.exit(r.status??1);
`);fs.chmodSync(binary,0o755);process.env.PATH=dir+path.delimiter+original;
  return {marker,release,cleanup(){process.env.PATH=original;fs.rmSync(dir,{recursive:true,force:true});}};
}

for(const change of ['subscription','allow','limit','stop','guard','frozen']) test(`리뷰: fingerprint 대기 중 ${change} 변경은 실제 시작 전에 차단`,async()=>{
  const f=cli('codex'),e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{codex:f.binary}});
  let gate:ReturnType<typeof gitGate>|undefined,pending:Promise<unknown>|undefined;
  try {
    const t=await assign(e.ex,task(e,'task-a',{mode:'manual'}));
    t.status='review_pending';t.result={headSha:execFileSync('/usr/bin/git',['rev-parse','HEAD'],{cwd:t.worktree,encoding:'utf8'}).trim(),checks:[],checksPassed:true} as any;
    gate=gitGate(t.worktree);pending=startReviewJob(e.ex,t.taskId,{mode:'real',reviewer:'codex'});
    await waitFor(()=>fs.existsSync(gate!.marker),'fingerprint entered');
    if(change==='subscription')e.cfg.confirmedSubscriptionAuth=false;
    if(change==='allow')e.cfg.allowRealModelCalls=false;
    if(change==='limit')e.ex.runtime.limited.codex={at:'now',detail:'synthetic limit'};
    if(change==='stop')stop(e.ex);
    if(change==='guard')e.ex.guardAlert={detail:'synthetic billing signal'} as any;
    if(change==='frozen')e.ex.runtime.frozen=true;
    fs.writeFileSync(gate.release,'continue');
    await assert.rejects(pending);
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(e.ex.locks.holder(`review:${t.taskId}`),null);
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {
    if(gate)fs.writeFileSync(gate.release,'cleanup');await pending?.catch(()=>{});gate?.cleanup();e.cleanup();f.cleanup();
  }
});

for(const change of ['stop','cwd-settings','profile']) test(`메인: ${change}이면 프로세스 시작 거절`,async()=>{
  const agent=change==='cwd-settings'?'claude':'codex',f=cli(agent),e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{[agent]:f.binary}});
  try {
    const bundle=path.join(e.dir,'main-bundle');fs.mkdirSync(bundle);
    e.ex.probes[agent]={agent,binary:f.binary,installed:true,version:'fake',verifiedFlags:[],missingFlags:[],note:'fake',checkedAt:'',loginStatus:'Logged in using ChatGPT'};
    if(change==='stop')stop(e.ex);
    if(change==='cwd-settings')setting(bundle,'claude');
    if(change==='profile')setting(e.cfg.homeDir!,'codex',true);
    await assert.rejects(e.ex.launchMainProcess({agent,bundleDir:bundle,prompt:'synthetic',sessionId:'synthetic'}));
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {e.cleanup();f.cleanup();}
});

test('리뷰: 실제 실행 bundle의 Claude 과금 설정도 검사',async()=>{
  const f=cli('claude',true),e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{claude:f.binary}});let pending:Promise<unknown>|undefined;
  try {
    const t=await assign(e.ex,task(e,'task-b',{mode:'manual',allowedFiles:['src_b/']}));
    t.status='review_pending';t.result={headSha:execFileSync('/usr/bin/git',['rev-parse','HEAD'],{cwd:t.worktree,encoding:'utf8'}).trim(),checks:[],checksPassed:true} as any;
    pending=startReviewJob(e.ex,t.taskId,{mode:'real',reviewer:'claude'});
    await waitFor(()=>fs.existsSync(f.marker),'review probe entered');
    const reviews=path.join(e.cfg.stateDir,'reviews'),bundle=path.join(reviews,fs.readdirSync(reviews)[0]);setting(bundle,'claude');
    fs.writeFileSync(f.release,'continue');await assert.rejects(pending);
    assert.deepEqual(e.ex.state.executions,{});assert.equal(fs.existsSync(f.invoked),false);
  } finally {fs.writeFileSync(f.release,'cleanup');await pending?.catch(()=>{});e.cleanup();f.cleanup();}
});

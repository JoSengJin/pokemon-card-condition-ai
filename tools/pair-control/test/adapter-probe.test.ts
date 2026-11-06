// CLI 점검 실패 반례. 이 파일은 자체 fake CLI만 실행한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { probe } from '../src/executor/adapterProbe.ts';
import { realPlan } from '../src/executor/adapterPlan.ts';
import { realReadiness } from '../src/executor/adapterReadiness.ts';
import { codexLoginIsChatgpt } from '../src/executor/codexSettings.ts';
import type { PairConfig } from '../src/executor/config.ts';
import type { TaskInputT } from '../src/executor/contract.ts';
import { assign } from '../src/executor/taskAssign.ts';
import { launch } from '../src/executor/taskLaunch.ts';
import { setup, task, toolRoot } from './helpers.ts';

function fake(options: { helpCode?: number; loginCode?: number; loginText?: string } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pair-probe-'));
  const binary = path.join(dir, 'codex'), invoked = path.join(dir, 'invoked');
  fs.writeFileSync(binary, `#!${process.execPath}\nimport fs from 'node:fs';
const args=process.argv.slice(2);
if(args.includes('--version')) { console.log('fake-codex 1'); process.exit(0); }
if(args[0]==='exec' && args.includes('--help')) { console.log('--cd <DIR> --sandbox <MODE> --json'); process.exit(${options.helpCode ?? 0}); }
if(args[0]==='login' && args[1]==='status') { console.log(${JSON.stringify(options.loginText ?? 'Logged in using ChatGPT')}); process.exit(${options.loginCode ?? 0}); }
fs.writeFileSync(${JSON.stringify(invoked)}, 'unexpected model command'); process.exit(88);
`);fs.chmodSync(binary, 0o755);
  const cfg: PairConfig = { repo:dir, integration:{checkout:dir,branch:'main'}, worktreeRoot:dir, port:4111, toolRoot, stateDir:dir, homeDir:dir, cli:{codex:binary}, allowRealModelCalls:true, confirmedSubscriptionAuth:true, streamOutput:true };
  const input = { taskId:'synthetic', agent:'codex', worktree:dir, goal:'synthetic' } as TaskInputT;
  return { dir,cfg,input,invoked,cleanup:()=>fs.rmSync(dir,{recursive:true,force:true}) };
}

test('help가 실패하면 출력에 옵션 이름이 있어도 확인된 옵션·stream으로 인정하지 않는다', async () => {
  const f=fake({helpCode:1});
  try {
    const p=await probe('codex',f.cfg);
    assert.deepEqual(p.verifiedFlags,[]);
    assert.deepEqual(p.missingFlags,['--cd','--sandbox']);
    assert.equal(p.stream,false);
    assert.ok('refused' in realPlan(f.input,p,f.cfg));
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {f.cleanup();}
});

test('login status 실패는 ChatGPT 문구를 출력해도 로그인 성공으로 인정하지 않고 출력도 노출하지 않는다', async () => {
  const f=fake({loginCode:1,loginText:'Logged in using ChatGPT synthetic-private-detail'});
  try {
    const p=await probe('codex',f.cfg);
    assert.equal(codexLoginIsChatgpt(p.loginStatus),false);
    assert.equal(p.loginStatus?.includes('synthetic-private-detail'),false);
    assert.ok(realReadiness('codex',p,f.cfg,{env:{}}).blockers.some(b=>b.code==='login_not_chatgpt'));
    assert.ok('refused' in realPlan(f.input,p,f.cfg));
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {f.cleanup();}
});

test('로그인 판정은 부정·만료·설명 문장의 부분 일치를 성공으로 인정하지 않는다', () => {
  for(const text of ['Not logged in using ChatGPT','Logged in using ChatGPT but expired','error: previously logged in using ChatGPT']) assert.equal(codexLoginIsChatgpt(text),false,text);
  assert.equal(codexLoginIsChatgpt('Logged in using ChatGPT'),true);
  assert.equal(codexLoginIsChatgpt('  Logged in using ChatGPT  '),true);
});

test('실행 계획도 API key 로그인과 미확인을 거절하며 정상 ChatGPT 로그인만 허용한다', async () => {
  for(const text of ['Logged in using an API key','', 'Logged in using ChatGPT']) {
    const f=fake({loginText:text});
    try {
      const p=await probe('codex',f.cfg),plan=realPlan(f.input,p,f.cfg);
      assert.equal('refused' in plan,text!=='Logged in using ChatGPT');
      assert.equal(fs.existsSync(f.invoked),false);
    } finally {f.cleanup();}
  }
});

test('직접 작업 시작도 API key 로그인이면 감독 프로세스·모델 명령을 시작하지 않는다', async () => {
  const f=fake({loginText:'Logged in using an API key'});
  const e=setup({allowRealModelCalls:true,confirmedSubscriptionAuth:true,cli:{codex:f.cfg.cli.codex}});
  try {
    const t=await assign(e.ex,task(e,'task-b',{mode:'real',allowedFiles:['src_b/']}));
    const result=await launch(e.ex,t.taskId,'synthetic');
    assert.equal(result.ok,false);
    assert.deepEqual(e.ex.state.executions,{});
    assert.equal(fs.existsSync(f.invoked),false);
    assert.equal(e.ex.locks.holder(`task:${t.taskId}`),null);
  } finally {e.cleanup();f.cleanup();}
});

test('설치 CLI의 알려진 PATH alias 경고는 로그인 결과에서 분리한다', async () => {
  const f=fake({loginText:'WARNING: proceeding, even though we could not create PATH aliases: Operation not permitted (os error 1)\nLogged in using ChatGPT'});
  try {
    const p=await probe('codex',f.cfg);
    assert.equal(p.loginStatus,'Logged in using ChatGPT');
    assert.ok(!('refused' in realPlan(f.input,p,f.cfg)));
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {f.cleanup();}
});

test('알 수 없는 동반 로그인 출력은 성공으로 추정하지 않으며 원문을 상태에 노출하지 않는다', async () => {
  const f=fake({loginText:'Logged in using ChatGPT\nsynthetic-private-detail'});
  try {
    const p=await probe('codex',f.cfg);
    assert.equal(p.loginStatus,'ChatGPT 구독 로그인 미확인');
    assert.ok('refused' in realPlan(f.input,p,f.cfg));
    assert.equal(fs.existsSync(f.invoked),false);
  } finally {f.cleanup();}
});

// 로컬 가짜 child와 합성 파일만 사용한다. 실제 모델/CLI/API 호출 없음.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {readNewLog} from '../src/executor/processLog.ts';
import {outputSignals} from '../src/executor/streamGuard.ts';

function fixture(){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pair-stream-boundary-')),log=path.join(dir,'output.log'),owner:any={logOffsets:new Map()},record:any={execId:'synthetic',logPath:log};return {dir,log,owner,record};}

test('감독자는 나뉜 비밀값/UTF-8·stderr를 가리고 마지막 JSON도 온전한 줄로 기록',()=>{
 const f=fixture(),secret=['sk','ant','syntheticabcdefghijklmnopqrstuv'].join('-'),child=path.join(f.dir,'fake-child.mjs'),spec=path.join(f.dir,'spec.json'),exit=path.join(f.dir,'exit.json');
 try{
  fs.writeFileSync(child,`import {setTimeout as delay} from 'node:timers/promises';
const secret=${JSON.stringify(secret)},bytes=Buffer.from('한글');
process.stdout.write(secret.slice(0,4));await delay(40);process.stdout.write(secret.slice(4)+'\\n');
process.stdout.write(bytes.subarray(0,1));await delay(40);process.stdout.write(bytes.subarray(1));process.stdout.write('\\n');
process.stderr.write(secret.slice(0,5));await delay(40);process.stderr.write(secret.slice(5));
process.stdout.write(JSON.stringify({type:'assistant',message:{content:'credit balance synthetic documentation'}}));
`);
  fs.writeFileSync(spec,JSON.stringify({execId:'synthetic',token:'synthetic',cwd:f.dir,command:process.execPath,args:[child],env:{PATH:process.env.PATH},logPath:f.log,exitPath:exit}));
  execFileSync(process.execPath,[path.resolve('src/executor/supervisor.mjs'),spec],{stdio:'pipe'});
  const text=fs.readFileSync(f.log,'utf8');assert.equal(text.includes(secret),false,'청크에 나뉜 값도 가림');assert.ok(text.includes('한글'));assert.equal(text.includes('�'),false);assert.ok(text.includes('[stderr] [REDACTED]'));
  assert.deepEqual(outputSignals(readNewLog(f.owner,f.record)??'','synthetic'),[],'내용 JSON 마지막 줄을 시스템 로그와 합쳐 오탐하지 않음');assert.equal(JSON.parse(fs.readFileSync(exit,'utf8')).code,0);
 }finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

test('1MB를 넘는 내용 JSON은 잘리지 않고 다음 실제 과금 오류만 감지',()=>{
 const f=fixture();try{const content=JSON.stringify({type:'assistant',message:{content:'credit balance 문서 '+ '가'.repeat(400000)}})+'\n',error=JSON.stringify({type:'error',message:'Your credit balance is too low'})+'\n';fs.writeFileSync(f.log,content+error);const first=readNewLog(f.owner,f.record)??'';assert.ok(first===content,'JSON 한 줄 전체를 반환');assert.deepEqual(outputSignals(first,'synthetic'),[]);const second=readNewLog(f.owner,f.record)??'';assert.equal(second,error);assert.equal(outputSignals(second,'synthetic')[0].kind,'paid');assert.equal(readNewLog(f.owner,f.record),undefined);}finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

test('1MB 넘는 미완성 JSON은 byte offset을 보존하고 완성 뒤 한 번 읽음',()=>{
 const f=fixture();try{const content=JSON.stringify({type:'user',message:{content:'credit balance '+ 'x'.repeat(1100000)}});fs.writeFileSync(f.log,content.slice(0,-2));assert.equal(readNewLog(f.owner,f.record),'');assert.equal(f.owner.logOffsets.get('synthetic'),0);fs.appendFileSync(f.log,content.slice(-2)+'\n');assert.ok(readNewLog(f.owner,f.record)===content+'\n','완성 JSON을 한번 읽음');assert.deepEqual(outputSignals(content,'synthetic'),[]);assert.equal(readNewLog(f.owner,f.record),undefined);}finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

test('일반 텍스트 1MB 경계의 UTF-8은 다음 읽기와 합쳐 원문 그대로',()=>{
 const f=fixture();try{const text='x'.repeat(999999)+'한글\n';fs.writeFileSync(f.log,text);const first=readNewLog(f.owner,f.record)??'',second=readNewLog(f.owner,f.record)??'';assert.ok(first+second===text,'byte 경계에서 UTF-8 보존');assert.equal(f.owner.logOffsets.get('synthetic'),Buffer.byteLength(text));}finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

test('줄바꿈 없는 일반 과금 텍스트는 여전히 즉시 감지',()=>{
 const f=fixture();try{fs.writeFileSync(f.log,'Your credit balance is too low');const signals=outputSignals(readNewLog(f.owner,f.record)??'','synthetic');assert.equal(signals.length,1);assert.equal(signals[0].kind,'paid');}finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

test('감독자 실행 파일 오류도 종료 기록을 남기고 로그 버퍼 정리를 마침',()=>{
 const f=fixture(),spec=path.join(f.dir,'spec.json'),exit=path.join(f.dir,'exit.json');try{
  fs.writeFileSync(spec,JSON.stringify({execId:'synthetic',token:'synthetic',cwd:f.dir,command:path.join(f.dir,'missing-child'),args:[],env:{PATH:process.env.PATH},logPath:f.log,exitPath:exit}));
  execFileSync(process.execPath,[path.resolve('src/executor/supervisor.mjs'),spec],{stdio:'pipe'});const result=JSON.parse(fs.readFileSync(exit,'utf8'));assert.equal(result.token,'synthetic');assert.equal(result.spawnError,'ENOENT');assert.equal(result.code,null);assert.match(fs.readFileSync(f.log,'utf8'),/실행 실패: ENOENT/);
 }finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});

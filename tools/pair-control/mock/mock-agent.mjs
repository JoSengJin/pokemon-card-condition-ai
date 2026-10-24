#!/usr/bin/env node
// mock 에이전트. 모델 요청 없이 실제 CLI처럼 로그를 내고 worktree에 커밋한다.
import { execFileSync, spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const arg = (name) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : undefined; };
const scenario = arg('scenario') ?? 'success';
const task = arg('task') ?? 'unknown';
const allowed = arg('allowed') ?? 'mock-output.txt';
const counter = arg('counter');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const git = (...a) => execFileSync('git', ['-c', 'user.name=mock-agent', '-c', 'user.email=mock@localhost', ...a], { stdio: 'pipe' }).toString();

if (counter) fs.appendFileSync(counter, JSON.stringify({ task, scenario, pid: process.pid, at: new Date().toISOString() }) + '\n');
console.log(`[mock] task=${task} scenario=${scenario} pid=${process.pid} cwd=${process.cwd()}`);
console.log('[mock] 모델 요청 없음 · 토큰/비용 미측정');

async function commit(file, steps) {
  for (let i = 1; i <= steps; i++) { console.log(`[mock] 작업 중 ${i}/${steps}`); await sleep(250); }
  fs.mkdirSync(path.dirname(file) || '.', { recursive: true });
  fs.appendFileSync(file, `mock change for ${task} at ${new Date().toISOString()}\n`);
  git('add', '--', file);
  git('commit', '-q', '-m', `feat(mock): ${task} 변경`);
  console.log(`[mock] 커밋 ${git('rev-parse', 'HEAD').trim()}`);
}

const target = allowed.endsWith('/') ? `${allowed}mock-${task}.txt` : allowed;
switch (scenario) {
  case 'success': await commit(target, 4); break;
  case 'slow-success': await commit(target, 12); break;
  case 'touch-forbidden': await commit('outside-scope.txt', 2); break;
  case 'fail': console.log('[mock] 검사 실패를 흉내냄'); await sleep(300); process.exit(3);
  case 'paid-message': console.log('Your credit balance is too low to continue.'); setInterval(() => {}, 1000); break;
  case 'spawn-child': {
    const child = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { stdio: 'ignore' });
    console.log(`[mock] grandchild pid=${child.pid}`);
    setInterval(() => console.log('[mock] heartbeat'), 500);
    break;
  }
  case 'hang': setInterval(() => console.log('[mock] heartbeat'), 500); break;
  default: console.error(`unknown scenario ${scenario}`); process.exit(2);
}

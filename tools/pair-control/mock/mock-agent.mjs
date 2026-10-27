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
const contract = arg('contract');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const git = (...a) => execFileSync('git', ['-c', 'user.name=mock-agent', '-c', 'user.email=mock@localhost', ...a], { stdio: 'pipe' }).toString();

if (counter) fs.appendFileSync(counter, JSON.stringify({ task, scenario, pid: process.pid, at: new Date().toISOString() }) + '\n');
console.log(`[mock] task=${task} scenario=${scenario} pid=${process.pid} cwd=${process.cwd()}`);
console.log('[mock] 모델 요청 없음 · 토큰/비용 미측정');
if (contract) console.log(`[mock] 계약 읽음: ${fs.existsSync(contract) ? fs.readFileSync(contract, 'utf8').split('\n')[0] : '(없음)'}`);

async function commit(file, steps) {
  for (let i = 1; i <= steps; i++) { console.log(`[mock] 작업 중 ${i}/${steps}`); await sleep(250); }
  fs.mkdirSync(path.dirname(file) || '.', { recursive: true });
  fs.appendFileSync(file, `mock change for ${task} at ${new Date().toISOString()}\n`);
  git('add', '--', file);
  git('commit', '-q', '-m', `feat(mock): ${task} 변경`);
  console.log(`[mock] 커밋 ${git('rev-parse', 'HEAD').trim()}`);
}

// 실제 CLI의 줄 단위 이벤트(JSONL)를 흉내 낸다. 모델 요청 없음. apiKeySource·내용 이벤트·오류 이벤트는 가드 검사용.
const ev = (o) => console.log(JSON.stringify(o));
const init = (apiKeySource) => ev({ type: 'system', subtype: 'init', cwd: process.cwd(), session_id: 'mock', model: 'mock-model', tools: ['Bash', 'Edit', 'Read'], apiKeySource });
const say = (text) => ev({ type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text }] } });
const tool = (name, input) => ev({ type: 'assistant', message: { role: 'assistant', content: [{ type: 'tool_use', id: 't1', name, input }] } });
const result = (content, is_error = false) => ev({ type: 'user', message: { role: 'user', content: [{ type: 'tool_result', tool_use_id: 't1', content, is_error }] } });

const target = allowed.endsWith('/') ? `${allowed}mock-${task}.txt` : allowed;
switch (scenario) {
  case 'success': await commit(target, 4); break;
  case 'slow-success': await commit(target, 12); break;
  case 'touch-forbidden': await commit('outside-scope.txt', 2); break;
  case 'edit-contract': await commit(contract, 2); break;
  case 'fail': console.log('[mock] 검사 실패를 흉내냄'); await sleep(300); process.exit(3);
  case 'paid-message': console.log('Your credit balance is too low to continue.'); setInterval(() => {}, 1000); break;
  case 'spawn-child': {
    const child = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { stdio: 'ignore' });
    console.log(`[mock] grandchild pid=${child.pid}`);
    setInterval(() => console.log('[mock] heartbeat'), 500);
    break;
  }
  case 'stream': {
    init('none'); say('계약을 읽겠습니다.'); tool('Read', { file_path: contract ?? 'docs/x.md' }); result('# 작업 계약\n목표 …');
    tool('Bash', { command: 'git status --short' }); result('');
    await commit(target, 2);
    ev({ type: 'result', subtype: 'success', is_error: false, duration_ms: 1500, num_turns: 3, result: '완료했습니다.' });
    break;
  }
  case 'stream-quote': {
    // 에이전트가 과금 문구가 들어 있는 파일을 읽거나 쓰는 상황: 내용 이벤트라 서비스가 종료되면 안 된다.
    init('none'); say('billing 관련 코드를 확인합니다. credit balance 문구가 상수에 있습니다.');
    tool('Read', { file_path: 'src/executor/paidSignals.mjs' });
    result('export const PAID_LOG_HARD = [/credit balance/i, /payment required/i]; // extra usage, billing');
    await commit(target, 2);
    ev({ type: 'result', subtype: 'success', is_error: false, duration_ms: 900, num_turns: 2, result: '문서에 credit balance 와 billing 이 나옵니다.' });
    break;
  }
  case 'stream-api-key': init('user'); setInterval(() => {}, 1000); break;
  case 'stream-error-event': init('none'); ev({ type: 'assistant', error: 'billing_error', message: { role: 'assistant', content: [{ type: 'text', text: 'x' }] } }); setInterval(() => {}, 1000); break;
  case 'hang': setInterval(() => console.log('[mock] heartbeat'), 500); break;
  default: console.error(`unknown scenario ${scenario}`); process.exit(2);
}

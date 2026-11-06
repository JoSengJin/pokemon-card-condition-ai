// 메인 턴 실행 준비 대기 반례. 자체 CLI는 version/help/login metadata만 제공하며 모델 실행은 stub으로 센다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { assign } from '../src/executor/taskAssign.ts';
import { grantApproval, revokeApproval } from '../src/executor/mainApprovals.ts';
import { tick } from '../src/executor/monitorTick.ts';
import { pipe } from '../src/executor/pipelineState.ts';
import { setup, task, waitFor } from './helpers.ts';

function gatedCli() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pair-turn-start-'));
  const binary = path.join(dir, 'codex.mjs'), entered = path.join(dir, 'entered'), release = path.join(dir, 'release');
  fs.writeFileSync(binary, `#!${process.execPath}\nimport fs from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
const a=process.argv.slice(2);
if(a.includes('--version')){fs.writeFileSync(${JSON.stringify(entered)},'probe');while(!fs.existsSync(${JSON.stringify(release)}))await delay(10);console.log('fake codex');}
else if(a.includes('--help'))console.log('--cd --sandbox --skip-git-repo-check --json');
else if(a[0]==='login'&&a[1]==='status')console.log('Logged in using ChatGPT');
else process.exit(99);
`);
  fs.chmodSync(binary, 0o755);
  return { dir, binary, entered, release };
}

async function queued(mixed=false) {
  const cli = gatedCli(), e = setup({ cli: { codex: cli.binary } });
  const session: any = { id: 'session', generation: 1, agent: 'codex', from: 'claude', status: 'idle', startedAt: new Date().toISOString(), limitRecovery: false, checkpointFile: '', checkpointHash: '', tokenHash: '', actionResults: [] };
  e.ex.runtime.session = session; e.ex.runtime.generation = 1;
  const keys: string[] = [], approvals = [];
  for (const id of mixed ? ['task-a','task-b'] : ['task-a']) {
    const t = await assign(e.ex, task(e, id, { allowedFiles: [id==='task-a'?'src_a/':'src_b/'] }));
    t.status = 'approved'; t.approval = { sha: t.baseSha } as any;
    approvals.push(grantApproval(e.ex, { basis: '합성: 실행 직전 승인', actions: ['integrate_task'], targets: [id] }));
    const key = `approved:${id}:${t.baseSha}`;keys.push(key);
    pipe(e.ex).events[key] = { key, kind: 'approved', taskId: id, sha: t.baseSha, at: session.startedAt, state: 'pending', tried: [] };
  }
  pipe(e.ex).launch = { sessionId: session.id, generation: 1, eventKeys: keys, stage: 'queued' };
  const calls: {bundleDir:string}[] = [];
  e.ex.launchMainProcess = async (input) => { calls.push(input); return 'fake-execution'; };
  return { e, cli, keys, approvals, calls, session };
}

for (const change of ['session','generation','frozen','approval','condition','task-status','task-sha','mixed']) test(`메인 턴: probe 대기 중 ${change} 변경이면 오래된 요청 시작 없음`, async () => {
  const { e, cli, keys, approvals, calls, session } = await queued(change === 'mixed');
  let pending: Promise<void> | undefined;
  try {
    pending = tick(e.ex);
    await waitFor(() => fs.existsSync(cli.entered), 'fake probe entered');
    if (change === 'session') e.ex.runtime.session = { ...session, id: 'replacement', generation: 2 };
    if (change === 'generation') e.ex.runtime.generation = 2;
    if (change === 'frozen') e.ex.runtime.frozen = true;
    if (change === 'approval' || change === 'mixed') revokeApproval(e.ex, approvals[0].id);
    if (change === 'condition') approvals[0].conditions = '사람이 확인해야 하는 변경 조건';
    if (change === 'task-status') e.ex.state.tasks['task-a'].status = 'review_pending';
    if (change === 'task-sha') e.ex.state.tasks['task-a'].approval!.sha = 'f'.repeat(40);
    fs.writeFileSync(cli.release, 'continue');await pending;
    assert.equal(calls.length, 0, '변경 전 입력 묶음으로 모델 요청하지 않음');
    const first = Object.values(pipe(e.ex).turns)[0];
    if (['session','generation','frozen'].includes(change)) {
      assert.equal(first.status, 'stale');assert.equal(pipe(e.ex).events[keys[0]].state, 'pending');
    } else {
      assert.equal(first.status, 'failed');assert.equal(pipe(e.ex).events[keys[0]].state, 'held');
      if (change === 'mixed') {
        assert.equal(pipe(e.ex).events[keys[1]].state, 'pending');
        assert.ok(!pipe(e.ex).events[keys[1]].tried.includes(1), '실행하지 않은 독립 작업은 같은 세대 최초 실행 가능');
        await tick(e.ex);await tick(e.ex);
        assert.equal(calls.length, 1);
        const rows = JSON.parse(fs.readFileSync(path.join(calls[0].bundleDir, 'EVENTS.json'), 'utf8')).events;
        assert.deepEqual(rows.map((row:any) => row.taskId), ['task-b']);
      }
      if (change === 'approval' || change === 'task-status') {
        if (change === 'approval') grantApproval(e.ex, {basis:'합성: 다시 열린 승인',actions:['integrate_task'],targets:['task-a']});
        else e.ex.state.tasks['task-a'].status = 'approved';
        await tick(e.ex);await tick(e.ex);
        assert.equal(calls.length, 1, '요청 전 보류였으므로 조건이 다시 열리면 최초 실행');
      }
    }
  } finally {
    fs.writeFileSync(cli.release, 'cleanup');await pending?.catch(() => {});e.cleanup();fs.rmSync(cli.dir,{recursive:true,force:true});
  }
});

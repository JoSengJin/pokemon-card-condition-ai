import { assertMainActive } from './executorPolicy.ts';
import { authorize } from './approvalGate.ts';
import type { Executor } from './executor.ts';
import type { RuntimeOrigin } from '../runtimeRequests.ts';
import { sha256 } from './contentHash.ts';
export { sha256 } from './contentHash.ts';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { renderContract } from './contractRender.ts';
import type { TaskInputT } from './contract.ts';

export const contractPath = (taskId: string) => `docs/collaboration/tasks/${taskId}.md`;


export interface ContractCommit { contractSha: string; contractHash: string; reused: boolean }

export async function commitContract(worktree: string, t: TaskInputT, context?: { ex: Executor; origin?: RuntimeOrigin; generation: number }): Promise<ContractCommit> {
  const rel = contractPath(t.taskId);
  const abs = path.join(worktree, rel);
  const text = renderContract(t);
  const hash = sha256(text);
  if (fs.existsSync(abs)) {
    const current = fs.readFileSync(abs, 'utf8');
    if (sha256(current) !== hash) throw new Error(`이미 다른 내용의 계약이 있음: ${rel} (다른 task ID를 쓰거나 기존 계약을 확인)`);
    const dirty = await G.dirtyFiles(worktree);
    if (dirty.includes(rel)) throw new Error(`계약 파일이 커밋되지 않은 상태: ${rel}`);
    const last = (await G.git(worktree, 'log', '-1', '--format=%H', '--', rel)).stdout.trim();
    if (!G.FULL_SHA.test(last)) throw new Error('기존 계약 커밋을 찾지 못함');
    return { contractSha: last, contractHash: hash, reused: true };
  }
  const dirty = await G.dirtyFiles(worktree);
  if (dirty.length) throw new Error(`worktree에 미커밋 변경이 있어 계약을 커밋하지 않음: ${dirty.slice(0, 5).join(', ')}`);
  const email = (await G.git(worktree, 'config', 'user.email')).stdout.trim();
  if (!email) throw new Error('git user.email 미설정 — 계약 커밋 작성자를 정할 수 없음');
  if (context) {
    const { ex, origin, generation } = context;
    assertMainActive(ex, '작업 계약 쓰기', generation);
    if (origin) authorize(ex, origin.sessionId, origin.action, origin.target, origin.sha, origin);
  }
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, text, { flag: 'wx' });
  const add = await G.git(worktree, 'add', '--', rel);
  const commit = add.code === 0 ? await G.git(worktree, 'commit', '-q', '-m', `docs(task): ${t.taskId} 작업 계약`, '--', rel) : add;
  if (commit.code !== 0) {
    fs.rmSync(abs, { force: true });
    await G.git(worktree, 'reset', '-q', '--', rel);
    throw new Error(`계약 커밋 실패: ${commit.stderr.trim()}`);
  }
  const sha = await G.revParse(worktree, 'HEAD');
  return { contractSha: sha!, contractHash: hash, reused: false };
}

export async function contractHashAt(worktree: string, taskId: string, sha: string): Promise<string | null> {
  const r = await G.run('git', ['show', `${sha}:${contractPath(taskId)}`], worktree);
  return r.code === 0 ? sha256(r.stdout) : null;
}

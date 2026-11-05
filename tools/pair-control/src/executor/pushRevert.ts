import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { checkVenv } from './envcheck.ts';
import { checkout } from './pushConfig.ts';
import { lsRemote, networkEnv, redactText } from './pushTransport.ts';
import { UserError } from './executor.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function prepareRevert(ex: Executor, id: string): Promise<RevertInfo> {
  const rec = ex.state.pushes?.[id];
  if (!rec) throw new UserError('푸시 기록 없음');
  if (rec.status !== 'pushed_verified') throw new UserError(`확인된 푸시만 되돌릴 수 있음(${rec.status})`);
  if (rec.kind === 'revert') throw new UserError('되돌림 푸시는 다시 되돌리지 않음 — 필요하면 새 작업으로 처리');
  if (rec.revert) throw new UserError('이미 되돌림을 준비함');
  const cwd = checkout(ex);
  const cur = await G.currentBranch(cwd);
  if (cur !== rec.branch) throw new UserError(`통합 checkout 브랜치가 ${rec.branch}가 아님(${cur ?? 'detached'})`);
  const dirty = (await G.dirtyFiles(cwd)).filter((f) => !f.startsWith('artifacts/'));
  if (dirty.length || (await G.operationInProgress(cwd))) throw new UserError('통합 checkout이 깨끗하지 않음');
  const head = await G.revParse(cwd, 'HEAD');
  if (head !== rec.pushedSha) throw new UserError('로컬이 푸시한 SHA와 다름 — 그 위에 커밋이 있어 자동으로 되돌리지 않음');
  const remote = await lsRemote(cwd, rec.remote, rec.branch, networkEnv());
  if (!remote.ok) throw new UserError(`원격 확인 실패: ${redactText(remote.detail)}`);
  if (remote.sha !== rec.pushedSha) throw new UserError('원격이 푸시한 SHA와 다름 — 이후 푸시가 있어 자동으로 되돌리지 않음');
  const merges = (await G.git(cwd, 'rev-list', '--merges', `${rec.preRemoteHead}..${rec.pushedSha}`)).stdout.trim();
  if (merges) throw new UserError('범위에 병합 커밋이 있어 자동으로 되돌리지 않음');
  const develop = path.join(cwd, 'develop');
  if (!fs.existsSync(develop)) throw new UserError('통합 checkout에 ./develop 없음');
  const env = await checkVenv(cwd, 'python');
  if (!env.ready) throw new UserError(`통합 checkout 실행 환경 미준비: ${env.checks.filter((c) => !c.ok).map((c) => c.detail).join(', ')}`);
  const owner = crypto.randomUUID();
  if (!ex.locks.acquire('integration', { owner, kind: 'revert' })) throw new UserError('다른 통합·푸시가 진행 중');
  try {
    const r = await G.run(develop, ['--', 'git', 'revert', '--no-edit', `${rec.preRemoteHead}..${rec.pushedSha}`], cwd, 120_000, sanitizedChildEnv());
    if (r.code !== 0) {
      if (/사용 중/.test(r.stderr)) throw new UserError(`./develop 잠금 사용 중: ${r.stderr.trim()}`);
      await G.run(develop, ['--', 'git', 'revert', '--abort'], cwd, 60_000, sanitizedChildEnv());
      throw new UserError(`되돌림 충돌 또는 실패 — revert --abort만 수행(자동 해결·reset 없음): ${redactText((r.stderr || r.stdout).trim().slice(-300))}`);
    }
    const newHead = (await G.revParse(cwd, 'HEAD'))!;
    const made = (await G.git(cwd, 'rev-list', '--reverse', `${rec.pushedSha}..${newHead}`)).stdout.trim().split('\n').filter(Boolean);
    const treeRestored = (await G.git(cwd, 'diff', '--quiet', rec.preRemoteHead, newHead)).code === 0;
    rec.revert = { preparedAt: new Date().toISOString(), preHead: rec.pushedSha, newHead, commits: made, treeRestored };
    ex.audit('revert_prepared', { id, newHead, treeRestored });
    ex.store.save();
    return rec.revert;
  } finally { ex.locks.release('integration', 'owner', owner); }
}

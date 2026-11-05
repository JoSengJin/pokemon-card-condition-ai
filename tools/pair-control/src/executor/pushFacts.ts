import * as G from './git.ts';
import { networkEnv, redactUrl, redactText } from './pushTransport.ts';
import { checkout } from './pushConfig.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function collectPushFacts(ex: Executor, plan: PushPlan) {
  const cwd = checkout(ex), { remote, branch, blockers } = plan, env = networkEnv();
  const branchResult = await G.run('git', ['symbolic-ref', '--quiet', '--short', 'HEAD'], cwd);
  const cur = branchResult.code === 0 ? branchResult.stdout.trim() : null;
  if (cur !== branch) blockers.push(`통합 checkout의 브랜치가 ${branch}가 아님(현재 ${cur ?? 'detached'})`);
  const op = await G.operationInProgress(cwd);
  if (op) blockers.push(`통합 checkout에 진행 중인 Git 작업이 있음: ${op}`);
  const dirty = (await G.dirtyFiles(cwd)).filter((f) => !f.startsWith('artifacts/'));
  if (dirty.length) blockers.push(`통합 checkout에 미커밋 변경이 있음: ${dirty.slice(0, 5).join(', ')}`);
  const head = await G.revParse(cwd, `refs/heads/${branch}`);
  if (!head) { blockers.push(`로컬 ${branch} 브랜치를 읽지 못함`); return plan; }
  plan.localHead = head;

  const url = await G.run('git', ['remote', 'get-url', remote], cwd, 60_000, env);
  if (url.code !== 0) { blockers.push(`원격 '${remote}'이(가) 설정되어 있지 않음`); return plan; }
  plan.remoteUrl = redactUrl(url.stdout.trim());

  const f = await G.run('git', ['fetch', '--no-tags', remote, `+refs/heads/${branch}:refs/remotes/${remote}/${branch}`], cwd, 60_000, env);
  if (f.code !== 0) { blockers.push(`원격 fetch 실패: ${redactText(f.stderr.trim().slice(0, 300)) || `code ${f.code}`}`); return plan; }
  const remoteHead = await G.revParse(cwd, `refs/remotes/${remote}/${branch}`);
  if (!remoteHead) { blockers.push('원격에 이 브랜치가 없음 — 첫 푸시는 이 도구가 하지 않음'); return plan; }
  plan.remoteHead = remoteHead;

  if (!(await G.isAncestor(cwd, remoteHead, head))) {
    blockers.push('원격이 앞서 있거나 갈라짐(fast-forward 불가) — 자동 병합·force 없음. 직접 해결 후 다시 점검');
    return plan;
  }
  const log = (await G.git(cwd, 'log', '--reverse', '--format=%H%x09%P%x09%s', `${remoteHead}..${head}`)).stdout.trim().split('\n').filter(Boolean);
  plan.commits = log.map((l) => { const [sha, parents, subject] = l.split('\t'); return { sha, parents, subject }; });
  if (!plan.commits.length) { blockers.push('푸시할 커밋이 없음(로컬과 원격이 같음)'); return plan; }
  plan.files = (await G.changedFiles(cwd, remoteHead, head)).sort();

  return plan;
}

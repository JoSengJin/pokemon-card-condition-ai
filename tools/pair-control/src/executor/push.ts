// 푸시와 되돌림 절차. 푸시는 원격 이력을 바꾸므로 취소할 수 없다. 그래서
//   점검(읽기 전용 + --dry-run) → 대상 SHA 앞 12자 직접 입력 → 일반 push(force 없음, SHA 지정) → 원격 사후 확인 → 기록
// 순서로만 진행하고, 실수는 `git revert` 커밋을 만들어 같은 절차로 다시 올려 바로잡는다(이력 보존, force 없음).
// 자격 증명은 도구가 다루지 않는다(git의 기존 credential helper 사용, 프롬프트 없는 비대화형 실행).
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { isForbidden } from './contract.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { checkVenv } from './envcheck.ts';
import { UserError, type Executor } from './executor.ts';

export interface PushCommit { sha: string; parents: string; subject: string }
/** commit·fingerprint가 있는 항목은 이력(커밋별) 점검 결과다. 비밀 패턴 항목만 사용자가 오탐으로 확인할 수 있다. */
export interface Finding { kind: 'forbidden_path' | 'secret_pattern' | 'large_file'; file: string; line?: number; detail: string; commit?: string; fingerprint?: string; acknowledged?: boolean }
export interface PushPlan {
  id: string; remote: string; remoteUrl: string; branch: string; localHead: string; remoteHead: string | null;
  commits: PushCommit[]; files: string[]; tasks: string[]; findings: Finding[]; blockers: string[]; warnings: string[];
  dryRun: { ok: boolean; detail: string } | null; revertOf: string | null; checkedAt: string;
}
export interface RevertInfo { preparedAt: string; preHead: string; newHead: string; commits: string[]; treeRestored: boolean; pushedAs?: string }
export interface PushRecord {
  id: string; at: string; kind: 'push' | 'revert'; remote: string; remoteUrl: string; branch: string; preRemoteHead: string; pushedSha: string;
  commits: string[]; tasks: string[]; command: string[]; status: 'pushed_verified' | 'push_failed' | 'push_unverified' | 'remote_mismatch';
  detail: string; verifiedAt?: string; revertOf?: string; revert?: RevertInfo | null;
}

const BIG_FILE_BYTES = 5_000_000;
/** 알려진 비밀값 모양. 값은 기록·표시하지 않고 파일과 줄 번호만 보인다. 이 목록은 모든 비밀을 잡지 못한다. */
export const SECRET_LINE_PATTERNS: [string, RegExp][] = [
  ['API 키(sk-…)', /sk-[A-Za-z0-9_-]{20,}/], ['GitHub 토큰', /gh[pousr]_[A-Za-z0-9]{30,}/], ['AWS 액세스 키', /AKIA[0-9A-Z]{16}/],
  ['개인 키', /-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/], ['Slack 토큰', /xox[abprs]-[A-Za-z0-9-]{10,}/], ['Google API 키', /AIza[0-9A-Za-z_-]{35}/],
];
const extraForbidden = (f: string) => /(^|\/)\.env(\.|$)/.test(f) || /\.(pem|key|p12|sqlite3?|db|pt)$/.test(f)
  || /(^|\/)(development-review|nemotron-review|trusted-experiment)\.json$/.test(f);

export const redactUrl = (u: string) => u.replace(/\/\/[^@/\s]+@/, '//***@');
const redactText = (s: string) => redactUrl(s).replace(/(sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._-]{16,})/g, '[REDACTED]');

/** 프롬프트 없이 실패하게 하는 git 네트워크용 환경. 자격 증명은 git이 기존 helper로 처리한다. */
function netEnv(): NodeJS.ProcessEnv {
  const env = sanitizedChildEnv();
  env.GIT_TERMINAL_PROMPT = '0';
  if (process.env.SSH_AUTH_SOCK) env.SSH_AUTH_SOCK = process.env.SSH_AUTH_SOCK;
  return env;
}
const git = (cwd: string, args: string[], timeout = 60_000) => G.run('git', args, cwd, timeout, netEnv());

async function lsRemote(cwd: string, remote: string, branch: string): Promise<{ ok: boolean; sha: string | null; detail: string }> {
  const r = await git(cwd, ['ls-remote', remote, `refs/heads/${branch}`]);
  if (r.code !== 0) return { ok: false, sha: null, detail: redactText(r.stderr.trim().slice(0, 300)) };
  const m = r.stdout.trim().split(/\s+/)[0];
  return { ok: true, sha: G.FULL_SHA.test(m ?? '') ? m : null, detail: '' };
}

function checkout(ex: Executor) {
  const c = ex.cfg.integration.checkout;
  if (!c) throw new UserError('config.integration.checkout 미설정');
  return c;
}
const remoteName = (ex: Executor) => ex.cfg.integration.remote || 'origin';

export function pushState(ex: Executor) {
  const records = Object.values(ex.state.pushes ?? {}).sort((a, b) => b.at.localeCompare(a.at));
  return { remote: remoteName(ex), branch: ex.cfg.integration.branch, plan: ex.state.pushPlan ?? null, records };
}

/** 점검: 푸시하지 않고 가능 여부·대상 커밋·위험 항목을 계산한다(fetch와 `push --dry-run`은 원격에 읽기 접속만 한다). */
export async function preflight(ex: Executor): Promise<PushPlan> {
  const cwd = checkout(ex);
  const remote = remoteName(ex), branch = ex.cfg.integration.branch;
  const blockers: string[] = [], warnings: string[] = [];
  const plan: PushPlan = { id: crypto.randomUUID(), remote, remoteUrl: '', branch, localHead: '', remoteHead: null, commits: [], files: [], tasks: [], findings: [], blockers, warnings, dryRun: null, revertOf: null, checkedAt: new Date().toISOString() };
  const done = () => { ex.state.pushPlan = plan; ex.store.save(); return plan; };

  const cur = await G.currentBranch(cwd);
  if (cur !== branch) blockers.push(`통합 checkout의 브랜치가 ${branch}가 아님(현재 ${cur ?? 'detached'})`);
  const op = await G.operationInProgress(cwd);
  if (op) blockers.push(`통합 checkout에 진행 중인 Git 작업이 있음: ${op}`);
  const dirty = (await G.dirtyFiles(cwd)).filter((f) => !f.startsWith('artifacts/'));
  if (dirty.length) blockers.push(`통합 checkout에 미커밋 변경이 있음: ${dirty.slice(0, 5).join(', ')}`);
  const head = await G.revParse(cwd, `refs/heads/${branch}`);
  if (!head) { blockers.push(`로컬 ${branch} 브랜치를 읽지 못함`); return done(); }
  plan.localHead = head;

  const url = await git(cwd, ['remote', 'get-url', remote]);
  if (url.code !== 0) { blockers.push(`원격 '${remote}'이(가) 설정되어 있지 않음`); return done(); }
  plan.remoteUrl = redactUrl(url.stdout.trim());

  const f = await git(cwd, ['fetch', '--no-tags', remote, `+refs/heads/${branch}:refs/remotes/${remote}/${branch}`]);
  if (f.code !== 0) { blockers.push(`원격 fetch 실패: ${redactText(f.stderr.trim().slice(0, 300)) || `code ${f.code}`}`); return done(); }
  const remoteHead = await G.revParse(cwd, `refs/remotes/${remote}/${branch}`);
  if (!remoteHead) { blockers.push('원격에 이 브랜치가 없음 — 첫 푸시는 이 도구가 하지 않음'); return done(); }
  plan.remoteHead = remoteHead;

  if (!(await G.isAncestor(cwd, remoteHead, head))) {
    blockers.push('원격이 앞서 있거나 갈라짐(fast-forward 불가) — 자동 병합·force 없음. 직접 해결 후 다시 점검');
    return done();
  }
  const log = (await G.git(cwd, 'log', '--reverse', '--format=%H%x09%P%x09%s', `${remoteHead}..${head}`)).stdout.trim().split('\n').filter(Boolean);
  plan.commits = log.map((l) => { const [sha, parents, subject] = l.split('\t'); return { sha, parents, subject }; });
  if (!plan.commits.length) { blockers.push('푸시할 커밋이 없음(로컬과 원격이 같음)'); return done(); }
  plan.files = (await G.changedFiles(cwd, remoteHead, head)).sort();

  // 이 범위에 들어 있는 작업과 통합 후 검사 결과
  for (const t of Object.values(ex.state.tasks)) {
    const nh = t.integration?.newHead;
    if (!nh || !(await G.isAncestor(cwd, nh, head)) || (await G.isAncestor(cwd, nh, remoteHead))) continue;
    plan.tasks.push(t.taskId);
    if (t.status === 'integrated_check_failed') blockers.push(`작업 ${t.taskId}: 통합 후 검사 실패 상태 — 확인·복구 전에는 푸시하지 않음`);
    else if (t.integration?.postStatus === 'not_run') warnings.push(`작업 ${t.taskId}: 통합 후 검사가 지정되지 않아 미실행`);
  }
  for (const [id, rec] of Object.entries(ex.state.pushes ?? {})) {
    if (rec.revert && rec.revert.newHead === head && !rec.revert.pushedAs) plan.revertOf = id;
  }

  // 금지 경로·큰 파일·비밀 패턴: 커밋마다 본다. 중간 커밋에 들어갔다가 지워진 값도 이력에는 남아 원격에 올라가기 때문이다.
  if (plan.commits.length > 500) { blockers.push(`푸시할 커밋이 ${plan.commits.length}개로 너무 많아 이력 점검을 하지 않음 — 나눠서 푸시`); return done(); }
  const range = `${remoteHead}..${head}`;
  const names = (await G.git(cwd, 'log', '--reverse', '--diff-filter=AM', '--name-only', '--no-color', '--format=@@COMMIT %H', range)).stdout;
  let commit = '';
  const seen = new Set<string>();
  for (const line of names.split('\n')) {
    if (line.startsWith('@@COMMIT ')) { commit = line.slice(9); continue; }
    if (!line || !commit || seen.has(`${commit}\0${line}`)) continue;
    seen.add(`${commit}\0${line}`);
    if (isForbidden(line) || extraForbidden(line)) plan.findings.push({ kind: 'forbidden_path', file: line, commit, detail: '데이터·산출물·비밀 설정 경로는 푸시하지 않음' });
    const sz = await G.git(cwd, 'cat-file', '-s', `${commit}:${line}`);
    if (sz.code === 0 && Number(sz.stdout) > BIG_FILE_BYTES) plan.findings.push({ kind: 'large_file', file: line, commit, detail: `${(Number(sz.stdout) / 1e6).toFixed(1)}MB(5MB 초과)` });
  }
  const patches = await G.git(cwd, 'log', '--reverse', '-p', '-U0', '--no-color', '--diff-filter=AM', '--format=@@COMMIT %H', range);
  let file = '', ln = 0; commit = '';
  for (const line of patches.stdout.split('\n')) {
    if (line.startsWith('@@COMMIT ')) { commit = line.slice(9); continue; }
    if (line.startsWith('+++ b/')) { file = line.slice(6); continue; }
    const h = /^@@ -\S+ \+(\d+)/.exec(line);
    if (h) { ln = Number(h[1]); continue; }
    if (line.startsWith('+') && !line.startsWith('+++')) {
      for (const [name, re] of SECRET_LINE_PATTERNS) {
        if (!re.test(line)) continue;
        const fingerprint = crypto.createHash('sha256').update(`${commit}\0${file}\0${ln}\0${name}`).digest('hex').slice(0, 16);
        plan.findings.push({ kind: 'secret_pattern', file, line: ln, commit, fingerprint, detail: `${name} 모양(값은 표시하지 않음)` });
      }
      ln++;
    }
  }
  for (const fd of plan.findings) {
    if (fd.kind === 'secret_pattern' && fd.fingerprint && ex.state.pushAllow?.[fd.fingerprint]) {
      fd.acknowledged = true;
      warnings.push(`확인된 오탐: ${fd.file}:${fd.line} (커밋 ${fd.commit?.slice(0, 8)}) — 사용자가 ${ex.state.pushAllow[fd.fingerprint].at}에 확인`);
      continue;
    }
    blockers.push(`${fd.kind === 'secret_pattern' ? '비밀값 의심' : fd.kind === 'large_file' ? '큰 파일' : '금지 경로'}: ${fd.file}${fd.line ? `:${fd.line}` : ''}${fd.commit ? ` (커밋 ${fd.commit.slice(0, 8)})` : ''} — ${fd.detail}`);
  }
  if (blockers.length) return done();

  // 전송 없이 거절·인증 여부만 확인(원격에 읽기 접속)
  const dry = await git(cwd, ['push', '--dry-run', '--porcelain', remote, `${head}:refs/heads/${branch}`], 90_000);
  plan.dryRun = { ok: dry.code === 0, detail: redactText((dry.stderr || dry.stdout).trim().slice(0, 300)) };
  if (dry.code !== 0) blockers.push(`push --dry-run 실패: ${plan.dryRun.detail || `code ${dry.code}`}`);
  return done();
}

/** 푸시. 방금 다시 점검해 막힘이 없고, 사용자가 입력한 값이 대상 SHA의 앞 12자 이상과 일치할 때만 실행한다. verify가 있으면 push 직전에 같은 계획으로 호출되고, 던지면 push하지 않는다. */
export async function runPush(ex: Executor, confirm: string, verify?: (plan: PushPlan) => Promise<void>): Promise<PushRecord> {
  const cwd = checkout(ex);
  const typed = String(confirm ?? '').trim().toLowerCase();
  const plan = await preflight(ex);
  if (plan.blockers.length) throw new UserError(`푸시할 수 없음: ${plan.blockers.join(' / ')}`);
  if (typed.length < 12 || !plan.localHead.startsWith(typed)) throw new UserError(`확인 입력이 대상 SHA(${plan.localHead.slice(0, 12)}…)의 앞 12자와 다름 — 점검 이후 로컬이 바뀌었을 수 있음`);
  const owner = crypto.randomUUID();
  if (!ex.locks.acquire('integration', { owner, kind: 'push' })) throw new UserError(`다른 통합·푸시가 진행 중: ${JSON.stringify(ex.locks.holder('integration'))}`);
  try {
    const now = await lsRemote(cwd, plan.remote, plan.branch);
    if (!now.ok) throw new UserError(`원격 확인 실패: ${now.detail}`);
    if (now.sha !== plan.remoteHead) throw new UserError('점검 이후 원격이 바뀜 — 다시 점검');
    await verify?.(plan); // 자동 push의 승인 범위 재검사: 실제로 올릴 이 계획에 대해, 기록을 남기고 push하기 직전에 한다
    const command = ['git', 'push', '--porcelain', plan.remote, `${plan.localHead}:refs/heads/${plan.branch}`];
    const rec: PushRecord = {
      id: crypto.randomUUID(), at: new Date().toISOString(), kind: plan.revertOf ? 'revert' : 'push', remote: plan.remote, remoteUrl: plan.remoteUrl, branch: plan.branch,
      preRemoteHead: plan.remoteHead!, pushedSha: plan.localHead, commits: plan.commits.map((c) => c.sha), tasks: plan.tasks, command, status: 'push_unverified', detail: '푸시 실행 중',
      revertOf: plan.revertOf ?? undefined,
    };
    (ex.state.pushes ??= {})[rec.id] = rec;
    ex.state.pushPlan = null;
    ex.audit('push_started', { id: rec.id, sha: rec.pushedSha, kind: rec.kind });
    ex.store.save();
    const r = await G.run('git', command.slice(1), cwd, 120_000, netEnv());
    const out = redactText((r.stdout + (r.stderr ? `\n${r.stderr}` : '')).trim().slice(-600));
    if (r.code !== 0) {
      // 실패해도 원격 상태를 한 번 확인해 기록한다(성공했는데 응답만 실패한 경우 대비). 자동 재시도는 없다.
      const after = await lsRemote(cwd, plan.remote, plan.branch);
      rec.status = after.ok && after.sha === rec.pushedSha ? 'push_unverified' : 'push_failed';
      rec.detail = rec.status === 'push_failed' ? `push 실패(code ${r.code}): ${out}` : `push가 오류를 냈지만 원격이 대상 SHA와 같음 — 결과를 직접 확인하세요: ${out}`;
    } else {
      const after = await lsRemote(cwd, plan.remote, plan.branch);
      if (after.ok && after.sha === rec.pushedSha) { rec.status = 'pushed_verified'; rec.verifiedAt = new Date().toISOString(); rec.detail = '푸시 후 원격 SHA가 대상 SHA와 일치'; }
      else if (after.ok) { rec.status = 'remote_mismatch'; rec.detail = `푸시는 성공했지만 원격 SHA(${after.sha?.slice(0, 12) ?? '없음'})가 대상과 다름 — 다른 푸시가 있었는지 확인`; }
      else { rec.status = 'push_unverified'; rec.detail = `푸시는 성공했지만 사후 확인 실패: ${after.detail}`; }
    }
    if (rec.revertOf && rec.status === 'pushed_verified') { const o = ex.state.pushes![rec.revertOf]; if (o?.revert) o.revert.pushedAs = rec.id; }
    ex.audit('push_finished', { id: rec.id, status: rec.status });
    ex.store.save();
    return rec;
  } finally { ex.locks.release('integration', 'owner', owner); }
}

/** 결과 불명·불일치였던 푸시의 원격 상태를 다시 확인한다(읽기 전용). */
export async function verifyPush(ex: Executor, id: string): Promise<PushRecord> {
  const rec = ex.state.pushes?.[id];
  if (!rec) throw new UserError('푸시 기록 없음');
  const now = await lsRemote(checkout(ex), rec.remote, rec.branch);
  if (!now.ok) throw new UserError(`원격 확인 실패: ${now.detail}`);
  const reachable = now.sha && (now.sha === rec.pushedSha || (await G.isAncestor(checkout(ex), rec.pushedSha, now.sha)));
  if (now.sha === rec.pushedSha) { rec.status = 'pushed_verified'; rec.detail = '원격 SHA가 대상 SHA와 일치'; }
  else if (reachable) { rec.status = 'pushed_verified'; rec.detail = '대상 SHA가 원격 이력에 포함됨(이후 다른 커밋이 추가됨)'; }
  else { rec.status = 'push_failed'; rec.detail = '원격에 대상 SHA가 없음'; }
  rec.verifiedAt = new Date().toISOString();
  ex.audit('push_verified', { id, status: rec.status });
  ex.store.save();
  return rec;
}

/**
 * 되돌림 준비: 푸시한 커밋 범위를 `git revert`로 되돌리는 커밋을 통합 checkout에 만든다(로컬만, ./develop 잠금 안).
 * 로컬·원격이 모두 푸시한 SHA 그대로일 때만 한다. 충돌하면 `git revert --abort`만 하고 자동 해결하지 않는다.
 * 만든 뒤에는 일반 푸시 절차(점검 → 확인 → 푸시 → 사후 확인)로 올린다.
 */
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
  const remote = await lsRemote(cwd, rec.remote, rec.branch);
  if (!remote.ok) throw new UserError(`원격 확인 실패: ${remote.detail}`);
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

/**
 * 비밀 패턴 점검의 오탐(예: 테스트용 가짜 키)을 사용자가 항목별로 확인한다. 커밋·파일·줄이 같은 항목에만 적용되고
 * 다른 위치의 새 항목은 계속 막힌다. 금지 경로·큰 파일은 확인으로 넘길 수 없다.
 */
export function acknowledgeFindings(ex: Executor, fingerprints: string[]) {
  const plan = ex.state.pushPlan;
  if (!plan) throw new UserError('먼저 푸시 점검을 실행하세요');
  const targets = plan.findings.filter((f) => f.kind === 'secret_pattern' && f.fingerprint && fingerprints.includes(f.fingerprint));
  if (!targets.length) throw new UserError('확인할 수 있는 비밀 패턴 항목이 없음');
  const allow = (ex.state.pushAllow ??= {});
  for (const f of targets) allow[f.fingerprint!] = { at: new Date().toISOString(), file: f.file, line: f.line ?? 0, commit: f.commit ?? '' };
  ex.audit('push_findings_acknowledged', { count: targets.length, fingerprints: targets.map((f) => f.fingerprint) });
  ex.store.save();
  return targets.length;
}

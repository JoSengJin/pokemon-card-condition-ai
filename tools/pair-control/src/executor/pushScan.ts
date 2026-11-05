import crypto from 'node:crypto';
import * as G from './git.ts';
import { isForbidden } from './contract.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export const BIG_FILE_BYTES = 5_000_000;
export const SECRET_LINE_PATTERNS: [string, RegExp][] = [
  ['API 키(sk-…)', /sk-[A-Za-z0-9_-]{20,}/], ['GitHub 토큰', /gh[pousr]_[A-Za-z0-9]{30,}/], ['AWS 액세스 키', /AKIA[0-9A-Z]{16}/],
  ['개인 키', /-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----/], ['Slack 토큰', /xox[abprs]-[A-Za-z0-9-]{10,}/], ['Google API 키', /AIza[0-9A-Za-z_-]{35}/],
];
export const extraForbidden = (f: string) => /(^|\/)\.env(\.|$)/.test(f) || /\.(pem|key|p12|sqlite3?|db|pt)$/.test(f)
  || /(^|\/)(development-review|nemotron-review|trusted-experiment)\.json$/.test(f);

export async function scanPushHistory(ex: Executor, plan: PushPlan) {
  const cwd = ex.cfg.integration.checkout, blockers = plan.blockers;
  // 금지 경로·큰 파일·비밀 패턴: 커밋마다 본다. 중간 커밋에 들어갔다가 지워진 값도 이력에는 남아 원격에 올라가기 때문이다.
  if (plan.commits.length > 500) { blockers.push(`푸시할 커밋이 ${plan.commits.length}개로 너무 많아 이력 점검을 하지 않음 — 나눠서 푸시`); return plan; }
  const range = `${plan.remoteHead}..${plan.localHead}`;
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
  return plan;
}

import * as G from './git.ts';
import { checkout, remoteName } from './pushConfig.ts';
import { lsRemote } from './pushTransport.ts';
import { UserError } from './executor.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export function pushState(ex: Executor) {
  const records = Object.values(ex.state.pushes ?? {}).sort((a, b) => b.at.localeCompare(a.at));
  return { remote: remoteName(ex), branch: ex.cfg.integration.branch, plan: ex.state.pushPlan ?? null, records };
}

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

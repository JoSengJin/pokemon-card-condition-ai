import * as G from './git.ts';
import { git, redactText } from './pushTransport.ts';
import { checkout } from './pushConfig.ts';
import type { PushPlan, PushRecord, RevertInfo } from './pushTypes.ts';
import type { Executor } from './executor.ts';

export async function associatePushTasks(ex: Executor, plan: PushPlan) {
  const cwd = checkout(ex), { blockers, warnings } = plan;
  // 이 범위에 들어 있는 작업과 통합 후 검사 결과
  for (const t of Object.values(ex.state.tasks)) {
    const nh = t.integration?.newHead;
    if (!nh || !(await G.isAncestor(cwd, nh, plan.localHead)) || (await G.isAncestor(cwd, nh, plan.remoteHead!))) continue;
    plan.tasks.push(t.taskId);
    if (t.status === 'integrated_check_failed') blockers.push(`작업 ${t.taskId}: 통합 후 검사 실패 상태 — 확인·복구 전에는 푸시하지 않음`);
    else if (t.integration?.postStatus === 'not_run') warnings.push(`작업 ${t.taskId}: 통합 후 검사가 지정되지 않아 미실행`);
  }
  for (const [id, rec] of Object.entries(ex.state.pushes ?? {})) {
    if (rec.revert && rec.revert.newHead === plan.localHead && !rec.revert.pushedAs) plan.revertOf = id;
  }

  return plan;
}

export function judgePushFindings(ex: Executor, plan: PushPlan) {
  const { blockers, warnings } = plan;
  for (const fd of plan.findings) {
    if (fd.kind === 'secret_pattern' && fd.fingerprint && ex.state.pushAllow?.[fd.fingerprint]) {
      fd.acknowledged = true;
      warnings.push(`확인된 오탐: ${fd.file}:${fd.line} (커밋 ${fd.commit?.slice(0, 8)}) — 사용자가 ${ex.state.pushAllow[fd.fingerprint].at}에 확인`);
      continue;
    }
    blockers.push(`${fd.kind === 'secret_pattern' ? '비밀값 의심' : fd.kind === 'large_file' ? '큰 파일' : '금지 경로'}: ${fd.file}${fd.line ? `:${fd.line}` : ''}${fd.commit ? ` (커밋 ${fd.commit.slice(0, 8)})` : ''} — ${fd.detail}`);
  }
  return plan;

}

export async function dryRunPush(ex: Executor, plan: PushPlan) {
  const cwd = checkout(ex), blockers = plan.blockers;
  // 전송 없이 거절·인증 여부만 확인(원격에 읽기 접속)
  const dry = await git(cwd, ['push', '--dry-run', '--porcelain', plan.remote, `${plan.localHead}:refs/heads/${plan.branch}`], 90_000);
  plan.dryRun = { ok: dry.code === 0, detail: redactText((dry.stderr || dry.stdout).trim().slice(0, 300)) };
  if (dry.code !== 0) blockers.push(`push --dry-run 실패: ${plan.dryRun.detail || `code ${dry.code}`}`);
  return plan;
}

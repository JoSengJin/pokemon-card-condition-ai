import { getTask } from './executorLookup.ts';
import { limitFor, assertMainActive } from './executorPolicy.ts';
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import { probe, realReadiness } from './adapters.ts';
import { scanArgs } from './nocharge.ts';
import { sanitizedChildEnv } from './freeGuard.ts';
import { writeJsonAtomic } from './store.ts';
import { spawnSupervised } from './processSupervisor.ts';
import { worktreeFingerprint } from './reviewFingerprint.ts';
import { UserError } from './errors.ts';
import { REVIEW_MOCK_SCENARIOS, type Executor } from './executor.ts';

export async function startReviewJob(taskExecutor: Executor, taskId: string, o: { reviewer?: 'codex' | 'claude'; mode?: 'mock' | 'real'; mockScenario?: (typeof REVIEW_MOCK_SCENARIOS)[number]; forHandoff?: boolean } = {}) {
  assertMainActive(taskExecutor, '리뷰 시작');
  const t = getTask(taskExecutor, taskId);
  if (taskExecutor.guardAlert) throw new UserError('과금 신호 감지 상태 — 실행하지 않음');
  if (t.status !== 'review_pending') throw new UserError(`검토 대기 상태에서만 리뷰를 등록(${t.status})`);
  const sha = t.result?.headSha;
  const head = await G.revParse(t.worktree, `refs/heads/${t.branch}`);
  if (!sha || head !== sha) throw new UserError('Git 계약 검사 이후 코드 SHA가 바뀜 — 결과 재수집 필요');
  const reviewer = o.reviewer ?? (t.agent === 'claude' ? 'codex' : 'claude');
  if (reviewer === t.agent) throw new UserError('구현 담당과 다른 에이전트가 리뷰해야 함');
  const mode = o.mode ?? 'mock';
  if (mode === 'mock' && o.mockScenario && !REVIEW_MOCK_SCENARIOS.includes(o.mockScenario)) throw new UserError(`알 수 없는 fake 리뷰 시나리오: ${o.mockScenario}`);
  if (t.review?.status === 'running') throw new UserError('리뷰가 이미 실행 중');
  const reviewId = crypto.randomUUID();
  if (!taskExecutor.locks.acquire(`review:${taskId}`, { execId: reviewId, taskId, lifetime: taskExecutor.lifetime })) throw new UserError('리뷰 잠금 사용 중');
  try {
    const bundleDir = path.join(taskExecutor.cfg.stateDir, 'reviews', reviewId);
    fs.mkdirSync(bundleDir, { recursive: true });
    const contract = (await G.git(t.worktree, 'show', `${sha}:${t.contractPath}`)).stdout;
    fs.writeFileSync(path.join(bundleDir, 'contract.md'), contract);
    fs.writeFileSync(path.join(bundleDir, 'diff.patch'), await G.diffText(t.worktree, t.baseSha, sha, 2_000_000));
    writeJsonAtomic(path.join(bundleDir, 'checks.json'), {
      git_contract_checks: t.result!.checks,
      task_tests: t.verification && t.verification.sha === sha ? { status: t.verification.status, items: t.verification.items.map(({ logPath, ...i }) => ({ ...i, log: logPath && fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8').slice(-4000) : '' })) } : { status: 'not_run' },
    });
    writeJsonAtomic(path.join(bundleDir, 'meta.json'), { taskId, sha, baseSha: t.baseSha, contractSha: t.contractSha, contractHash: t.contractHash, implementer: t.agent, reviewer });
    fs.writeFileSync(path.join(bundleDir, 'REVIEW_REQUEST.md'), `# 리뷰 요청: ${taskId}

이 폴더만 읽는 별도 리뷰 작업이다. 구현 브랜치·worktree를 수정하지 않는다.
- contract.md: 작업 계약(목표·완료 조건·허용 파일·검사)
- diff.patch: 기준 ${t.baseSha} → 검토 대상 ${sha}
- checks.json: Git 계약 검사와 작업 테스트 결과(미실행은 통과가 아님)

판정을 아래 JSON 한 개로 review-result.json에 쓰거나 마지막 줄에 출력한다.
{"verdict": "approve | changes_requested | insufficient_evidence", "sha": "${sha}", "summary": "근거"}

판정은 사람 승인을 대신하지 않는다.
`);
    let command: string, args: string[], display: string[];
    if (mode === 'mock') {
      const script = path.join(taskExecutor.cfg.toolRoot, 'mock', 'fake-reviewer.mjs');
      command = process.execPath; args = [script, '--scenario', o.mockScenario ?? 'approve', '--bundle', bundleDir];
      display = ['node', 'mock/fake-reviewer.mjs', '--scenario', o.mockScenario ?? 'approve', '--bundle', '<리뷰 묶음>'];
    } else {
      taskExecutor.probes[reviewer] = await probe(reviewer, taskExecutor.cfg);
      const rr = realReadiness(reviewer, taskExecutor.probes[reviewer], taskExecutor.cfg, { limit: limitFor(taskExecutor, reviewer) });
      if (!rr.available) throw new UserError(`실제 ${reviewer} 리뷰 차단: ${rr.blockers.map((b) => b.message).join(', ')}`);
      const prompt = 'REVIEW_REQUEST.md를 읽고 판정 JSON을 마지막 줄에 출력하세요. 파일을 수정하지 마세요.';
      // 옵션 이름은 --help로 확인하지만 값(read-only, plan)은 실제 CLI에서 별도 확인 필요.
      args = reviewer === 'codex' ? ['exec', '--cd', bundleDir, '--sandbox', 'read-only', prompt] : ['--print', '--permission-mode', 'plan', prompt];
      const argRisks = scanArgs(args);
      if (argRisks.length) throw new UserError(`무과금 가드: ${argRisks.map((r) => r.message).join('; ')}`);
      command = taskExecutor.probes[reviewer]!.binary!; display = [reviewer, ...args.slice(0, -1).map((a) => (a === bundleDir ? '<리뷰 묶음>' : a)), '<prompt>'];
    }
    t.review = { reviewId, reviewer, mode, sha, contractHash: t.contractHash, bundleDir, worktreeFingerprint: await worktreeFingerprint(t), status: 'running', startedAt: new Date().toISOString(), ...(o.forHandoff ? { forHandoff: true } : {}) };
    const ex = spawnSupervised(taskExecutor, t, { kind: 'review', runId: reviewId, cwd: bundleDir, command, args, env: sanitizedChildEnv(), display, sha });
    t.review.execId = ex.execId;
    taskExecutor.audit('review_started', { taskId, reviewId, reviewer, mode, sha });
    taskExecutor.store.save();
    return t.review;
  } catch (err) {
    taskExecutor.locks.release(`review:${taskId}`, 'execId', reviewId);
    if (t.review?.reviewId === reviewId) t.review = null;
    throw err instanceof UserError ? err : new UserError((err as Error).message);
  }
}

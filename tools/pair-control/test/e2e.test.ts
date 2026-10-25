// 실제 사용자 흐름 회귀(합성 저장소 + mock 에이전트 + fake 리뷰 CLI). 모델 요청 없음.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { prepareTask, resumeStep, runInfo, startTask } from '../src/runtime.ts';
import { fakeSecret, setup, verify, waitFor } from './helpers.ts';

const gitOut = (cwd: string, ...a: string[]) => execFileSync('git', a, { cwd }).toString().trim();

test('준비 → 계약 커밋 → 실행 → Git 검사 → 작업 테스트 → 리뷰 → 승인 → 통합 → 통합 후 검사, 원본·다른 작업·비밀값 보존', async () => {
  const env = setup();
  const savedKey = process.env.OPENAI_API_KEY;
  const leakKey = fakeSecret('leak');
  const tokenText = fakeSecret('tok');
  process.env.OPENAI_API_KEY = leakKey;
  try {
    const repo = env.fixture.repo;
    const other = env.fixture.worktrees['task-c'].path;
    fs.writeFileSync(path.join(other, 'src_c', 'user-wip.txt'), '다른 작업의 미커밋 파일');
    const otherHead = gitOut(other, 'rev-parse', 'HEAD');
    const mainBefore = gitOut(repo, 'rev-parse', 'main');

    // 1) 준비: 사람은 담당·목표·파일·완료 조건·검사만 고름
    const prep = await prepareTask({
      agent: 'claude', goal: 'src_b 정리', allowedFiles: ['src_b/'], doneCriteria: ['src_b에 결과 파일 추가'],
      checks: [
        { id: 'ws', name: '공백 오류', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'] },
        { id: 'env', name: '비밀값 미전달', executable: 'node', args: ['-e', `console.log(process.env.OPENAI_API_KEY ?? "no-key"); console.log("token ${tokenText}")`] },
      ],
      postChecks: [{ id: 'post', name: '통합 후 파일 확인', executable: 'git', args: ['ls-files', '--error-unmatch', 'src_b/file.txt'] }],
    });
    const id = prep.taskId!;
    let t = env.ex.task(id);
    assert.equal(t.status, 'assigned');
    assert.equal(gitOut(t.worktree, 'log', '-1', '--format=%s'), `docs(task): ${id} 작업 계약`);
    assert.equal(gitOut(repo, 'rev-parse', 'main'), mainBefore, '준비 단계에서 main 불변');
    assert.equal(t.envReadiness?.ready, true);

    // 2) 실행 → Git 계약 검사
    await startTask(id);
    await waitFor(() => env.ex.task(id).status === 'review_pending', 'review');
    t = env.ex.task(id);
    assert.ok(t.result!.checksPassed, JSON.stringify(t.result!.checks));

    // 3) 작업 테스트(비밀값 미전달·로그 가림)
    const v = await verify(env, id);
    assert.equal(v.status, 'passed', JSON.stringify(v.items));
    const log = fs.readFileSync(v.items[1].logPath!, 'utf8');
    assert.match(log, /no-key/);
    assert.ok(!log.includes(tokenText) && !log.includes(leakKey));
    assert.match(log, /\[REDACTED\]/);

    // 4) 별도 리뷰(fake) — 판정은 기록만
    await env.ex.startReviewJob(id, { mockScenario: 'approve' });
    const rv = await waitFor(() => { const r = env.ex.task(id).review; return r && r.status !== 'running' ? r : null; }, 'review job');
    assert.equal(rv.reviewer, 'codex'); assert.equal(rv.verdict, 'approve');
    assert.equal(env.ex.task(id).status, 'review_pending', '리뷰가 승인을 대신하지 않음');

    // 5) 사람 승인 → 통합 → 통합 후 검사
    const a = await env.ex.approve(id, t.result!.headSha!);
    assert.equal(a.reviewVerdict, 'approve');
    await resumeStep(t.runId!, 'review-gate', { decision: 'approve', sha: a.sha });
    assert.equal((await runInfo(t.runId))?.suspendedStep, 'integrate-gate');
    await resumeStep(t.runId!, 'integrate-gate', { action: 'integrate' });
    t = env.ex.task(id);
    assert.equal(t.status, 'integrated', t.statusReason ?? '');
    assert.equal(t.integration!.postStatus, 'passed');
    assert.equal(t.integration!.preHead, mainBefore);
    assert.equal(gitOut(repo, 'rev-list', '--count', `${mainBefore}..main`), '2', '계약 커밋 + 변경 커밋');
    assert.ok(gitOut(repo, 'show', '--name-only', '--format=', 'main~1').includes(`docs/collaboration/tasks/${id}.md`));
    assert.equal(gitOut(repo, 'status', '--porcelain'), '');

    // 보존: 다른 작업 worktree, 미커밋 파일
    assert.equal(gitOut(other, 'rev-parse', 'HEAD'), otherHead);
    assert.equal(fs.readFileSync(path.join(other, 'src_c', 'user-wip.txt'), 'utf8'), '다른 작업의 미커밋 파일');
    // 상태 파일에 비밀값 없음
    const stateText = fs.readFileSync(path.join(env.cfg.stateDir, 'state.json'), 'utf8');
    assert.ok(!stateText.includes(leakKey));
  } finally {
    if (savedKey === undefined) delete process.env.OPENAI_API_KEY; else process.env.OPENAI_API_KEY = savedKey;
    env.cleanup();
  }
});

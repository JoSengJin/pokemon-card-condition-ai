import { getTask } from '../src/executor/executorLookup.ts';
// 진행률 항목 기반 계약 초안(원문 인용, 판단은 사람) — 합성 development-progress.json만 사용한다.
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { test } from 'node:test';
import { progressDraft, progressItems } from '../src/executor/progress.ts';
import { prepareTask } from '../src/runtime.ts';
import { setup, type Env } from './helpers.ts';

const git = (cwd: string, ...a: string[]) => execFileSync('git', ['-c', 'user.name=t', '-c', 'user.email=t@l', ...a], { cwd }).toString().trim();
const PROGRESS = {
  criterion_version: 'usable-test-v1', score: 30, max_score: 100,
  categories: [{ id: 'C', title: '범위별 성능', weight: 14, milestones: [
    { id: 'C1', title: '엣지', weight: 7, status: 'pending', earned: 0, completion_criterion: 'FN/(TP+FN)<=5%\n양성 각 20판정단위', evidence: ['card_condition/listing_readiness.py', 'artifacts/x/REPORT.md', 'missing/file.py', '../escape.py'], assessment: '통과한 근거가 없다.' },
    { id: 'C9', title: '완료된 항목', weight: 3, status: 'verified', earned: 3, completion_criterion: '완료', evidence: [], assessment: '확인됨' },
  ] }],
};
function commitProgress(env: Env, data: unknown = PROGRESS) {
  const cwd = env.fixture.repo;
  fs.writeFileSync(path.join(cwd, 'development-progress.json'), JSON.stringify(data, null, 2));
  fs.writeFileSync(path.join(cwd, 'card_condition', 'listing_readiness.py'), '# synthetic\n');
  git(cwd, 'add', '-A'); git(cwd, 'commit', '-qm', 'add progress');
  return git(cwd, 'rev-parse', 'HEAD');
}

test('미완료 항목만 나열하고 통합 브랜치에 커밋된 파일에서 읽음(미커밋 편집 무시)', async () => {
  const env = setup();
  try {
    await assert.rejects(progressItems(env.ex), /통합 브랜치에 없음/);
    const sha = commitProgress(env);
    const r = await progressItems(env.ex);
    assert.equal(r.source.sha, sha);
    assert.equal(r.source.criterionVersion, 'usable-test-v1');
    assert.deepEqual(r.items.map((i) => i.id), ['C1']);
    assert.equal(r.items[0].category, '범위별 성능');
    fs.writeFileSync(path.join(env.fixture.repo, 'development-progress.json'), JSON.stringify({ categories: [] }));
    assert.deepEqual((await progressItems(env.ex)).items.map((i) => i.id), ['C1'], '작업 디렉터리의 미커밋 변경은 읽지 않음');
    git(env.fixture.repo, 'checkout', '-q', '--', 'development-progress.json');
  } finally { env.cleanup(); }
});

test('초안: 원문 인용·출처 SHA·범위 제한, 증거 파일은 실제 있는 코드만 제안(자동 선택 아님)', async () => {
  const env = setup();
  try {
    const sha = commitProgress(env);
    const d = await progressDraft(env.ex, 'C1');
    assert.match(d.draft.goal, /^\[C1\] 엣지/);
    assert.ok(d.draft.prompt.includes(`development-progress.json @ main ${sha}`));
    assert.ok(d.draft.prompt.includes('> FN/(TP+FN)<=5%\n> 양성 각 20판정단위'), '완료 조건 원문을 줄 단위로 인용');
    assert.ok(d.draft.prompt.includes('> 통과한 근거가 없다.'));
    for (const needle of ['범위 제한:', '학습·모델 비교·사진 추론·성능 수치 평가는 기본 checkout의 단일 담당자', '점수·진척률·배점·판정을 바꾸지 않는다', '사람 정답·라벨']) assert.ok(d.draft.prompt.includes(needle), needle);
    assert.deepEqual(d.suggestedFiles, ['card_condition/listing_readiness.py']);
    assert.deepEqual(d.skippedEvidence.map((s) => s.path).sort(), ['../escape.py', 'artifacts/x/REPORT.md', 'missing/file.py']);
    assert.match(d.skippedEvidence.find((s) => s.path.startsWith('artifacts'))!.why, /데이터·산출물/);
    await assert.rejects(progressDraft(env.ex, 'C9'), /미완료 진행률 항목 없음/, '완료된 항목은 대상이 아님');
    await assert.rejects(progressDraft(env.ex, 'ZZ'), /미완료 진행률 항목 없음/);
  } finally { env.cleanup(); }
});

test('초안으로 작업 준비: 계약 파일에 원문과 범위 제한이 기록되고 ./develop 경로로 분류됨', async () => {
  const env = setup();
  try {
    commitProgress(env);
    const d = await progressDraft(env.ex, 'C1');
    const r = await prepareTask({ agent: 'claude', mode: 'manual', goal: d.draft.goal, doneCriteria: d.draft.doneCriteria, prompt: d.draft.prompt, allowedFiles: d.suggestedFiles,
      checks: [{ id: 'ws', name: '공백', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'] }] });
    const t = getTask(env.ex, r.taskId!);
    const text = fs.readFileSync(path.join(t.worktree, t.contractPath), 'utf8');
    assert.ok(text.includes('> FN/(TP+FN)<=5%') && text.includes('점수·진척률·배점·판정을 바꾸지 않는다'));
    assert.equal(t.usesDevelopLock, true);
    assert.equal(t.env, 'python');
    assert.ok(!text.includes(t.worktree), '계약에 로컬 경로 없음');
  } finally { env.cleanup(); }
});

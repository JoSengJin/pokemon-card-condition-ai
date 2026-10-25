// 파이프라인 단계 판정(화면과 같은 코드). 서버·브라우저 없이 작업 상태 스냅샷만으로 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { currentKey, stagesOf, STAGES } from '../src/ui/js/stages.js';

const SHA = 'a'.repeat(40);
const base = (over: Record<string, unknown> = {}) => ({
  taskId: 't1', agent: 'claude', mode: 'manual', status: 'assigned', statusReason: '', contractHash: 'h1',
  envReadiness: { ready: true }, result: null, verification: null, review: null, handoff: null, approval: null, integration: null, ...over,
});
const result = { headSha: SHA, checksPassed: true, commits: ['c1'] };
const passed = { sha: SHA, contractHash: 'h1', status: 'passed' };
const by = (stages: any[]) => Object.fromEntries(stages.map((s) => [s.key, s.status]));

test('단계 10개가 순서대로 나오고 배정 직후에는 준비가 사람 차례', () => {
  const st = stagesOf(base(), null, 'codex');
  assert.deepEqual(st.map((s: any) => s.key), STAGES.map((s: any) => s.key));
  assert.equal(st[0].status, 'action');
  assert.equal(st[0].primary.act, 'start');
  assert.equal(currentKey(st), 'prepare');
  assert.ok(st.slice(1).every((s: any) => s.status === 'todo'));
});

test('환경 미준비·시작 차단은 준비 단계에서 표시', () => {
  assert.equal(stagesOf(base({ envReadiness: { ready: false } }), null)[0].primary.act, 'env');
  const blocked = stagesOf(base({ status: 'blocked', statusReason: '충돌: task-x' }), null);
  assert.equal(blocked[0].status, 'failed');
  assert.equal(blocked[0].text, '충돌: task-x');
});

test('수동 작업 중은 구현 단계가 진행 중이고 대표 행동은 작업 완료', () => {
  const st = stagesOf(base({ status: 'manual_working' }), null);
  assert.equal(by(st).build, 'active');
  assert.equal(st[1].primary.act, 'finish');
  assert.equal(currentKey(st), 'build');
});

test('검토 단계: 테스트 미실행이면 작업 테스트가 사람 차례, 통과하면 인계 차례', () => {
  let st = stagesOf(base({ status: 'review_pending', result }), null, 'codex');
  assert.equal(by(st).gitcheck, 'done');
  assert.equal(by(st).tests, 'action');
  assert.equal(by(st).handoff, 'todo');
  assert.equal(by(st).approve, 'todo');
  assert.equal(by(st).review, 'skipped');
  assert.equal(currentKey(st), 'tests');
  st = stagesOf(base({ status: 'review_pending', result, verification: passed }), null, 'codex');
  assert.equal(by(st).tests, 'done');
  assert.equal(by(st).handoff, 'action');
  assert.match(st.find((s: any) => s.key === 'handoff').text, /codex에게 인계/);
  assert.equal(by(st).approve, 'action', '인계는 승인의 필수 조건이 아님');
  assert.equal(currentKey(st), 'handoff');
});

test('이전 SHA의 테스트 결과는 통과로 보지 않음, Git 검사 실패는 다시 수집 안내', () => {
  const stale = stagesOf(base({ status: 'review_pending', result, verification: { ...passed, sha: 'b'.repeat(40) } }), null);
  assert.equal(by(stale).tests, 'action');
  assert.match(stale.find((s: any) => s.key === 'tests').text, /코드가 바뀜/);
  assert.equal(by(stale).approve, 'todo');
  const bad = stagesOf(base({ status: 'review_pending', result: { ...result, checksPassed: false } }), null);
  assert.equal(by(bad).gitcheck, 'failed');
  assert.equal(currentKey(bad), 'gitcheck');
});

test('인계 진행 중이면 메인 차례, 인계 후 코드가 바뀌면 주의', () => {
  const h = { to: 'codex', headSha: SHA };
  let st = stagesOf(base({ status: 'review_pending', result, verification: passed, handoff: h }), null);
  assert.equal(by(st).handoff, 'active');
  assert.equal(st.find((s: any) => s.key === 'handoff').who, 'codex');
  st = stagesOf(base({ status: 'review_pending', result, verification: passed, handoff: { ...h, headSha: 'c'.repeat(40) } }), null);
  assert.equal(by(st).handoff, 'warn');
});

test('승인·통합·통합 후 검사·푸시 단계', () => {
  const ok = { result, verification: passed, approval: { sha: SHA } };
  assert.equal(by(stagesOf(base({ status: 'approved', ...ok }), null)).integrate, 'action');
  const merged = base({ status: 'integrated', ...ok, integration: { postStatus: 'not_run' } });
  let st = stagesOf(merged, { records: [] });
  assert.equal(by(st).postcheck, 'skipped');
  assert.equal(by(st).push, 'action');
  assert.equal(currentKey(st), 'push');
  st = stagesOf(merged, { records: [{ id: 'p1', tasks: ['t1'], status: 'pushed_verified', revert: null }] });
  assert.equal(by(st).push, 'done');
  st = stagesOf(merged, { records: [{ id: 'p1', tasks: ['t1'], status: 'pushed_verified', revert: { pushedAs: 'p2' } }] });
  assert.equal(by(st).push, 'warn');
  st = stagesOf(base({ status: 'integrated_check_failed', ...ok, integration: { postStatus: 'failed' } }), { records: [] });
  assert.equal(by(st).postcheck, 'failed');
  assert.equal(by(stagesOf(base({ status: 'integration_conflict', ...ok }), null)).integrate, 'failed');
  assert.equal(by(stagesOf(base({ status: 'rejected', ...ok }), null)).approve, 'failed');
});

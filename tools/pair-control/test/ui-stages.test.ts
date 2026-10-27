// 파이프라인 단계 판정(화면과 같은 코드). 서버·브라우저 없이 작업 상태 스냅샷만으로 검사한다.
import assert from 'node:assert/strict';
import { test } from 'node:test';
// @ts-ignore 화면용 ESM 모듈(타입 없음)
import { currentKey, gate, stagesOf, venvMissing, STAGES } from '../src/ui/js/stages.js';

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

test('.venv가 없어서 막힌 준비 단계의 대표 버튼은 환경 만들기, 다른 이유면 다시 확인', () => {
  const missing = { ready: false, checks: [{ name: '자체 .venv', ok: false, detail: '없음' }] };
  assert.equal(stagesOf(base({ envReadiness: missing }), null)[0].primary.act, 'venv');
  assert.equal(venvMissing(missing), true);
  const other = { ready: false, checks: [{ name: '자체 .venv', ok: false, detail: '.venv가 심볼릭 링크 — 다른 checkout과 공유 금지' }] };
  assert.equal(stagesOf(base({ envReadiness: other }), null)[0].primary.act, 'env');
  assert.equal(venvMissing({ ready: true, checks: [] }), false);
});

test('통합 후 검사가 도는 중이면 통합은 완료, 통합 후 검사가 진행 중이고 그 단계가 지금 단계', () => {
  const ok = { result, verification: passed, approval: { sha: SHA } };
  const running = base({ status: 'integrating', ...ok, integration: { postStatus: 'running', postChecks: [{ id: 'p1', name: 'x', status: 'running', logPath: 'x.log' }] } });
  const st = stagesOf(running, null);
  assert.equal(by(st).integrate, 'done');
  assert.equal(by(st).postcheck, 'active');
  assert.equal(currentKey(st), 'postcheck');
  assert.equal(by(stagesOf(base({ status: 'integrating', ...ok }), null)).integrate, 'active', '검사 전의 통합 중은 그대로');
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
  assert.equal(by(st).approve, 'todo', '앞 단계(메인 인계)가 끝나기 전에는 승인이 열리지 않음');
  assert.match(st.find((s: any) => s.key === 'approve').text, /앞 단계\(메인 인계\) 완료 후/);
  assert.equal(st.find((s: any) => s.key === 'approve').primary, null);
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
  assert.equal(by(st).handoff, 'action', '도는 프로세스가 없으면 회전(진행 중)이 아니라 사람이 할 일');
  assert.equal(by(st).approve, 'todo');
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

test('자동 확인: 별도 프로세스가 도는 동안만 진행 중, approve가 아니면 사람 차례로 남고 승인은 열리지 않는다', () => {
  const h = { to: 'codex', headSha: SHA };
  const rv = (over: any) => ({ reviewer: 'codex', forHandoff: true, sha: SHA, status: 'running', ...over });
  let st = stagesOf(base({ status: 'review_pending', result, verification: passed, handoff: h, review: rv({}) }), null);
  assert.equal(by(st).handoff, 'active');
  assert.equal(by(st).approve, 'todo');
  const res = { at: 'x', status: 'done', verdict: 'insufficient_evidence', summary: '근거 부족' };
  st = stagesOf(base({ status: 'review_pending', result, verification: passed, handoff: { ...h, autoResult: res }, review: rv({ status: 'done', verdict: 'insufficient_evidence' }) }), null);
  assert.equal(by(st).handoff, 'action');
  assert.match(st.find((s: any) => s.key === 'handoff').text, /자동 확인 결과: 근거 부족/);
  assert.equal(st.find((s: any) => s.key === 'handoff').primary.act, 'hconfirm');
  assert.equal(by(st).approve, 'todo');
  st = stagesOf(base({ status: 'review_pending', result, verification: passed, handoff: { ...h, confirmedAt: 'now', auto: true } }), null);
  assert.equal(by(st).handoff, 'done');
  assert.equal(by(st).approve, 'action', '메인 확인이 끝나면 승인이 열림');
});

test('단계 전환: 앞 단계가 끝나지 않으면 뒤 단계의 할 일은 대기로 낮추고, 선택 단계(리뷰) 의견은 막지 않는다', () => {
  const mk = (key: string, status: string) => ({ key, label: key, status, text: '', primary: { act: 'x' } });
  const out = gate([mk('a', 'done'), mk('b', 'action'), mk('c', 'action'), mk('d', 'todo')]);
  assert.deepEqual(out.map((s: any) => s.status), ['done', 'action', 'todo', 'todo']);
  assert.equal(out[2].primary, null);
  const withReview = gate([mk('tests', 'done'), mk('review', 'warn'), mk('handoff', 'action')]);
  assert.equal(withReview[2].status, 'action', '리뷰 의견(warn)은 뒤를 막지 않음');
  const running = gate([mk('tests', 'done'), mk('review', 'active'), mk('handoff', 'action')]);
  assert.equal(running[2].status, 'todo', '리뷰가 도는 동안은 대기');
  const failed = gate([mk('gitcheck', 'failed'), mk('tests', 'action')]);
  assert.deepEqual(failed.map((s: any) => s.status), ['failed', 'todo']);
});

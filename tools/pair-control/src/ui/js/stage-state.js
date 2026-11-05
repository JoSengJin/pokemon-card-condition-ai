import { STAGES } from './stage-catalog.js';
import { testState, reviewState, handoffState, pushStateOf } from './stage-evidence.js';
import { gate } from './stage-gate.js';

export function stagesOf(t, push, mainAgent) {
  const s = t.status, r = t.result, env = t.envReadiness;
  const after = ['review_pending', 'approved', 'integrating', 'integrated', 'integrated_check_failed', 'integration_refused', 'integration_conflict', 'integration_blocked', 'rejected'];
  const has = !!r && after.includes(s);
  const merged = s === 'integrated' || s === 'integrated_check_failed';
  const review = s === 'review_pending';
  const tests = testState(t), rv = reviewState(t), ho = handoffState(t);
  const testsOk = tests.status === 'passed';
  const main = (t.handoff && !t.handoff.cancelledAt && t.handoff.to) || mainAgent || 'codex';
  const ps = merged ? pushStateOf(t, push) : null;
  const post = t.integration && t.integration.postStatus;
  const build = {
    assigned: ['todo', '시작 전'], blocked: ['todo', '시작 전'], starting: ['active', '시작 중'], running: ['active', '에이전트 실행 중(도구가 감독)'],
    collecting: ['active', '결과 수집 중'], cancelling: ['active', '중단 중'], manual_working: ['active', t.agent + ' 세션에서 작업 중'],
    orphan_running: ['warn', '재시작 전 프로세스가 아직 실행 중'], exit_observed: ['action', '재시작 후 종료 관찰 — 결과 반영 필요'],
    unknown: ['failed', '결과 불명'], failed: ['failed', '에이전트 실패'], cancelled: ['failed', '중단됨'], abandoned: ['failed', '결과 불명 확정(미완료)'],
  }[s] || ['done', r ? '계약 이후 커밋 ' + r.commits.length + '개' : '완료'];
  const vals = {
    prepare: s === 'blocked' ? ['failed', t.statusReason || '시작 차단', { act: 'start', label: '다시 시작' }]
      : s === 'assigned' ? (env && !env.ready ? ['action', '실행 환경 준비 필요', venvMissing(env) ? { act: 'venv', label: '환경 만들기' } : { act: 'env', label: '준비 상태 다시 확인' }]
        : ['action', '시작 대기', { act: 'start', label: t.mode === 'manual' ? '작업 시작(파일 점유)' : '에이전트 시작' }])
        : ['done', '계약·환경 준비됨'],
    build: [build[0], build[1], s === 'manual_working' ? { act: 'finish', label: '작업 완료 — 결과 수집' }
      : s === 'exit_observed' ? { act: 'apply', label: '결과 반영' } : ['failed', 'cancelled'].includes(s) ? { act: 'start', label: '다시 시작' }
        : s === 'unknown' ? { act: 'ack', label: '결과 불명 확정' } : null],
    gitcheck: !has ? ['todo', '구현 후'] : r.checksPassed ? ['done', '통과'] : ['failed', '실패 — 고친 뒤 다시 수집', review ? { act: 'recollect', label: '결과 다시 수집' } : null],
    tests: !has ? ['todo', '구현 후'] : testsOk ? ['done', '통과'] : tests.status === 'running' ? ['active', '실행 중']
      : review ? [tests.status === 'none' ? 'action' : tests.status === 'stale' ? 'action' : 'failed', tests.text, { act: 'checks', label: '작업 테스트 실행' }]
        : ['warn', tests.text],
    // 인계 자동 확인용 리뷰는 6. 메인 인계 단계의 일부다. 5단계가 돌고 있다고 6단계를 막지 않는다.
    review: !has ? ['todo', '구현 후'] : rv.status === 'active' && t.review && t.review.forHandoff ? ['skipped', '자동 확인 중 — 6. 메인 인계에서 진행', null]
      : [rv.status, rv.text, review && rv.status !== 'active' ? { act: 'review', label: '리뷰 실행' } : null],
    handoff: !has ? ['todo', '구현 후'] : ho.status === 'done' ? ['done', ho.text] : (ho.status === 'active' || ho.status === 'action') ? [ho.status, ho.text, ho.status === 'action' ? { act: 'hconfirm', label: '메인 확인 완료' } : null]
      : ho.status === 'stale' ? ['warn', ho.text, { act: 'handoff', label: '다시 인계' }]
        : review ? (testsOk ? ['action', main + '에게 인계할 차례', { act: 'handoff', label: '메인에게 인계' }] : ['todo', '작업 테스트 통과 후'])
          : ['skipped', '인계 없이 진행됨'],
    approve: !has ? ['todo', '앞 단계 후'] : s === 'rejected' ? ['failed', '거절됨']
      : review ? (r.checksPassed && testsOk ? ['action', '승인 대기 — diff 확인 후 승인', { act: 'diff', label: 'diff 보고 승인' }] : ['todo', 'Git 검사·작업 테스트 통과 후'])
        : ['done', t.approval ? 'SHA ' + t.approval.sha.slice(0, 12) : '승인됨'],
    integrate: s === 'approved' ? ['action', t.statusReason && /사용 중|깨끗하지|미준비/.test(t.statusReason) ? '대기: ' + t.statusReason : '통합 실행 대기', { act: 'integrate', label: '통합 실행' }]
      : s === 'integrating' ? (post === 'running' ? ['done', '통합됨 · 통합 후 검사 중'] : ['active', '통합 중']) : merged ? ['done', '통합됨']
        : s === 'integration_refused' ? ['failed', '승인 무효화 — 재검토 필요', { act: 'rereview', label: '재검토' }]
          : s === 'integration_conflict' ? ['failed', '충돌로 중단(abort)'] : ['todo', '승인 후'],
    postcheck: !merged ? (post === 'running' ? ['active', '통합 후 검사 실행 중'] : ['todo', '통합 후']) : post === 'passed' ? ['done', '통과'] : post === 'failed' ? ['failed', '실패 — 복구 필요'] : ['skipped', '지정 없음(미실행)'],
    push: ps ? [ps.status, ps.text, ps.primary || null] : ['todo', '통합 후'],
  };
  const who = { prepare: '사용자', build: t.agent, gitcheck: '도구', tests: '도구(사용자가 실행)', review: '리뷰 에이전트', handoff: main, approve: '사용자', integrate: '사용자→도구', postcheck: '도구', push: '사용자' };
  return gate(STAGES.map((st) => ({ ...st, status: vals[st.key][0], text: vals[st.key][1], primary: vals[st.key][2] || null, who: who[st.key] })));
}

export function venvMissing(env) {
  if (!env || env.ready) return false;
  for (const check of env.checks || []) if (check.name === '자체 .venv' && !check.ok && check.detail === '없음') return true;
  return false;
}

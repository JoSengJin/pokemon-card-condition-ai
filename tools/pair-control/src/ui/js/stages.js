// 작업 상태에서 파이프라인 단계를 파생한다(저장하지 않음). 화면과 단위 검사가 같은 판정을 쓴다.
// 상태: done 완료 · active 진행 중 · action 사람이 할 일 · failed 실패 · warn 주의 · todo 대기 · skipped 건너뜀(선택 단계)
export const STAGES = [
  { key: 'prepare', label: '준비', desc: '계약 커밋·작업 폴더·실행 환경. 시작하면 이 작업이 허용 파일을 점유합니다.' },
  { key: 'build', label: '구현', desc: '에이전트가 작업 폴더에서 코딩·커밋합니다. 수동 모드는 에이전트 세션에서 진행하고 끝나면 "작업 완료"를 누릅니다.' },
  { key: 'gitcheck', label: 'Git 검사', desc: '브랜치·커밋·계약 불변·허용 파일 범위만 봅니다. 코드가 맞는지는 검사하지 않습니다.' },
  { key: 'tests', label: '작업 테스트', desc: '계약의 검사 명령을 실행기가 따로 실행합니다. 미실행·이전 SHA 결과는 통과가 아닙니다.' },
  { key: 'review', label: '리뷰', desc: '선택 단계. 다른 에이전트가 고정 SHA 묶음을 별도로 검토합니다. 결과는 참고이며 승인을 대신하지 않습니다.' },
  { key: 'handoff', label: '메인 인계', desc: '메인 에이전트에게 결과를 넘기고 확인받습니다. 안내문을 메인에게 붙여 넣거나 "인계 + 자동 확인"을 쓰며, 자동 확인이 approve가 아니면 사람이 확인 완료를 눌러야 다음 단계로 갑니다.' },
  { key: 'approve', label: '사람 승인', desc: '앞 단계가 모두 끝난 뒤에만 열립니다. diff와 검사 결과를 보고 전체 SHA를 승인하거나 거절합니다.' },
  { key: 'integrate', label: '통합', desc: '승인한 SHA를 다시 확인한 뒤 통합 checkout에서 ./develop 잠금 안으로 cherry-pick 합니다.' },
  { key: 'postcheck', label: '통합 후 검사', desc: '통합 checkout에서 계약의 통합 후 검사를 실행합니다. 지정이 없으면 미실행으로 남습니다.' },
  { key: 'push', label: '푸시', desc: '통합 브랜치를 원격에 올립니다. 취소할 수 없으므로 점검→SHA 입력→푸시→원격 확인 순서입니다.' },
];

/** 파일을 점유 중인 작업 상태(서버 OCCUPYING과 같은 목록). 새 작업 폼이 메인에게 점유 작업을 알려 줄 때 쓴다. */
export const OCCUPYING_STATUSES = ['starting', 'running', 'manual_working', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
  'review_pending', 'approved', 'integrating', 'integration_refused', 'integration_conflict', 'integration_blocked'];

/** 현재 HEAD·계약 기준 작업 테스트 상태. 다른 SHA·계약의 결과는 통과로 보지 않는다. */
export function testState(t) {
  const v = t.verification, sha = t.result && t.result.headSha;
  if (!v) return { status: 'none', text: '미실행' };
  if (v.sha !== sha || v.contractHash !== t.contractHash) return { status: 'stale', text: '코드가 바뀜 — 다시 실행' };
  const map = { running: '실행 중', passed: '통과', failed: '실패', cancelled: '중단됨', unknown: '결과 불명', interrupted: '재시작으로 끊김' };
  return { status: v.status, text: map[v.status] || v.status };
}

export function reviewState(t) {
  const r = t.review, sha = t.result && t.result.headSha;
  if (!r) return { status: 'skipped', text: '선택 · 미실행' };
  if (r.status === 'running') return { status: 'active', text: '리뷰 실행 중' };
  if (r.sha !== sha) return { status: 'warn', text: '이전 SHA 리뷰' };
  if (r.status === 'done') {
    const v = { approve: ['done', '승인 의견'], changes_requested: ['warn', '수정 필요 의견'], insufficient_evidence: ['warn', '근거 부족 의견'] }[r.verdict] || ['warn', String(r.verdict)];
    return { status: v[0], text: v[1] };
  }
  return { status: 'warn', text: { failed: '리뷰 실패(판정 없음)', cancelled: '리뷰 중단', unknown: '리뷰 결과 불명' }[r.status] || r.status };
}

export function handoffState(t) {
  const h = t.handoff, sha = t.result && t.result.headSha;
  if (!h || h.cancelledAt) return { status: 'none', text: '미인계' };
  if (h.headSha !== sha) return { status: 'stale', text: '인계 후 코드 변경 — 다시 인계' };
  if (h.confirmedAt) return { status: 'done', text: h.to + (h.auto ? ' 자동 확인 완료' : ' 확인 완료') };
  // 도는 프로세스가 있을 때만 진행 중(회전)으로 본다. 그 밖에는 사람이 확인해 줘야 하는 대기다.
  const r = t.review;
  if (r && r.forHandoff && r.status === 'running' && r.sha === h.headSha) return { status: 'active', text: h.to + ' 자동 확인 중(별도 프로세스)' };
  // 이 기능 이전에 끝난 자동 확인 리뷰는 autoResult가 없으므로 리뷰 기록에서 같은 결과를 읽는다.
  const a = h.autoResult || (r && r.forHandoff && r.status !== 'running' && r.sha === h.headSha ? { status: r.status, verdict: r.verdict } : null);
  if (a) {
    const word = { insufficient_evidence: '근거 부족', changes_requested: '수정 필요', approve: '승인' }[a.verdict] || ({ failed: '실패', cancelled: '중단', unknown: '결과 불명' }[a.status] || a.status);
    return { status: 'action', text: '자동 확인 결과: ' + word + ' — 사람이 내용을 보고 확인 완료 또는 인계 취소' };
  }
  return { status: 'action', text: h.to + ' 확인 대기 — 안내문을 전달하고 끝나면 "메인 확인 완료"' };
}

/** 이 작업의 통합 커밋이 들어간 가장 최근 푸시 기록으로 판정한다(기록은 최신순). */
export function pushStateOf(t, push) {
  const rec = ((push && push.records) || []).find((r) => r.tasks.includes(t.taskId));
  if (!rec) return { status: 'action', text: '아직 푸시 안 함', primary: { act: 'pushcheck', label: '푸시 점검' } };
  if (rec.status === 'pushed_verified') return rec.revert && rec.revert.pushedAs ? { status: 'warn', text: '푸시 후 되돌림됨' } : { status: 'done', text: '원격 반영 확인' };
  if (rec.status === 'push_failed') return { status: 'failed', text: '푸시 실패(원격 그대로)', primary: { act: 'pushcheck', label: '다시 점검' } };
  return { status: 'warn', text: '결과 불명 — 원격 다시 확인', primary: { act: 'verify', label: '원격 다시 확인', id: rec.id } };
}

/**
 * 단계 목록. 각 단계는 상태·한 줄 설명·누가 하는지·대표 행동(있으면)을 가진다.
 * 대표 행동은 사람이 할 일일 때만 붙인다(진행 중·완료는 버튼 없음).
 */
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

/**
 * 단계 전환 규칙: 앞 단계가 완료(done)되거나 선택 단계라 건너뛴(skipped) 경우에만 다음 단계가 열린다.
 * 앞 단계가 끝나지 않았으면 뒤 단계의 '할 일·진행 중'은 대기로 낮추고 버튼도 없앤다(눌러도 서버가 막는다).
 * 리뷰는 선택·참고 단계라 돌고 있을 때(active)만 뒤를 막고, 근거 부족 같은 의견은 막지 않는다. 실패·주의 단계는 그대로 보여 준다.
 */
export function gate(stages) {
  let wait = null;
  return stages.map((s) => {
    const out = wait && ['action', 'active'].includes(s.status)
      ? { ...s, status: 'todo', text: '앞 단계(' + wait.label + ') 완료 후', primary: null } : s;
    if (!wait && !['done', 'skipped'].includes(s.status) && !(s.key === 'review' && s.status !== 'active')) wait = s;
    return out;
  });
}

/** 실행 환경이 막힌 이유가 '자체 .venv 없음'뿐인지(그러면 버튼 한 번으로 만들 수 있다). 검사 항목이 없으면 알 수 없으므로 false. */
export function venvMissing(env) {
  return !!env && !env.ready && (env.checks || []).some((c) => c.name === '자체 .venv' && !c.ok && c.detail === '없음');
}

/** 지금 볼 단계: 사람이 할 일·진행 중·실패·주의가 있는 첫 단계, 없으면 마지막 완료 단계. */
export function currentKey(stages) {
  const live = stages.find((x) => ['action', 'active', 'failed', 'warn'].includes(x.status) && x.key !== 'review');
  if (live) return live.key;
  const done = stages.filter((x) => x.status === 'done');
  return done.length ? done[done.length - 1].key : stages[0].key;
}

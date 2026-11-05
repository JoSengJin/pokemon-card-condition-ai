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

export function pushStateOf(t, push) {
  const rec = ((push && push.records) || []).find((r) => r.tasks.includes(t.taskId));
  if (!rec) return { status: 'action', text: '아직 푸시 안 함', primary: { act: 'pushcheck', label: '푸시 점검' } };
  if (rec.status === 'pushed_verified') return rec.revert && rec.revert.pushedAs ? { status: 'warn', text: '푸시 후 되돌림됨' } : { status: 'done', text: '원격 반영 확인' };
  if (rec.status === 'push_failed') return { status: 'failed', text: '푸시 실패(원격 그대로)', primary: { act: 'pushcheck', label: '다시 점검' } };
  return { status: 'warn', text: '결과 불명 — 원격 다시 확인', primary: { act: 'verify', label: '원격 다시 확인', id: rec.id } };
}

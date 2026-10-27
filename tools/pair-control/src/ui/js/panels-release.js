// 파이프라인 뒤쪽 단계의 상세 패널: 메인 인계 · 사람 승인 · 통합 · 통합 후 검사 · 푸시.
import { B, esc, lbl } from './core.js';
import { reviewState, testState } from './stages.js';

const PSTATUS = { pushed_verified: ['푸시됨 · 원격 확인됨', 'ok'], push_failed: ['푸시 실패(원격 변경 없음)', 'bad'], push_unverified: ['결과 불명 · 원격 확인 필요', 'warn'], remote_mismatch: ['원격 SHA 불일치 · 확인 필요', 'bad'] };
const RUN = { pending: ['대기', 'muted'], running: ['실행 중', 'info'], passed: ['통과', 'ok'], failed: ['실패', 'bad'], cancelled: ['중단', 'warn'], unknown: ['결과 불명', 'bad'], not_run: ['미실행', 'muted'] };

export function panelHandoff(t, ui) {
  const h = t.handoff, s = t.status, r = t.result;
  const live = !!h && !h.cancelledAt && !!r && h.headSha === r.headSha;
  return '<p class="small muted">인계 문서는 브랜치에 커밋하지 않습니다.</p>' +
    (h ? '<div class="kv small"><div>받는 쪽</div><div>' + esc(h.to) + '</div><div>인계 SHA</div><div class="mono">' + esc(h.headSha) + '</div>' +
      '<div>상태</div><div>' + esc(h.cancelledAt ? '취소됨' : h.confirmedAt ? (h.auto ? '자동 확인(별도 프로세스) ' : '메인 확인 ') + h.confirmedAt : '메인 확인 대기') + '</div>' +
      (h.autoResult && !h.confirmedAt ? '<div>자동 확인 결과</div><div class="warn">' + esc(h.autoResult.verdict || h.autoResult.status) + ' — ' + esc(h.autoResult.summary || '') + '</div>' : '') + '</div>' : '') +
    '<textarea id="hText" readonly rows="6" placeholder="인계하면 메인에게 붙여 넣을 안내문이 나타납니다">' + esc(ui.handoff[t.taskId] || '') + '</textarea>' +
    '<div class="actions">' + B('handoff', '메인에게 인계', s === 'review_pending' && !!r && !live, 'primary') + B('handoffauto', '인계 + 자동 확인', s === 'review_pending' && !!r && !live) + B('hshow', '안내문 다시 불러오기', !!h) +
    B('copy', '안내문 복사', !!ui.handoff[t.taskId], '', ' data-target="hText" data-what="인계 안내문"') +
    B('hconfirm', '메인 확인 완료', s === 'review_pending' && live && !h.confirmedAt) +
    B('hcancel', '인계 취소', !!h && !h.cancelledAt && !t.approval, 'danger') + '</div>';
}

export function panelApprove(t, ui) {
  const s = t.status, r = t.result, sha = r && r.headSha;
  const seen = !!sha && !!ui.diff && ui.diff.key === t.taskId + ':' + sha;
  const ts = testState(t), rv = reviewState(t), h = t.handoff, rvRunning = rv.status === 'active';
  const why = s !== 'review_pending' ? '' : !r || !r.checksPassed ? 'Git 검사 실패' : ts.status !== 'passed' ? '작업 테스트 ' + ts.text : !seen ? '먼저 "diff 보기"로 변경 내용을 확인하세요' : !(h && !h.cancelledAt && h.confirmedAt && h.headSha === sha) ? '메인 인계가 끝나지 않음 — 인계하고 확인 완료 후 승인할 수 있습니다' : rvRunning ? '리뷰가 실행 중입니다' : '';
  const notes = s !== 'review_pending' || why ? [] : [
    rv.text !== '승인 의견' ? '리뷰: ' + rv.text + ' — 승인은 가능하지만 확인하세요' : '',
  ].filter(Boolean);
  const a = t.approval;
  return '<p class="small muted">승인 뒤 코드·계약·기준 브랜치·관련 파일이 바뀌면 승인은 자동으로 무효가 됩니다.</p>' +
    (why ? '<p class="warn">승인 불가: ' + esc(why) + '</p>' : '') + notes.map((n) => '<p class="warn small">⚠ ' + esc(n) + '</p>').join('') +
    '<div class="kv small"><div>승인할 SHA</div><div class="mono">' + esc(sha || '—') + '</div>' +
    '<div>승인 기록</div><div class="mono">' + esc(a ? a.sha + ' (기준 ' + a.baseBranch + '@' + a.baseHead.slice(0, 12) + ', 리뷰 ' + (a.reviewVerdict || '없음') + ')' : '—') + '</div></div>' +
    '<div class="actions">' + B('diff', seen ? 'diff 다시 불러오기' : 'diff 보기', !!sha) + B('approve', '이 SHA 승인', s === 'review_pending' && !why, 'primary') +
    B('unapprove', '승인 취소(검토로 되돌리기)', ['approved', 'integration_blocked'].includes(s)) +
    B('reject', '거절', ['review_pending', 'approved', 'integration_refused', 'integration_blocked'].includes(s), 'danger') + '</div>' +
    (seen ? '<h4>diff ' + esc(t.baseSha.slice(0, 12)) + '..' + esc(sha.slice(0, 12)) + ' (계약 커밋 포함)</h4><pre class="diff">' + esc(ui.diff.text) + '</pre>' : '');
}

export function panelIntegrate(t) {
  const g = t.integration, s = t.status;
  return '<p class="small muted">명령: <code>./develop -- git cherry-pick -x</code>. 충돌이 나면 자동으로 고르지 않고 중단(abort)합니다. 푸시는 다음 단계에서 따로 합니다.</p>' +
    (t.statusReason && ['approved', 'integration_refused', 'integration_conflict', 'integration_blocked'].includes(s) ? '<p class="warn">' + esc(t.statusReason) + '</p>' : '') +
    (g ? '<div class="kv small"><div>결과</div><div>' + esc(g.outcome + ' · ' + (g.detail || '').slice(0, 400)) + '</div>' +
      (g.preHead ? '<div>통합 전 SHA(복구 기준)</div><div class="mono">' + esc(g.preHead) + '</div>' : '') +
      (g.newHead ? '<div>통합 후 SHA</div><div class="mono">' + esc(g.newHead) + '</div>' : '') + '</div>' : '') +
    '<div class="actions">' + B('integrate', '통합 실행(./develop 잠금)', s === 'approved', 'primary') + B('unapprove', '승인 취소(검토로 되돌리기)', ['approved', 'integration_blocked'].includes(s)) + B('rereview', '재검토(에이전트 재실행 없음)', s === 'integration_refused') + '</div>';
}

export function panelPostcheck(t) {
  const g = t.integration;
  const specs = t.postChecks || [];
  return (specs.map((c) => '<div class="mono small">' + esc([c.executable].concat(c.args).join(' ')) + '</div>').join('') || '<p class="muted">계약에 통합 후 검사가 없습니다.</p>') +
    ((g && g.postChecks) || []).map((i) => '<div class="runrow">' + lbl(esc((RUN[i.status] || [i.status])[0]), (RUN[i.status] || ['', 'muted'])[1]) + ' <b>' + esc(i.name) + '</b> <span class="muted small">code ' + esc(i.exitCode ?? '—') + '</span>' +
      (i.logPath ? ' <button type="button" class="link" data-act="log" data-id="post:' + esc(i.id) + '">로그</button>' : '') + '</div>').join('') +
    (g && g.postStatus === 'failed' && g.preHead ? '<p class="bad small">복구가 필요하면 통합 전 SHA ' + esc(g.preHead.slice(0, 12)) + ' 를 기준으로 사람이 판단하세요(도구는 reset 하지 않습니다).</p>' : '');
}

export function panelPush(t, ui) {
  const ps = ui.state.push;
  if (!ps) return '<p class="muted">푸시 설정이 없습니다.</p>';
  const p = ps.plan, open = p ? p.findings.filter((f) => f.kind === 'secret_pattern' && !f.acknowledged) : [];
  const typed = String(ui.keep.pushConfirm || '').trim().toLowerCase();
  const ready = !!p && !p.blockers.length && typed.length >= 12 && p.localHead.startsWith(typed);
  const plan = !p ? '<p class="muted small">아직 점검하지 않았습니다. 먼저 ① 푸시 점검을 누르세요.</p>'
    : '<div class="kv small"><div>원격 SHA → 로컬 SHA</div><div class="mono">' + esc((p.remoteHead || '—').slice(0, 12) + ' → ' + (p.localHead || '—')) + '</div>' +
      '<div>점검 시각</div><div>' + esc(p.checkedAt) + '</div><div>포함된 작업</div><div>' + (p.tasks.map(esc).join(', ') || '—') + '</div>' +
      '<div>dry-run</div><div>' + (p.dryRun ? (p.dryRun.ok ? lbl('거절 없음', 'ok') : lbl(esc(p.dryRun.detail), 'bad')) : lbl('막힘이 있어 실행 안 함', 'muted')) + '</div></div>' +
      (p.revertOf ? '<p class="info small">이 푸시는 이전 푸시의 되돌림 커밋입니다.</p>' : '') +
      p.blockers.map((b) => '<div class="bad small">✗ ' + esc(b) + '</div>').join('') + p.warnings.map((w) => '<div class="warn small">⚠ ' + esc(w) + '</div>').join('') +
      (open.length ? '<div class="actions">' + B('pushack', '비밀 패턴 ' + open.length + '건을 오탐으로 확인(기록됨)', true) + '</div>' : '') +
      (p.commits.length ? '<h4>푸시할 커밋 ' + p.commits.length + '개</h4>' + p.commits.map((c, i) => '<div class="mono small">' + (i + 1) + '. ' + esc(c.sha.slice(0, 12) + ' ' + c.subject) + '</div>').join('') : '');
  return '<p class="small muted">대상 ' + esc(ps.remote + '/' + ps.branch) + ' · 일반 push만(force 없음) · 실수는 되돌림 커밋으로 바로잡습니다.</p>' +
    '<div class="actions">' + B('pushcheck', '① 푸시 점검(전송 없음)', true) + '</div>' + plan +
    '<div class="row"><input data-keep="pushConfirm" class="mono" value="' + esc(ui.keep.pushConfirm || '') + '" placeholder="② 푸시할 SHA 앞 12자를 직접 입력">' + B('push', '③ 푸시', ready, 'danger') + '</div>';
}

/** 푸시 기록(최신순). 원격 다시 확인·되돌림 준비 버튼을 함께 그린다. panelPush와 나란히 renderTask가 부른다(호출 깊이 제한). */
export function pushRecords(records) {
  return records.map((r) => {
    const rv = r.revert, st = PSTATUS[r.status] || [r.status, 'muted'];
    return '<div class="rec"><div><span class="chip">' + (r.kind === 'revert' ? '되돌림 푸시' : '푸시') + '</span> ' + lbl(esc(st[0]), st[1]) + ' <span class="muted small">' + esc(r.at) + '</span></div>' +
      '<div class="kv small"><div>원격 이전 → 이후</div><div class="mono">' + esc(r.preRemoteHead.slice(0, 12) + ' → ' + r.pushedSha.slice(0, 12) + ' (' + r.commits.length + '개 커밋)') + '</div>' +
      '<div>결과</div><div>' + esc(r.detail) + '</div>' + (r.tasks.length ? '<div>작업</div><div>' + r.tasks.map(esc).join(', ') + '</div>' : '') +
      (rv ? '<div>되돌림</div><div class="mono">' + esc(rv.newHead.slice(0, 12) + ' · 커밋 ' + rv.commits.length + '개 · ') + (rv.treeRestored ? lbl('트리 복원 ✓', 'ok') : lbl('트리 다름 ✗', 'bad')) + (rv.pushedAs ? ' · ' + lbl('되돌림 푸시 완료', 'ok') : ' · 위 ①~③으로 푸시') + '</div>' : '') + '</div>' +
      '<div class="actions">' + B('verify', '원격 다시 확인', true, '', ' data-id="' + esc(r.id) + '"') +
      (r.kind === 'push' && r.status === 'pushed_verified' && !rv ? B('revert', '되돌림 커밋 준비', true, 'danger', ' data-id="' + esc(r.id) + '"') : '') + '</div></div>';
  }).join('') || '<p class="muted small">기록 없음</p>';
}

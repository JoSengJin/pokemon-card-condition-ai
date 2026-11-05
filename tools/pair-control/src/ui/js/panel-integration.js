import { B, esc, lbl } from './core.js';
import { reviewState, testState } from './stages.js';
import { RUN } from './panel-push.js';

export const PSTATUS = { pushed_verified: ['푸시됨 · 원격 확인됨', 'ok'], push_failed: ['푸시 실패(원격 변경 없음)', 'bad'], push_unverified: ['결과 불명 · 원격 확인 필요', 'warn'], remote_mismatch: ['원격 SHA 불일치 · 확인 필요', 'bad'] };

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

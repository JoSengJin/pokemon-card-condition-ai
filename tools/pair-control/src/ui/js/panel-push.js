import { B, esc, lbl } from './core.js';

import { PSTATUS } from './panel-integration.js';

export const RUN = { pending: ['대기', 'muted'], running: ['실행 중', 'info'], passed: ['통과', 'ok'], failed: ['실패', 'bad'], cancelled: ['중단', 'warn'], unknown: ['결과 불명', 'bad'], not_run: ['미실행', 'muted'] };

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

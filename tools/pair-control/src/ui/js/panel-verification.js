import { B, esc, lbl } from './core.js';

export function panelGit(t, ui) {
  const r = t.result;
  if (!r) return '<p class="muted">구현이 끝나면 도구가 브랜치·커밋·허용 파일을 자동으로 검사합니다.</p>';
  const key = t.taskId + ':' + r.headSha;
  const diff = ui.diff && ui.diff.key === key ? ui.diff.text : '';
  return r.checks.map((c) => '<div>' + (c.ok ? lbl('✓', 'ok') : lbl('✗', 'bad')) + ' ' + esc(c.name) + ' <span class="muted">' + esc(c.detail) + '</span></div>').join('') +
    '<div class="kv small" style="margin-top:6px"><div>결과 SHA</div><div class="mono">' + esc(r.headSha) + '</div>' +
    '<div>변경 파일</div><div class="mono">' + (r.changedFiles.map(esc).join('<br>') || '—') + '</div>' +
    (r.outOfScope.length ? '<div>범위 밖</div><div class="mono bad">' + r.outOfScope.map(esc).join('<br>') + '</div>' : '') + '</div>' +
    '<div class="actions">' + B('diff', diff ? 'diff 다시 불러오기' : 'diff 보기', true) + B('recollect', '결과 다시 수집', t.status === 'review_pending') + '</div>' +
    (diff ? '<pre class="diff">' + esc(diff) + '</pre>' : '');
}

export function panelTests(t) {
  const v = t.verification, sha = t.result && t.result.headSha;
  const stale = v && (v.sha !== sha || v.contractHash !== t.contractHash);
  const names = { pending: '대기', running: '실행 중', passed: '통과', failed: '실패', cancelled: '중단', unknown: '결과 불명', not_run: '미실행' };
  const cls = { passed: 'ok', failed: 'bad', unknown: 'bad', cancelled: 'warn', running: 'info' };
  return '<h4>계약에 적힌 검사</h4>' + ((t.checks || []).map((c) => '<div class="mono small">' + esc([c.executable].concat(c.args).join(' ')) + ' <span class="muted">(cwd ' + esc(c.cwd) + ')</span></div>').join('') || '<p class="bad">검사가 없어 승인할 수 없습니다.</p>') +
    (v ? '<h4>실행 결과 ' + (stale ? lbl('이전 SHA 결과 — 통과로 보지 않음', 'warn') : '') + '</h4>' + v.items.map((i) => '<div class="runrow">' + lbl(esc(names[i.status] || i.status), cls[i.status] || 'muted') +
      ' <b>' + esc(i.name) + '</b> <span class="muted small">code ' + esc(i.exitCode ?? '—') + ' · SHA ' + esc((i.sha || '').slice(0, 12)) + '</span>' +
      (i.execId ? ' <button type="button" class="link" data-act="log" data-id="' + esc(i.execId) + '">로그</button>' : '') + '</div>').join('') +
      (v.note ? '<p class="warn small">' + esc(v.note) + '</p>' : '') : '<p class="muted">아직 실행하지 않았습니다. 미실행은 통과가 아닙니다.</p>') +
    '<div class="actions">' + B('checks', v ? '작업 테스트 다시 실행' : '작업 테스트 실행', t.status === 'review_pending' && (t.checks || []).length > 0 && !(v && v.status === 'running'), 'primary') + '</div>';
}

export function panelReview(t, ui) {
  const r = t.review;
  const other = t.agent === 'claude' ? 'Codex' : 'Claude';
  const sel = ui.keep.revScenario || 'approve';
  const opt = [['approve', '승인 의견'], ['changes_requested', '수정 필요'], ['insufficient_evidence', '근거 부족'], ['garbage', '형식 오류'], ['hang', '끝나지 않음']]
    .map((o) => '<option value="' + o[0] + '"' + (o[0] === sel ? ' selected' : '') + '>fake: ' + o[1] + '</option>').join('');
  return '<p>' + other + '가 고정 SHA·diff·계약·검사 결과 묶음을 <b>별도 프로세스</b>로 검토합니다. 현재 Codex 앱 대화로 보내지 않으며, 결과는 참고일 뿐 사람 승인을 대신하지 않습니다. 지금은 fake 리뷰 CLI(모델 요청 없음)만 연결되어 있습니다.</p>' +
    (r ? '<div class="kv small"><div>리뷰</div><div>' + esc(r.reviewer + ' (' + r.mode + ') · SHA ' + r.sha.slice(0, 12) + ' · ' + r.status + (r.verdict ? ' / ' + r.verdict : '')) + '</div>' +
      (r.summary ? '<div>요약</div><div>' + esc(r.summary) + '</div>' : '') + (r.note ? '<div>메모</div><div class="warn">' + esc(r.note) + '</div>' : '') + '</div>' +
      (r.execId ? '<button type="button" class="link" data-act="log" data-id="' + esc(r.execId) + '">리뷰 로그</button>' : '') : '') +
    '<div class="actions"><select data-keep="revScenario">' + opt + '</select>' + B('review', other + ' 리뷰 실행(mock)', t.status === 'review_pending' && !(r && r.status === 'running')) + '</div>';
}

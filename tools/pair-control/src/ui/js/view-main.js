import { esc, lbl } from './core.js';

export function renderMain(state, ui) {
  const m = state.main || { agent: 'codex', since: null };
  const other = m.agent === 'codex' ? 'claude' : 'codex';
  document.getElementById('mainSummary').innerHTML = '메인 역할: <b>' + esc(m.agent) + '</b> <span class="muted small">' + (m.since ? '(' + esc(m.since) + (m.reason ? ' · ' + esc(m.reason) : '') + ')' : '(기본값)') + '</span> — 이양하려면 펼치기';
  const swap = document.getElementById('bMainSwap');
  swap.textContent = other + '에게 표시만 이양';
  swap.title = '표시와 인계 메모만 바꿉니다(새 메인 프로세스를 실행하지 않음). 실제 교대는 아래 "새 메인 실행하며 교대"';
  swap.dataset.to = other;
  const b = ui.mainBlockers;
  document.getElementById('mainBlockers').innerHTML = !b ? '' : b.error ? lbl(esc(b.error), 'bad')
    : b.list.length ? b.list.map((x) => '<div class="bad">✗ ' + esc(x) + '</div>').join('') : lbl('✓ 이양을 막는 진행 중인 일이 없습니다', 'ok');
}

export const SESSION = { launching: '새 메인 실행 중(인수 확인 전)', taken_over: '인수 확인됨', completed: '교대 완료(인수 확인 + 다음 행동 수행)', idle: '인수됨(수행한 다음 행동 없음 — 완료 아님)', failed: '교대 실패' };

export function renderMainRuntime(state) {
  const r = state.mainRuntime;
  if (!r) return;
  const s = r.session, lim = Object.keys(r.limited || {});
  document.getElementById('mainRt').innerHTML =
    '<div>세대 <b>' + r.generation + '</b>' + (r.frozen ? ' · ' + lbl('교대 중 — 새 배정·승인·통합 정지', 'warn') : '') +
    (lim.length ? ' · 한도: ' + lim.map((a) => lbl(esc(a) + ' <button type="button" class="small" data-act="mainclear" data-agent="' + esc(a) + '">풀림 확인</button>', 'bad')).join(' ') : '') + '</div>' +
    (s ? '<div>' + esc(s.from) + ' → <b>' + esc(s.agent) + '</b> (세대 ' + s.generation + ') · ' + lbl(esc(SESSION[s.status] || s.status), s.status === 'completed' ? 'ok' : s.status === 'failed' ? 'bad' : 'info') +
      (s.limitRecovery ? ' <span class="muted">한도 복구</span>' : '') + (s.actionResults.length ? '<div class="muted">' + s.actionResults.map((a) => (a.ok ? '✓ ' : '✗ ') + esc(a.type + ': ' + a.detail)).join('<br>') + '</div>' : '') + '</div>' : '') +
    r.failures.map((f) => '<div class="warn">교대 실패 기록: ' + esc(f.reason) + (f.checkpointFile ? ' <span class="muted mono">복구 지점 ' + esc(f.checkpointFile.split('/').pop()) + '</span>' : '') + '</div>').join('');
  document.getElementById('apprList').innerHTML = r.approvals.length ? r.approvals.map((a) => '<div>' + (a.revokedAt ? '<s>' : '') + '· ' + esc(a.actions.join(', ')) + ' → ' + esc(a.targets === '*' ? '전체' : a.targets.join(', ')) +
    ' <span class="muted">근거: ' + esc(a.basis) + (a.boundSessionId ? ' · 세션 묶임(승계 안 됨)' : '') + '</span>' + (a.revokedAt ? '</s> 철회됨' : ' <button type="button" class="small" data-act="apprrevoke" data-id="' + esc(a.id) + '">철회</button>') + '</div>').join('') : '<span class="muted">기록된 승인 없음 — 교대한 새 메인은 어떤 행동도 수행하지 못합니다</span>';
}

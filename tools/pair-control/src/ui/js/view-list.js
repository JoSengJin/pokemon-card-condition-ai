// 화면 위쪽(연결·과금 가드·한도·메인 역할·CLI 확인)과 왼쪽 작업 목록(카드 + 작은 파이프라인).
import { esc, lbl } from './core.js';
import { currentKey, stagesOf } from './stages.js';

export const STATUS = {
  assigned: ['배정됨', 'muted'], blocked: ['시작 차단', 'warn'], starting: ['시작 중', 'info'],
  running: ['에이전트 실행 중', 'info'], collecting: ['결과 수집 중', 'info'], cancelling: ['중단 중', 'warn'], cancelled: ['중단됨', 'muted'],
  failed: ['에이전트 실패', 'bad'], orphan_running: ['재시작 전 프로세스 실행 중', 'warn'], exit_observed: ['재시작 후 종료 관찰', 'warn'],
  unknown: ['결과 불명', 'bad'], abandoned: ['결과 불명 확정', 'muted'],
  manual_working: ['수동 작업 중', 'info'], review_pending: ['검토 단계', 'warn'], approved: ['승인됨', 'warn'], rejected: ['거절됨', 'muted'],
  integrating: ['통합 중', 'info'], integrated: ['통합 완료', 'ok'], integrated_check_failed: ['통합 후 검사 실패', 'bad'],
  integration_refused: ['통합 거절', 'bad'], integration_conflict: ['통합 충돌', 'bad'], integration_blocked: ['통합 대기', 'warn'],
};

export function renderHeader(state) {
  const c = state.connection;
  const kind = { demo: ['데모 저장소', 'warn'], real: ['실제 저장소', 'info'], unconfigured: ['저장소 미설정', 'bad'] }[c.kind];
  document.getElementById('connKind').innerHTML = lbl(kind[0], kind[1]);
  document.getElementById('guard').innerHTML = state.guard ? lbl('과금 신호 감지 · 서비스 중단', 'bad') : '과금 신호 감지 없음';
  document.getElementById('connBar').innerHTML = '<span>저장소 <span class="mono">' + esc(c.repo || '—') + '</span></span>' +
    '<span>기준 브랜치 <span class="mono">' + esc(c.integrationBranch) + '</span></span>' +
    ['codex', 'claude'].map((a) => { const r = c.realRun[a]; return '<span>실제 ' + a + ' ' + (r.available ? lbl('가능', 'ok') : '<span class="bad" title="' + esc(r.blockers.map((b) => b.message + ' → ' + b.fix).join('\n')) + '">차단 ' + r.blockers.length + '</span>') + '</span>'; }).join('');
  const gb = document.getElementById('guardBanner');
  gb.hidden = !state.guard;
  gb.textContent = state.guard ? '유료 전환 신호 감지로 서비스 중단: ' + state.guard.detail + ' (' + state.guard.at + '). 확인 후 npm run guard:ack' : '';
  const lb = document.getElementById('limitBanner');
  lb.hidden = !state.limit;
  lb.innerHTML = !state.limit ? '' : '<span>구독 사용 한도 도달 — 실제 CLI 실행을 멈췄습니다(재시도·크레딧 구매 없음). ' + esc(state.limit.detail) + ' (' + esc(state.limit.at) + ')</span>' +
    '<button type="button" data-act="limitclear">한도가 풀린 것을 확인함</button>';
  // 배정 폼의 "실제 CLI" 선택지는 고른 에이전트의 실행 가능 여부를 따른다.
  const form = document.getElementById('assign');
  const agent = (form.agent && form.agent.value) || 'claude', rr = c.realRun[agent];
  const radio = form.querySelector('input[name=mode][value=real]');
  radio.disabled = !rr.available;
  if (radio.disabled && radio.checked) form.querySelector('input[name=mode][value=manual]').checked = true;
  document.getElementById('realLabel').classList.toggle('dis', !rr.available);
  document.getElementById('realWhy').innerHTML = rr.available ? '' : '실제 ' + esc(agent) + ' 실행 불가: ' + rr.blockers.map((b) => '<div>· ' + esc(b.message) + ' — <span class="muted">해결: ' + esc(b.fix) + '</span></div>').join('');
}

export function renderMain(state, ui) {
  const m = state.main || { agent: 'codex', since: null };
  const other = m.agent === 'codex' ? 'claude' : 'codex';
  document.getElementById('mainSummary').innerHTML = '메인 역할: <b>' + esc(m.agent) + '</b> <span class="muted small">' + (m.since ? '(' + esc(m.since) + (m.reason ? ' · ' + esc(m.reason) : '') + ')' : '(기본값)') + '</span> — 이양하려면 펼치기';
  const swap = document.getElementById('bMainSwap');
  swap.textContent = other + '에게 이양';
  swap.dataset.to = other;
  const b = ui.mainBlockers;
  document.getElementById('mainBlockers').innerHTML = !b ? '' : b.error ? lbl(esc(b.error), 'bad')
    : b.list.length ? b.list.map((x) => '<div class="bad">✗ ' + esc(x) + '</div>').join('') : lbl('✓ 이양을 막는 진행 중인 일이 없습니다', 'ok');
}

export function renderProbes(state) {
  const p = state.probes || {};
  document.getElementById('probes').innerHTML = ['codex', 'claude'].map((k) => {
    const x = p[k];
    if (!x) return '<div>' + k + ': 확인 전</div>';
    return '<div><b>' + k + '</b>: ' + (x.installed ? lbl('설치됨', 'ok') + ' ' + esc(x.version) : lbl('미설치', 'warn')) +
      ' · 확인 옵션 ' + esc(x.verifiedFlags.join(', ') || '없음') + (x.missingFlags.length ? ' · ' + lbl('미확인 ' + esc(x.missingFlags.join(', ')), 'warn') : '') + ' · ' + esc(x.note) + '</div>';
  }).join('') + '<div>실제 모델 호출: <b>' + (state.mode === 'mock-only' ? '차단(별도 승인 작업)' : '허용 설정됨') + '</b></div>';
}

/** 작업 카드 목록. 카드마다 10단계 점 줄과 지금 단계를 보여 준다. */
export function renderList(state, ui) {
  const el = document.getElementById('list');
  el.innerHTML = state.tasks.map((t) => {
    const st = stagesOf(t, state.push, state.main && state.main.agent);
    const cur = st.find((s) => s.key === currentKey(st));
    const s = STATUS[t.status] || [t.status, 'muted'];
    return '<button type="button" class="card' + (t.taskId === ui.selected ? ' sel' : '') + ' s-' + cur.status + '" data-act="select" data-id="' + esc(t.taskId) + '">' +
      '<div class="cardTop"><span class="mono">' + esc(t.taskId) + '</span>' + lbl(esc(s[0]), s[1]) + '</div>' +
      '<div class="cardGoal">' + esc(t.goal) + '</div>' + miniPipeline(st) +
      '<div class="small"><span class="muted">' + esc(t.agent) + ' · 지금</span> <b>' + esc(cur.label) + '</b> <span class="muted">' + esc(cur.text) + '</span></div></button>';
  }).join('') || '<p class="muted small">배정된 작업이 없습니다. 위의 "새 작업 만들기"로 시작하세요.</p>';
}

export function miniPipeline(stages) {
  return '<div class="mini" aria-hidden="true">' + stages.map((s) => '<i class="s-' + s.status + '" title="' + esc(s.label + ': ' + s.text) + '"></i>').join('') + '</div>';
}

import { esc, lbl } from './core.js';

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

export function renderProbes(state) {
  const p = state.probes || {};
  document.getElementById('probes').innerHTML = ['codex', 'claude'].map((k) => {
    const x = p[k];
    if (!x) return '<div>' + k + ': 확인 전</div>';
    return '<div><b>' + k + '</b>: ' + (x.installed ? lbl('설치됨', 'ok') + ' ' + esc(x.version) : lbl('미설치', 'warn')) +
      ' · 확인 옵션 ' + esc(x.verifiedFlags.join(', ') || '없음') + (x.missingFlags.length ? ' · ' + lbl('미확인 ' + esc(x.missingFlags.join(', ')), 'warn') : '') + ' · ' + esc(x.note) + '</div>';
  }).join('') + '<div>실제 모델 호출: <b>' + (state.mode === 'mock-only' ? '차단(별도 승인 작업)' : '허용 설정됨') + '</b></div>';
}

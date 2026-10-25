// 화면 공용 상태와 기본 도구. 다른 모듈은 ui 객체로 화면 상태를 공유한다.
// 다시 그리기는 ui.rerender / ui.refreshNow(함수 참조, app.js가 채움)로 별도 시작점에서 실행한다.
export const ui = {
  state: null, selected: null, stage: {}, keep: {}, diff: null, prompt: {}, handoff: {}, memo: '', mainBlockers: null,
  logChoice: null, log: { exec: null, next: 0, text: '' }, rerender: null, refreshNow: null,
  seen: {}, changedAt: null, // 직전에 그린 단계 상태(바뀐 노드를 깜빡이게)와 마지막 변화 시각
};

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

export function esc(v) { return String(v ?? '').replace(/[&<>"']/g, (c) => ESC[c]); }

/** 이미 안전한 텍스트에 색을 입힌다. 이스케이프는 호출하는 쪽에서 한다(호출 깊이를 늘리지 않기 위해). */
export function lbl(safeText, cls) { return '<span class="' + cls + '">' + safeText + '</span>'; }

/** data-act 버튼. label은 화면에 고정된 문구만 넘긴다. */
export function B(act, label, enabled, cls, extra) {
  return '<button type="button" data-act="' + act + '"' + (cls ? ' class="' + cls + '"' : '') + (extra || '') + (enabled ? '' : ' disabled') + '>' + label + '</button>';
}

export async function api(path, body, method) {
  const post = body !== undefined || method === 'POST';
  const opt = post ? { method: 'POST', headers: { 'content-type': 'application/json', 'x-pair-control': '1' }, body: JSON.stringify(body ?? {}) }
    : { signal: AbortSignal.timeout(8000) }; // 조회가 멈추면 1초 갱신이 영영 막히므로 8초에 끊는다
  const r = await fetch('/pair/api/' + path, opt);
  const j = await r.json().catch(() => ({ ok: false, error: 'HTTP ' + r.status }));
  if (!j.ok) throw new Error(j.error || 'HTTP ' + r.status);
  return j.data;
}

export function say(text, cls) {
  const el = document.getElementById('msg');
  el.className = 'msg ' + (cls || '');
  el.textContent = text || '';
  el.hidden = !text;
}

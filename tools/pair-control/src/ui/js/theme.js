// 화면 색 전환(시스템/밝게/어둡게). 고른 값은 브라우저에 기억하고(막혀 있으면 이번 화면에서만), 기본은 시스템 설정을 따른다.
// 색 자체는 page.html의 CSS 변수가 정하고, 여기서는 <html data-theme>만 바꾼다.
const KEY = 'pairTheme';

/** 알 수 없는 값은 system. */
export function normalize(v) { return v === 'light' || v === 'dark' ? v : 'system'; }

/** data-theme을 바꾸고(system이면 속성 제거) 버튼의 눌림 표시를 맞춘다. 저장은 막혀 있어도 화면은 바뀐다. */
export function applyTheme(v, save) {
  const t = normalize(v), root = document.documentElement;
  if (t === 'system') root.removeAttribute('data-theme'); else root.dataset.theme = t;
  for (const b of document.querySelectorAll('[data-theme-set]')) b.setAttribute('aria-pressed', String(b.dataset.themeSet === t));
  if (save) { try { localStorage.setItem(KEY, t); } catch { /* 저장이 막힌 환경(비공개 창 등): 이번 화면에서만 적용 */ } }
}

export function onThemeClick(ev) {
  const b = ev.target.closest('[data-theme-set]');
  if (b) applyTheme(b.dataset.themeSet, true);
}

export function initTheme() {
  let v = 'system';
  try { v = localStorage.getItem(KEY) || 'system'; } catch { /* 읽기 막힘 */ }
  applyTheme(v, false);
}

import { onClick, onInput } from './actions.js';
import { ui } from './core.js';
import { initForm } from './form.js';
import { initTheme, onThemeClick } from './theme.js';
import { render } from './app-render.js';
import { refresh, pollActivity } from './app-state.js';
import { pollLog, onLogScroll } from './app-log.js';

let busy = false;

ui.rerender = render;
ui.refreshNow = refresh;
document.addEventListener('click', onClick);
document.addEventListener('click', onThemeClick);
document.addEventListener('input', onInput);
document.addEventListener('change', onInput);
document.addEventListener('scroll', onLogScroll, true); // scroll도 버블링되지 않아 capture로 받는다
document.addEventListener('toggle', onInput, true); // toggle은 버블링되지 않아 capture로 받는다
// 숨겨진 탭은 브라우저가 타이머를 늦추므로, 다시 보일 때 바로 확인한다.
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('focus', () => refresh());
initTheme();
initForm();
setInterval(async () => {
  if (busy) return;
  busy = true;
  try { await refresh(); await pollLog(); await pollActivity(); } finally { busy = false; }
}, 1000);
refresh().then(pollLog);

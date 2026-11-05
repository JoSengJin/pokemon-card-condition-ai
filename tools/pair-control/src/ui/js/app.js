import { onClick, onInput } from './actions.js';
import { ui } from './core.js';
import { initForm } from './form.js';
import { initTheme, onThemeClick } from './theme.js';
import { render } from './app-render.js';
import { refresh, pollActivity } from './app-state.js';
import { pollLog, onLogScroll } from './app-log.js';

let busy = false;

ui.rerender = render;
ui.refreshNow = poll;
document.addEventListener('click', onClick);
document.addEventListener('click', onThemeClick);
document.addEventListener('input', onInput);
document.addEventListener('change', onInput);
document.addEventListener('scroll', onLogScroll, true); // scroll도 버블링되지 않아 capture로 받는다
document.addEventListener('toggle', onInput, true); // toggle은 버블링되지 않아 capture로 받는다
// 같은 폴링 진입점이 상태 수집과 렌더를 순서대로 수행한다.
document.addEventListener('visibilitychange', poll);
window.addEventListener('focus', poll);
initTheme();
initForm();
setInterval(poll, 1000);
poll();

async function poll() {
  if (busy || document.hidden) return;
  busy = true;
  try {
    if (await refresh()) render();
    await pollLog();
    if (await pollActivity()) render();
  } finally { busy = false; }
}

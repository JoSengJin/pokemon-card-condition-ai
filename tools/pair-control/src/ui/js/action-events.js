import { say, ui } from './core.js';
import { ACTIONS } from './action-routes.js';
import { run } from './action-request.js';

export async function onClick(ev) {
  const el = ev.target.closest('[data-act]');
  if (!el || el.disabled) return;
  const act = el.dataset.act;
  if (el.dataset.stage && ui.selected) ui.stage[ui.selected] = el.dataset.stage;
  if (act === 'select') ui.selected = el.dataset.id;
  else if (act === 'log') ui.keep.logSel = el.dataset.id;
  else if (act === 'logfollow') ui.keep.logFollow = ui.keep.logFollow === false;
  else if (act === 'logpause') ui.keep.logPaused = !ui.keep.logPaused;
  else if (act === 'copy') return copyText(document.getElementById(el.dataset.target), el.dataset.what);
  else if (act === 'maincopy') return copyText(document.getElementById('mainMemo'), '이양 메모');
  else if (ACTIONS[act]) await run(act, el);
  ui.rerender();
}

export async function onInput(ev) {
  const el = ev.target;
  if (el.id === 'mainBox' && ev.type === 'toggle' && el.open) { await run('maincheck', el); ui.rerender(); return; }
  const k = el.dataset && el.dataset.keep;
  if (!k) return;
  ui.keep[k] = el.type === 'checkbox' ? el.checked : el.tagName === 'DETAILS' ? el.open : el.value;
  if (k === 'logSel' || k === 'logFind') return ui.rerender(); // 로그 선택·찾기는 바로 다시 그린다
  if (k !== 'pushConfirm') return;
  const p = ui.state.push && ui.state.push.plan, v = el.value.trim().toLowerCase();
  const b = document.querySelector('[data-act=push]');
  if (b) b.disabled = !(p && !p.blockers.length && v.length >= 12 && p.localHead.startsWith(v));
}

export async function copyText(el, what) {
  const text = el && (el.value ?? el.textContent); // 칸(textarea)은 value, 로그(pre)는 textContent
  if (!text) return say(what + ': 복사할 내용이 없습니다', 'warn');
  try { await navigator.clipboard.writeText(text); say(what + ' 복사됨', 'ok'); }
  catch { if (el.select) el.select(); else window.getSelection().selectAllChildren(el); say('자동 복사를 못 했습니다. 선택된 텍스트를 직접 복사하세요(⌘C)', 'warn'); }
}

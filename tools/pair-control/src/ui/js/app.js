// 화면 시작점. 1초마다 상태를 받아 바뀌었을 때만 다시 그리고, 선택한 실행의 로그를 이어 받는다.
import { onClick, onInput } from './actions.js';
import { api, say, ui } from './core.js';
import { initForm } from './form.js';
import { renderHeader, renderList, renderMain, renderProbes } from './view-list.js';
import { renderTask } from './view-task.js';

let lastSig = '', busy = false;

function render() {
  if (!ui.state) return;
  // 다시 그려도 입력 중이던 칸의 포커스·커서를 지킨다(1초 갱신 때문에 입력이 끊기지 않게).
  const a = document.activeElement, k = a && a.dataset && a.dataset.keep, pos = k && a.selectionStart;
  renderHeader(ui.state); renderMain(ui.state, ui); renderProbes(ui.state); renderList(ui.state, ui); renderTask(ui.state, ui);
  const el = k && document.querySelector('[data-keep="' + k + '"]');
  if (el && el !== a) { el.focus(); if (typeof pos === 'number' && el.setSelectionRange) el.setSelectionRange(pos, pos); }
  const log = document.getElementById('log');
  if (log) log.scrollTop = log.scrollHeight;
  // 좁은 화면에서 단계 줄이 넘치면 고른 노드가 보이도록 가로로만 옮긴다(페이지는 움직이지 않음).
  const pipe = document.querySelector('.pipe'), sel = pipe && pipe.querySelector('.node.sel');
  if (sel) pipe.scrollLeft = sel.offsetLeft - (pipe.clientWidth - sel.offsetWidth) / 2;
}

async function refresh() {
  try {
    const s = await api('state');
    ui.state = s;
    if (!ui.selected && s.tasks[0]) ui.selected = s.tasks[0].taskId;
    const sig = JSON.stringify({ ...s, now: 0 });
    const live = document.getElementById('live');
    if (sig !== lastSig && lastSig) ui.changedAt = new Date().toLocaleTimeString();
    live.className = 'chip ok';
    live.textContent = '● 실시간' + (ui.changedAt ? ' · 마지막 변화 ' + ui.changedAt : '');
    if (document.getElementById('msg').textContent.startsWith('상태 조회 실패')) say(''); // 다시 연결되면 오류 문구를 지운다
    if (sig === lastSig) return;
    lastSig = sig;
    render();
  } catch (e) {
    document.getElementById('live').className = 'chip bad';
    document.getElementById('live').textContent = '○ 연결 끊김 — 1초마다 다시 시도';
    say('상태 조회 실패: ' + e.message + ' (서버 재시작 중이면 곧 다시 연결됩니다)', 'bad');
  }
}

async function pollLog() {
  const t = ui.state && ui.state.tasks.find((x) => x.taskId === ui.selected);
  const id = ui.logChoice || (t && t.exec && t.exec.execId);
  if (!id) return;
  if (id !== ui.log.exec) ui.log = { exec: id, next: 0, text: '' };
  try {
    const d = await api('execs/' + encodeURIComponent(id) + '/log?from=' + ui.log.next);
    if (!d.text) return;
    ui.log.text = (ui.log.text + d.text).slice(-60000);
    ui.log.next = d.next;
    const el = document.getElementById('log');
    if (el) { el.textContent = ui.log.text; el.scrollTop = el.scrollHeight; }
  } catch { /* 다음 주기에 다시 받는다 */ }
}

ui.rerender = render;
ui.refreshNow = refresh;
document.addEventListener('click', onClick);
document.addEventListener('input', onInput);
document.addEventListener('change', onInput);
document.addEventListener('toggle', onInput, true); // toggle은 버블링되지 않아 capture로 받는다
// 숨겨진 탭은 브라우저가 타이머를 늦추므로, 다시 보일 때 바로 확인한다.
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('focus', () => refresh());
initForm();
setInterval(async () => {
  if (busy) return;
  busy = true;
  try { await refresh(); await pollLog(); } finally { busy = false; }
}, 1000);
refresh().then(pollLog);

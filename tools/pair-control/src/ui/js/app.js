// 화면 시작점. 1초마다 상태를 받아 바뀌었을 때만 다시 그리고, 선택한 실행의 로그를 이어 받는다.
import { onClick, onInput } from './actions.js';
import { api, say, ui } from './core.js';
import { initForm } from './form.js';
import { logTarget, paintLog } from './logview.js';
import { renderHeader, renderList, renderMain, renderProbes } from './view-list.js';
import { renderTask } from './view-task.js';

let lastSig = '', busy = false;

function render() {
  if (!ui.state) return;
  // 다시 그려도 입력 중이던 칸의 포커스·커서를 지킨다(1초 갱신 때문에 입력이 끊기지 않게).
  const a = document.activeElement, k = a && a.dataset && a.dataset.keep, pos = k && a.selectionStart;
  const old = document.getElementById('log'), top = old ? old.scrollTop : 0; // 따라가기를 끈 사람의 스크롤 위치
  renderHeader(ui.state); renderMain(ui.state, ui); renderProbes(ui.state); renderList(ui.state, ui); renderTask(ui.state, ui);
  const el = k && document.querySelector('[data-keep="' + k + '"]');
  if (el && el !== a) { el.focus(); if (typeof pos === 'number' && el.setSelectionRange) el.setSelectionRange(pos, pos); }
  const log = document.getElementById('log');
  if (log) log.scrollTop = ui.keep.logFollow === false ? top : log.scrollHeight;
  // 좁은 화면에서 단계 줄이 넘치면 고른 노드가 보이도록 가로로만 옮긴다(페이지는 움직이지 않음).
  const pipe = document.querySelector('.pipe'), sel = pipe && pipe.querySelector('.node.sel');
  if (sel) pipe.scrollLeft = sel.offsetLeft - (pipe.clientWidth - sel.offsetWidth) / 2;
}

async function refresh() {
  try {
    const s = await api('state');
    ui.state = s;
    const first = s.tasks.find((x) => !x.archivedAt);
    if (!ui.selected && first) ui.selected = first.taskId;
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
  const g = t && logTarget(t, ui.shownStage, ui);
  if (!g) return;
  if (g.empty) { paintLog(g, ui); return; } // 아직 기록이 없는 단계: 안내문만(상태 줄은 갱신)
  if (g.id !== ui.log.id) ui.log = { id: g.id, next: 0, text: '', stamps: [] };
  if (ui.keep.logPaused) return paintLog(g, ui); // 일시정지: 새 출력은 받지 않고 경과만 갱신
  try {
    const d = await api(g.api + ui.log.next);
    if (d.text) appendLog(d.text, ui.log.next === 0);
    ui.log.next = d.next;
    paintLog(g, ui);
  } catch { /* 다음 주기에 다시 받는다 */ }
}

/** 받은 글을 붙이고 새로 시작된 줄에 받은 시각을 매긴다. 처음 열 때 이미 있던 줄은 시각을 비운다(실제 출력 시각을 모르므로). */
function appendLog(chunk, firstFetch) {
  const started = (s) => (s ? s.split('\n').length - (s.endsWith('\n') ? 1 : 0) : 0);
  const before = started(ui.log.text);
  ui.log.text += chunk;
  const d = new Date(), now = [d.getHours(), d.getMinutes(), d.getSeconds()].map((n) => String(n).padStart(2, '0')).join(':'); // HH:MM:SS(로케일 글자 길이에 흔들리지 않게)
  for (let i = before; i < started(ui.log.text); i++) ui.log.stamps[i] = firstFetch ? '' : now;
  while (ui.log.text.length > 200000) { // 너무 길면 앞쪽 줄부터 버린다(시각도 같이)
    ui.log.text = ui.log.text.slice(ui.log.text.indexOf('\n') + 1);
    ui.log.stamps.shift();
  }
}

/** 수동 모드 작업 폴더의 활동(새 커밋·변경 파일)을 3초마다 받아 바뀌었을 때만 다시 그린다. */
async function pollActivity() {
  const t = ui.state && ui.state.tasks.find((x) => x.taskId === ui.selected);
  if (!t || t.status !== 'manual_working' || Date.now() - ui.activityAt < 3000) return;
  ui.activityAt = Date.now();
  try {
    const a = await api('tasks/' + encodeURIComponent(t.taskId) + '/activity');
    const same = JSON.stringify({ ...a, at: 0 }) === JSON.stringify({ ...ui.activity[t.taskId], at: 0 });
    ui.activity[t.taskId] = a;
    if (!same) render();
  } catch { /* 다음 주기에 다시 받는다 */ }
}

/** 로그를 위로 올려 보면 따라가기를 끄고, 맨 아래로 내리면 다시 켠다(버튼 글자만 바꾸고 다시 그리지 않음). */
function onLogScroll(ev) {
  const el = ev.target;
  if (!el || el.id !== 'log') return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  if (atBottom === (ui.keep.logFollow !== false)) return;
  ui.keep.logFollow = atBottom;
  const b = document.getElementById('logFollowBtn');
  if (b) b.textContent = atBottom ? '따라가기 켜짐' : '따라가기 꺼짐';
}

ui.rerender = render;
ui.refreshNow = refresh;
document.addEventListener('click', onClick);
document.addEventListener('input', onInput);
document.addEventListener('change', onInput);
document.addEventListener('scroll', onLogScroll, true); // scroll도 버블링되지 않아 capture로 받는다
document.addEventListener('toggle', onInput, true); // toggle은 버블링되지 않아 capture로 받는다
// 숨겨진 탭은 브라우저가 타이머를 늦추므로, 다시 보일 때 바로 확인한다.
document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
window.addEventListener('focus', () => refresh());
initForm();
setInterval(async () => {
  if (busy) return;
  busy = true;
  try { await refresh(); await pollLog(); await pollActivity(); } finally { busy = false; }
}, 1000);
refresh().then(pollLog);

import { api, say, ui } from './core.js';

import { render } from './app-render.js';

let lastSig = '';

export async function refresh() {
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

/** 수동 모드 작업 폴더의 활동(새 커밋·변경 파일)을 3초마다 받아 바뀌었을 때만 다시 그린다. */
export async function pollActivity() {
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

import { api, ui } from './core.js';

import { logTarget, paintLog } from './logview.js';

import { splitLogChunk, appendLogRows, fmtLine } from './event-log.js';

export async function pollLog() {
  const t = ui.state && ui.state.tasks.find((x) => x.taskId === ui.selected);
  const g = t && logTarget(t, ui.shownStage, ui);
  if (!g) return;
  if (g.empty) { paintLog(g, ui); return; } // 아직 기록이 없는 단계: 안내문만(상태 줄은 갱신)
  if (g.id !== ui.log.id) ui.log = { id: g.id, next: 0, rows: [], pending: '' };
  if (ui.keep.logPaused) return paintLog(g, ui); // 일시정지: 새 출력은 받지 않고 경과만 갱신
  try {
    const d = await api(g.api + ui.log.next);
    const batch = splitLogChunk(ui.log, d.text || '', ui.log.next === 0, g.live);
    for (const raw of batch.raws) appendLogRows(ui.log, fmtLine(raw), batch.now);
    ui.log.next = d.next;
    paintLog(g, ui);
  } catch { /* 다음 주기에 다시 받는다 */ }
}

/** 로그를 위로 올려 보면 따라가기를 끄고, 맨 아래로 내리면 다시 켠다(버튼 글자만 바꾸고 다시 그리지 않음). */
export function onLogScroll(ev) {
  const el = ev.target;
  if (!el || el.id !== 'log') return;
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 24;
  if (atBottom === (ui.keep.logFollow !== false)) return;
  ui.keep.logFollow = atBottom;
  const b = document.getElementById('logFollowBtn');
  if (b) b.textContent = atBottom ? '따라가기 켜짐' : '따라가기 꺼짐';
}

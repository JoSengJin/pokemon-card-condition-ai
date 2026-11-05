import { B, esc } from './core.js';
import { logRows, paintLines } from './log-lines.js';
import { statText, footText } from './log-status.js';

export function renderLog(g, ui) {
  if (!g) return '';
  const follow = ui.keep.logFollow !== false, paused = !!ui.keep.logPaused, off = !!g.empty;
  const pick = off ? '<b class="small">로그</b>' : g.list.length > 1 ? '<select data-keep="logSel" aria-label="로그 선택">' + g.list.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === g.id ? ' selected' : '') + '>' + esc(x.label) + (x.live ? ' (실행 중)' : '') + '</option>').join('') + '</select>' : '<b class="small">' + esc(g.label) + '</b>';
  const rows = off ? [] : logRows(ui, g.id);
  const note = off ? g.empty : paused ? '(일시정지 중 — 새 출력을 받지 않습니다)' : ui.keep.logFind ? '(찾는 말이 든 줄이 없습니다)' : g.live ? '(아직 출력 없음 — 새 출력이 오면 여기에 나타납니다)' : '(출력 없음)';
  return '<div class="logbox"><div class="logbar">' + pick + '<span class="sp"></span>' +
    '<input class="logfind" data-keep="logFind" value="' + esc(ui.keep.logFind || '') + '" placeholder="찾기(일치하는 줄만)" aria-label="로그 찾기"' + (off ? ' disabled' : '') + '>' +
    B('logfollow', follow ? '따라가기 켜짐' : '따라가기 꺼짐', !off, '', ' id="logFollowBtn"') + B('logpause', paused ? '이어서 보기' : '일시정지', !off) +
    B('copy', '복사', !off, '', ' data-target="log" data-what="로그"') + '</div>' +
    '<pre id="log" tabindex="0"' + (rows.some((r) => r.t) ? '' : ' class="nots"') + '>' + (rows.length ? paintLines(rows) : esc(note)) + '</pre>' +
    '<div class="logfoot small muted"><span id="logFoot">' + footText(g, ui) + '</span><span>비밀값은 기록 전에 가려집니다 (sk-…, Bearer …)</span></div></div>';
}

export function paintLog(g, ui) {
  const pre = document.getElementById('log'), stat = document.getElementById('logStat'), foot = document.getElementById('logFoot');
  if (stat) stat.innerHTML = statText(g);
  if (foot) foot.textContent = footText(g, ui);
  if (!pre) return;
  const rows = logRows(ui, g.id);
  if (rows.length) pre.innerHTML = paintLines(rows); // 색 입힌 줄(복사는 textContent라 글자만 복사됨)
  pre.classList.toggle('nots', !rows.some((r) => r.t)); // 받은 시각이 한 줄도 없으면(지난 기록) 시각 칸을 없앤다
  if (ui.keep.logFollow !== false) pre.scrollTop = pre.scrollHeight;
}

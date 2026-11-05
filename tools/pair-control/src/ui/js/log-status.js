export const mmss = (sec) => String(Math.floor(sec / 60)).padStart(2, '0') + ':' + String(sec % 60).padStart(2, '0');

export function statText(g) {
  if (!g || g.empty) return '<span class="muted">○ 시작 전</span>';
  const sec = g.at ? Math.max(0, Math.round(((g.end && !g.live ? Date.parse(g.end) : Date.now()) - Date.parse(g.at)) / 1000)) : null;
  return (g.live ? '<span class="ok">● 실행 중</span>' : '<span class="muted">종료' + (g.code != null ? ' · 코드 ' + Number(g.code) : '') + '</span>') +
    (g.pid ? ' · PID ' + Number(g.pid) : '') + (sec === null ? '' : ' · ' + mmss(sec) + ' 경과');
}

export function footText(g, ui) {
  const n = g && !g.empty && ui.log.id === g.id ? ui.log.rows.length : 0;
  return n + '줄 · 새 출력이 오면 ' + (ui.keep.logFollow !== false ? '자동으로 아래로 이동' : '그 자리에 머무름') + (ui.keep.logPaused ? ' · 일시정지 중' : '');
}

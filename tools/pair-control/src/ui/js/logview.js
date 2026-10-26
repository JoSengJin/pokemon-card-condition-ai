// 단계 패널 안의 실시간 로그 창. 어떤 로그를 보여 줄지(logTarget)와 그리는 방법(renderLog·paintLog)만 안다.
// 로그를 받아 오는 일은 app.js의 pollLog가 하고, 받은 글은 ui.log에 쌓인다.
import { B, esc } from './core.js';

const enc = encodeURIComponent;
const LIVE = ['running', 'cancelling'];
const item = (id, label, api, live, code, at, end, pid) => ({ id, label, api, live, code, at, end, pid });

/** 이 단계에서 보여 줄 로그 목록과 지금 고른 것. 로그가 없는 단계는 null. api는 from=까지 적힌 조회 경로 앞부분. */
export function logTarget(t, key, ui) {
  const e = t.exec, r = t.review;
  const list = key === 'build' && e ? [item(e.execId, '에이전트 출력', 'execs/' + enc(e.execId) + '/log?from=', LIVE.includes(e.status), e.exitCode, e.startedAt, e.endedAt, e.pid)]
    : key === 'tests' ? ((t.verification && t.verification.items) || []).filter((i) => i.execId).map((i) => item(i.execId, i.name, 'execs/' + enc(i.execId) + '/log?from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt))
    : key === 'review' && r && r.execId ? [item(r.execId, '리뷰 출력', 'execs/' + enc(r.execId) + '/log?from=', r.status === 'running', null, r.startedAt, r.endedAt)]
    : key === 'postcheck' ? (((t.integration && t.integration.postChecks) || []).filter((i) => i.logPath).map((i) => item('post:' + i.id, i.name, 'tasks/' + enc(t.taskId) + '/post-log?check=' + enc(i.id) + '&from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt)))
    : [];
  if (!list.length) return null;
  const sel = list.find((x) => x.id === ui.keep.logSel) || list.find((x) => x.live) || list[list.length - 1];
  return { ...sel, list };
}

/** 화면에 보일 글: 찾기 칸에 적은 말이 있으면 그 말이 든 줄만. */
export function logText(ui, id) {
  const text = ui.log.id === id ? ui.log.text : '';
  const q = String(ui.keep.logFind || '').trim().toLowerCase();
  return q ? text.split('\n').filter((l) => l.toLowerCase().includes(q)).join('\n') : text;
}

/** 상태 줄(실행 중/종료·코드·PID·줄 수·경과). 1초마다 pollLog가 이 글만 갈아 끼운다. 숫자만 쓰므로 esc를 부르지 않는다(호출 깊이). */
export function statText(g, ui) {
  const raw = ui.log.id === g.id ? ui.log.text : '';
  const sec = g.at ? Math.max(0, Math.round(((g.end && !g.live ? Date.parse(g.end) : Date.now()) - Date.parse(g.at)) / 1000)) : null;
  const el = sec === null ? '' : ' · ' + String(Math.floor(sec / 60)).padStart(2, '0') + ':' + String(sec % 60).padStart(2, '0') + ' 경과';
  return (g.live ? '<span class="ok">● 실행 중</span>' : '<span class="muted">종료' + (g.code != null ? ' · 코드 ' + Number(g.code) : '') + '</span>') +
    (g.pid ? ' · PID ' + Number(g.pid) : '') + ' · ' + (raw ? raw.split('\n').length - (raw.endsWith('\n') ? 1 : 0) : 0) + '줄' + el;
}

export function renderLog(g, ui) {
  if (!g) return '';
  const follow = ui.keep.logFollow !== false, paused = !!ui.keep.logPaused;
  const pick = g.list.length > 1 ? '<select data-keep="logSel" aria-label="로그 선택">' + g.list.map((x) => '<option value="' + esc(x.id) + '"' + (x.id === g.id ? ' selected' : '') + '>' + esc(x.label) + (x.live ? ' (실행 중)' : '') + '</option>').join('') + '</select>' : '<b class="small">' + esc(g.label) + '</b>';
  const text = logText(ui, g.id);
  return '<h4>로그</h4><div class="logbar">' + pick + '<span class="small" id="logStat">' + statText(g, ui) + '</span><span class="sp"></span>' +
    '<input class="logfind" data-keep="logFind" value="' + esc(ui.keep.logFind || '') + '" placeholder="찾기(일치하는 줄만)" aria-label="로그 찾기">' +
    B('logfollow', follow ? '따라가기 켜짐' : '따라가기 꺼짐', true, '', ' id="logFollowBtn"') + B('logpause', paused ? '이어서 보기' : '일시정지', true) +
    B('copy', '복사', true, '', ' data-target="log" data-what="로그"') + '</div>' +
    '<pre id="log" tabindex="0">' + esc(text || (paused ? '(일시정지 중 — 새 출력을 받지 않습니다)' : g.live ? '(아직 출력 없음 — 새 출력이 오면 여기에 나타납니다)' : '(출력 없음)')) + '</pre>';
}

/** 다시 그리지 않고 로그 글과 상태 줄만 제자리에서 갱신한다(스크롤·입력 포커스 유지). */
export function paintLog(g, ui) {
  const pre = document.getElementById('log'), stat = document.getElementById('logStat');
  if (stat) stat.innerHTML = statText(g, ui);
  if (!pre) return;
  const text = logText(ui, g.id);
  if (text) pre.textContent = text;
  if (ui.keep.logFollow !== false) pre.scrollTop = pre.scrollHeight;
}

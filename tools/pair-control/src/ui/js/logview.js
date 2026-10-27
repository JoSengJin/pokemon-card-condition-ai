// 단계 패널 안의 실시간 로그 창(패널 제목 바로 아래). 어떤 로그를 보여 줄지(logTarget)와 그리는 방법만 안다.
// 로그를 받아 오는 일은 app.js의 pollLog가 하고, 받은 글과 줄별 수신 시각은 ui.log에 쌓인다.
import { B, esc } from './core.js';

const enc = encodeURIComponent;
const LIVE = ['running', 'cancelling'];
/** 로그를 보여 주는 단계. 이 단계에서는 로그가 아직 없어도 창을 보여 준다(시작 전 안내). */
export const LOG_STAGES = ['build', 'tests', 'review', 'postcheck'];
const EMPTY = {
  build: '(아직 시작 전 — 시작하면 에이전트 출력이 여기에 흐릅니다)',
  tests: '(아직 실행 전 — "작업 테스트 실행"을 누르면 명령별 출력이 여기에 흐릅니다)',
  review: '(리뷰 전 — 리뷰를 실행하면 리뷰 출력이 여기에 흐릅니다)',
  postcheck: '(통합 전 — 통합 후 검사가 실행되면 출력이 여기에 흐릅니다)',
};

/** 이 단계에서 보여 줄 로그 목록과 지금 고른 것. 로그 단계가 아니면 null. 아직 기록이 없으면 {empty: 안내문}. api는 from=까지 적힌 조회 경로 앞부분. */
export function logTarget(t, key, ui) {
  if (!LOG_STAGES.includes(key)) return null;
  const e = t.exec, r = t.review, g = (id, label, api, live, code, at, end, pid) => ({ id, label, api, live, code, at, end, pid });
  const list = key === 'build' && e ? [g(e.execId, '에이전트 출력', 'execs/' + enc(e.execId) + '/log?from=', LIVE.includes(e.status), e.exitCode, e.startedAt, e.endedAt, e.pid)]
    : key === 'tests' ? ((t.verification && t.verification.items) || []).filter((i) => i.execId).map((i) => g(i.execId, i.name, 'execs/' + enc(i.execId) + '/log?from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt))
    : key === 'review' && r && r.execId ? [g(r.execId, '리뷰 출력', 'execs/' + enc(r.execId) + '/log?from=', r.status === 'running', null, r.startedAt, r.endedAt)]
    : key === 'postcheck' ? (((t.integration && t.integration.postChecks) || []).filter((i) => i.logPath).map((i) => g('post:' + i.id, i.name, 'tasks/' + enc(t.taskId) + '/post-log?check=' + enc(i.id) + '&from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt)))
    : [];
  if (!list.length) {
    const manual = key === 'build' && t.mode === 'manual';
    return { empty: manual ? '(수동 모드는 에이전트 세션의 출력을 도구가 받지 못합니다 — 대신 아래 "작업 폴더 활동"을 보여 줍니다)' : key === 'postcheck' && t.integration && t.integration.postStatus === 'not_run' ? '(계약에 통합 후 검사가 없어 실행하지 않았습니다)' : EMPTY[key], list: [], live: false };
  }
  const sel = list.find((x) => x.id === ui.keep.logSel) || list.find((x) => x.live) || list[list.length - 1];
  return { ...sel, list };
}

/** 화면에 보일 줄들 [{t: 받은 시각, s: 글}]. 찾기 칸에 적은 말이 있으면 그 말이 든 줄만. */
export function logRows(ui, id) {
  if (ui.log.id !== id) return [];
  const lines = ui.log.text.split('\n');
  if (lines[lines.length - 1] === '') lines.pop();
  const q = String(ui.keep.logFind || '').trim().toLowerCase();
  return lines.map((s, i) => ({ t: ui.log.stamps[i] || '', s })).filter((r) => !q || r.s.toLowerCase().includes(q));
}

const HTML = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
const KIND = [[/^\s*\$ /, 'info'], [/(error|exception|traceback|failed|fatal|실패|오류|에러)/i, 'bad'], [/(warn|경고|주의)/i, 'warn'], [/^\s*(ok|ran \d+ tests?.*|.*\b\d+ passed\b.*|\[[\w./-]+ [0-9a-f]{7,}\].*)\s*$/i, 'ok']];

/**
 * 줄마다 받은 시각(CSS ::before라 복사에는 안 들어감)을 붙이고 종류를 가볍게 구분해 색을 입힌다:
 * `$ ` 명령은 파랑, 오류·실패는 빨강, 경고는 주황, 테스트 통과 요약·커밋 결과(`[브랜치 해시]`)는 초록. 글자 패턴만 보는 표시용이라 판정에는 쓰이지 않는다.
 * 호출 깊이 때문에 esc 대신 여기서 직접 이스케이프한다.
 */
export function paintLines(rows) {
  return rows.map((r) => {
    const safe = r.s.replace(/[&<>"]/g, (c) => HTML[c]), kind = KIND.find((k) => k[0].test(r.s));
    return '<span class="ln" data-t="' + r.t + '">' + (kind ? '<span class="' + kind[1] + '">' + safe + '</span>' : safe) + '</span>';
  }).join('\n');
}

const mmss = (sec) => String(Math.floor(sec / 60)).padStart(2, '0') + ':' + String(sec % 60).padStart(2, '0');

/** 제목 줄 옆 상태(실행 중/종료·코드·PID·경과). 1초마다 pollLog가 이 글만 갈아 끼운다. 숫자만 쓰므로 esc를 부르지 않는다(호출 깊이). */
export function statText(g) {
  if (!g || g.empty) return '<span class="muted">○ 시작 전</span>';
  const sec = g.at ? Math.max(0, Math.round(((g.end && !g.live ? Date.parse(g.end) : Date.now()) - Date.parse(g.at)) / 1000)) : null;
  return (g.live ? '<span class="ok">● 실행 중</span>' : '<span class="muted">종료' + (g.code != null ? ' · 코드 ' + Number(g.code) : '') + '</span>') +
    (g.pid ? ' · PID ' + Number(g.pid) : '') + (sec === null ? '' : ' · ' + mmss(sec) + ' 경과');
}

/** 로그 창 아래 줄: 줄 수와 따라가기 안내. */
export function footText(g, ui) {
  const n = g && !g.empty && ui.log.id === g.id ? ui.log.text.split('\n').length - (ui.log.text.endsWith('\n') || !ui.log.text ? 1 : 0) : 0;
  return n + '줄 · 새 출력이 오면 ' + (ui.keep.logFollow !== false ? '자동으로 아래로 이동' : '그 자리에 머무름') + (ui.keep.logPaused ? ' · 일시정지 중' : '');
}

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
    '<pre id="log" tabindex="0">' + (rows.length ? paintLines(rows) : esc(note)) + '</pre>' +
    '<div class="logfoot small muted"><span id="logFoot">' + footText(g, ui) + '</span><span>비밀값은 기록 전에 가려집니다 (sk-…, Bearer …)</span></div></div>';
}

/** 다시 그리지 않고 로그 글·상태·줄 수만 제자리에서 갱신한다(스크롤·입력 포커스 유지). */
export function paintLog(g, ui) {
  const pre = document.getElementById('log'), stat = document.getElementById('logStat'), foot = document.getElementById('logFoot');
  if (stat) stat.innerHTML = statText(g);
  if (foot) foot.textContent = footText(g, ui);
  if (!pre) return;
  const rows = logRows(ui, g.id);
  if (rows.length) pre.innerHTML = paintLines(rows); // 색 입힌 줄(복사는 textContent라 글자만 복사됨)
  if (ui.keep.logFollow !== false) pre.scrollTop = pre.scrollHeight;
}

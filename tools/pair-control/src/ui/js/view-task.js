// 선택한 작업의 파이프라인 화면: 지금 할 일 → 단계 노드 → 고른 단계의 상세 → 실행 정보·로그.
import { B, esc } from './core.js';
import { panelBuild, panelGit, panelPrepare, panelReview, panelTests } from './panels-work.js';
import { panelApprove, panelHandoff, panelIntegrate, panelPostcheck, panelPush, pushRecords } from './panels-release.js';
import { currentKey, stagesOf } from './stages.js';

const PANELS = { prepare: panelPrepare, build: panelBuild, gitcheck: panelGit, tests: panelTests, review: panelReview, handoff: panelHandoff, approve: panelApprove, integrate: panelIntegrate, postcheck: panelPostcheck, push: panelPush };
const ICON = { done: '✓', active: '', action: '!', failed: '✗', warn: '!', todo: '', skipped: '–' };
const WORD = { done: '완료', active: '진행 중', action: '할 일', failed: '실패', warn: '주의', todo: '대기', skipped: '건너뜀' };
const WHO = { user: '사용자', implementer: '구현 에이전트', main: '메인 에이전트', tool: '도구' };

export function renderTask(state, ui) {
  const box = document.getElementById('detail');
  const t = state.tasks.find((x) => x.taskId === ui.selected);
  if (!t) { box.innerHTML = '<p class="muted empty">왼쪽 목록에서 작업을 고르거나 위에서 새 작업을 만드세요.</p>'; return; }
  const stages = stagesOf(t, state.push, state.main && state.main.agent);
  const cur = currentKey(stages);
  const key = ui.stage[t.taskId] && PANELS[ui.stage[t.taskId]] ? ui.stage[t.taskId] : cur;
  const now = stages.find((s) => s.key === cur), st = stages.find((s) => s.key === key);
  const p = now.primary, u = t.turn;
  const idx = stages.indexOf(st) + 1;
  box.innerHTML =
    '<div class="thead"><div><h2>' + esc(t.taskId) + '</h2><div class="goal">' + esc(t.goal) + '</div></div>' +
      '<div class="meta"><span class="chip">' + esc(t.agent) + ' · ' + esc({ manual: '수동', real: '실제 CLI', mock: '연습' }[t.mode] || t.mode) + '</span> <span class="mono small">' + esc(t.branch) + '</span></div></div>' +
    (t.mismatch ? '<p class="bad small">⚠ Mastra 실행 기록과 실제 상태 불일치: ' + esc(t.mismatch) + '</p>' : '') +
    '<div class="now s-' + now.status + '"><div><div class="nowLabel">지금 단계</div><b>' + esc(now.label) + '</b> — ' + esc(now.text) +
      (u ? '<div class="small">차례: <b>' + esc(u.agent ? WHO[u.who] + '(' + u.agent + ')' : WHO[u.who]) + '</b> · ' + esc(u.next) + '</div>' : '') + '</div>' +
      (p ? B(p.act, p.label, true, 'primary', ' data-stage="' + cur + '"' + (p.id ? ' data-id="' + esc(p.id) + '"' : '')) : '') + '</div>' +
    pipelineBar(stages, key, cur) +
    '<section class="stagePanel s-' + st.status + '"><h3><span class="num">' + idx + '</span> ' + esc(st.label) + ' <span class="pill s-' + st.status + '">' + WORD[st.status] + '</span>' +
      (key !== cur ? ' <button type="button" class="link small" data-act="stage" data-stage="' + cur + '">지금 단계로</button>' : '') + '</h3>' +
      '<p class="desc">' + esc(st.desc) + '</p><div class="small muted">담당: ' + esc(st.who) + ' · 상태: ' + esc(st.text) + '</div>' +
      '<div class="panelBody">' + PANELS[key](t, ui) + (key === 'push' && state.push ? '<h4>푸시 기록</h4>' + pushRecords(state.push.records) : '') + '</div></section>' +
    runInfo(t, ui);
}

/** 단계 노드 줄. 노드를 누르면 그 단계의 상세가 아래에 열린다(작업 상태는 바꾸지 않음). */
export function pipelineBar(stages, key, cur) {
  return '<ol class="pipe" aria-label="작업 단계">' + stages.map((s, i) =>
    '<li class="node s-' + s.status + (s.key === key ? ' sel' : '') + (s.key === cur ? ' cur' : '') + '">' +
      '<button type="button" data-act="stage" data-stage="' + s.key + '" title="' + esc(s.desc) + '" aria-current="' + (s.key === key ? 'step' : 'false') + '">' +
      '<span class="dot">' + (ICON[s.status] || '') + '</span><span class="nl">' + (i + 1) + '. ' + esc(s.label) + '</span><span class="nt">' + esc(s.text) + '</span></button></li>').join('') + '</ol>';
}

/** 접힌 실행 정보: Mastra 실행·프로세스·계약·로그. 사람이 평소에 볼 필요는 없는 값들. */
export function runInfo(t, ui) {
  const e = t.exec, m = t.mastra;
  const open = ui.keep.infoOpen ? ' open' : '';
  return '<details class="info" data-keep="infoOpen"' + open + '><summary>실행 정보 · 계약 · 로그</summary><div class="kv small">' +
    '<div>목표</div><div>' + esc(t.goal) + '</div>' +
    '<div>완료 조건</div><div>' + ((t.doneCriteria || []).map(esc).join('<br>') || '<span class="muted">(지정 없음)</span>') + '</div>' +
    '<div>계약 파일</div><div class="mono">' + esc(t.contractPath + ' @ ' + (t.contractSha || '').slice(0, 12)) + '</div>' +
    '<div>Mastra 실행</div><div class="mono">' + esc((t.runId || '—') + (m ? ' · ' + m.status + (m.suspendedStep ? ' @ ' + m.suspendedStep : '') : '')) + '</div>' +
    '<div>실행 ID</div><div class="mono">' + esc(e ? e.execId : '—') + '</div><div>실행 권한</div><div>' + esc(t.permission || '—') + '</div></div>' +
    '<h4>로그 <span class="muted small">' + (ui.logChoice ? '선택한 검사·리뷰' : '에이전트') + '</span>' +
    (ui.logChoice ? ' <button type="button" class="link" data-act="logagent">에이전트 로그로</button>' : '') + '</h4>' +
    '<pre id="log">' + esc(ui.log.text || '(없음)') + '</pre></details>';
}

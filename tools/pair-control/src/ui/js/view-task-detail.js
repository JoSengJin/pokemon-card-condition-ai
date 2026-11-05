import { B, esc } from './core.js';
import { panelBuild, panelGit, panelPrepare, panelReview, panelTests } from './panels-work.js';
import { panelApprove, panelHandoff, panelIntegrate, panelPostcheck, panelPush, pushRecords } from './panels-release.js';
import { logTarget, renderLog, statText } from './logview.js';
import { currentKey, stagesOf } from './stages.js';
import { pipelineBar, stageChanges, logStageLinks } from './view-stage-bar.js';
import { runInfo } from './view-run-info.js';

export const PANELS = { prepare: panelPrepare, build: panelBuild, gitcheck: panelGit, tests: panelTests, review: panelReview, handoff: panelHandoff, approve: panelApprove, integrate: panelIntegrate, postcheck: panelPostcheck, push: panelPush };

export const WORD = { done: '완료', active: '진행 중', action: '할 일', failed: '실패', warn: '주의', todo: '대기', skipped: '건너뜀' };

export const DISCARDABLE = ['review_pending', 'approved', 'integration_refused', 'integration_blocked', 'assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export const ARCHIVABLE = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned', 'integrated', 'integrated_check_failed'];

export const WHO = { user: '사용자', implementer: '구현 에이전트', main: '메인 에이전트', tool: '도구' };

export function renderTask(state, ui) {
  const box = document.getElementById('detail');
  const t = state.tasks.find((x) => x.taskId === ui.selected);
  if (!t) { box.innerHTML = '<p class="muted empty">왼쪽 목록에서 작업을 고르거나 위에서 새 작업을 만드세요.</p>'; return; }
  const stages = stagesOf(t, state.push, state.main && state.main.agent);
  const cur = currentKey(stages);
  const key = ui.stage[t.taskId] && PANELS[ui.stage[t.taskId]] ? ui.stage[t.taskId] : cur;
  ui.shownStage = key; // pollLog가 지금 보이는 단계의 로그를 받아 오도록
  const now = stages.find((s) => s.key === cur), st = stages.find((s) => s.key === key);
  const p = now.primary, u = t.turn;
  const prev = ui.seen[t.taskId];
  const { changed, seen } = stageChanges(stages, prev);
  ui.seen[t.taskId] = seen;
  const idx = stages.indexOf(st) + 1;
  const lg = logTarget(t, key, ui); // 로그 단계면 패널 제목 바로 아래에 로그 창
  box.innerHTML =
    '<div class="thead"><div><h2>' + esc(t.taskId) + '</h2><div class="goal">' + esc(t.goal) + '</div></div>' +
      '<div class="meta"><span class="chip">' + esc(t.agent) + ' · ' + esc({ manual: '수동', real: '실제 CLI', mock: '연습' }[t.mode] || t.mode) + '</span> <span class="mono small">' + esc(t.branch) + '</span>' +
      (t.archivedAt ? '<span class="chip">보관됨</span>' + B('unarchive', '보관 해제', true, 'link') : B('archive', '보관', ARCHIVABLE.includes(t.status), 'link', ' title="끝났거나 시작 전인 작업만 목록에서 숨깁니다(기록은 남음)"') + B('discard', '폐기', DISCARDABLE.includes(t.status), 'link', ' title="필요 없는 작업을 사유와 함께 버립니다. 결정이 남은 작업은 거절로 처리하고 보관함으로 보냅니다(브랜치·작업 폴더는 지우지 않음)"')) + '</div></div>' +
    (t.mismatch ? '<p class="bad small">⚠ Mastra 실행 기록과 실제 상태 불일치: ' + esc(t.mismatch) + '</p>' : '') +
    '<div class="now s-' + now.status + '"><div><div class="nowLabel">지금 단계</div><b>' + esc(now.label) + '</b> — ' + esc(now.text) +
      (u ? '<div class="small">차례: <b>' + esc(u.agent ? WHO[u.who] + '(' + u.agent + ')' : WHO[u.who]) + '</b> · ' + esc(u.next) + '</div>' : '') + '</div>' +
      (p ? B(p.act, p.label, true, 'primary', ' data-stage="' + cur + '"' + (p.id ? ' data-id="' + esc(p.id) + '"' : '')) : '') + '</div>' +
    pipelineBar(stages, key, cur, changed) +
    '<section class="stagePanel s-' + st.status + '"><h3><span class="num">' + idx + '</span> ' + esc(st.label) + ' <span class="pill s-' + st.status + '">' + WORD[st.status] + '</span>' +
      (lg ? ' <span class="small muted" id="logStat">' + statText(lg) + '</span>' : '') +
      (key !== cur ? ' <button type="button" class="link small" data-act="stage" data-stage="' + cur + '">지금 단계로</button>' : '') + '</h3>' + renderLog(lg, ui) +
      (lg ? '' : '<div class="small muted logHint">실행 로그는 ' + logStageLinks(stages) + ' 단계에서 볼 수 있습니다(누르면 그 단계로 이동).</div>') +
      '<p class="desc">' + esc(st.desc) + '</p><div class="small muted">담당: ' + esc(st.who) + ' · 상태: ' + esc(st.text) + '</div>' +
      '<div class="panelBody">' + PANELS[key](t, ui) + (key === 'push' && state.push ? '<h4>푸시 기록</h4>' + pushRecords(state.push.records) : '') + '</div></section>' +
    runInfo(t, ui);
}

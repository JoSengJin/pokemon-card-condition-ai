import { currentKey, stagesOf } from './stages.js';

import { taskFinished, taskCard, miniPipeline } from './view-task-card.js';
import { archiveList } from './view-archive.js';

export function renderList(state, ui) {
  const el = document.getElementById('list');
  const archived = state.tasks.filter((t) => t.archivedAt);
  // 서버의 일괄 보관(archiveFinished)과 같은 기준: 거절·결과 불명 확정, 통합되고 원격 반영까지 확인된 작업
  const pushed = new Set(((state.push && state.push.records) || []).filter((r) => r.status === 'pushed_verified').flatMap((r) => r.tasks));
  const open = state.tasks.filter((t) => !t.archivedAt);
  const nFin = open.filter((t) => taskFinished(t, pushed)).length;
  const cards = [];
  for (const task of open) {
    const stages = stagesOf(task, state.push, state.main && state.main.agent), key = currentKey(stages);
    let current;
    for (const stage of stages) if (stage.key === key) { current = stage; break; }
    cards.push(taskCard(task, ui, pushed, current, miniPipeline(stages)));
  }
  el.innerHTML = (nFin ? '<div class="small"><button type="button" data-act="archivefin">끝난 작업 ' + nFin + '개 보관</button> <span class="muted">거절·결과 불명 확정·푸시 확인된 작업(기록은 남음)</span></div>' : '') + cards.join('') || '<p class="muted small">진행 중인 작업이 없습니다. 위의 "새 작업 만들기"로 시작하세요.</p>';
  el.innerHTML += archiveList(archived, ui);
}

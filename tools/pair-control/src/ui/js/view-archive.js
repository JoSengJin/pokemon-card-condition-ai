import { esc } from './core.js';

import { STATUS } from './view-status.js';

export function archiveList(archived, ui) {
  return !archived.length ? '' : '<details class="archive" data-keep="archOpen"' + (ui.keep.archOpen ? ' open' : '') + '><summary class="small muted">보관된 작업 ' + archived.length + '개</summary>' +
    archived.map((t) => '<div class="archRow' + (t.taskId === ui.selected ? ' sel' : '') + '"><button type="button" class="link" data-act="select" data-id="' + esc(t.taskId) + '">' + esc(t.taskId) + '</button> <span class="small muted">' + esc((STATUS[t.status] || [t.status])[0] + ' · ' + t.goal) + '</span>' + (t.discard ? ' <span class="small warn">폐기: ' + esc(t.discard.reason) + '</span>' : '') +
      ' <button type="button" class="small" data-act="unarchive" data-task="' + esc(t.taskId) + '">보관 해제</button></div>').join('') + '</details>';
}

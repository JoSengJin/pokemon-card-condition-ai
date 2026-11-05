import { esc, lbl } from './core.js';

import { STATUS } from './view-status.js';

export function miniPipeline(stages) {
  const nodes = [];
  for (const stage of stages) nodes.push('<i class="s-' + stage.status + '" title="' + esc(stage.label + ': ' + stage.text) + '"></i>');
  return '<div class="mini" aria-hidden="true">' + nodes.join('') + '</div>';
}

export function taskCard(t, ui, pushed, cur, pipeline) {
    const s = STATUS[t.status] || [t.status, 'muted'];
    const mark = cur.key + ':' + cur.status, was = ui.seen['card:' + t.taskId];
    ui.seen['card:' + t.taskId] = mark;
    return '<button type="button" class="card' + (t.taskId === ui.selected ? ' sel' : '') + (was && was !== mark ? ' changed' : '') + ' s-' + cur.status + '" data-act="select" data-id="' + esc(t.taskId) + '">' +
      '<div class="cardTop"><span class="mono">' + esc(t.taskId) + '</span>' + lbl(esc(s[0]), s[1]) + '</div>' +
      '<div class="cardGoal">' + esc(t.goal) + '</div>' + pipeline +
      '<div class="small"><span class="muted">' + esc(t.agent) + ' · 지금</span> <b>' + esc(cur.label) + '</b> <span class="muted">' + esc(cur.text) + '</span></div>' +
      (!taskFinished(t, pushed) && t.status !== 'integrated' && idleDays(t) >= 1 ? '<div class="small warn">' + idleDays(t) + '일째 변화 없음 — 필요 없으면 열어서 "폐기"</div>' : '') + '</button>';

}

export function taskFinished(t, pushed) { return ['rejected', 'abandoned'].includes(t.status) || (t.status === 'integrated' && pushed.has(t.taskId)); }

export function idleDays(t) { return Math.floor((Date.now() - Date.parse(t.updatedAt)) / 86400000); }

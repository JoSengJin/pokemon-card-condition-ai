import { esc } from './core.js';

export const ICON = { done: '✓', active: '', action: '!', failed: '✗', warn: '!', todo: '', skipped: '–' };

export function pipelineBar(stages, key, cur, changed) {
  const rows = [];
  for (const [i, s] of stages.entries()) {
    rows.push(
    '<li class="node s-' + s.status + (s.key === key ? ' sel' : '') + (s.key === cur ? ' cur' : '') + (changed.includes(s.key) ? ' changed' : '') + '">' +
      '<button type="button" data-act="stage" data-stage="' + s.key + '" title="' + esc(s.desc) + '" aria-current="' + (s.key === key ? 'step' : 'false') + '">' +
      '<span class="dot">' + (ICON[s.status] || '') + '</span><span class="nl">' + (i + 1) + '. ' + esc(s.label) + '</span><span class="nt">' + esc(s.text) + '</span></button></li>');
  }
  return '<ol class="pipe" aria-label="작업 단계">' + rows.join('') + '</ol>';
}

export function stageChanges(stages, prev) {
  const changed = [], seen = {};
  for (const stage of stages) {
    if (prev && prev[stage.key] !== stage.status) changed.push(stage.key);
    seen[stage.key] = stage.status;
  }
  return { changed, seen };
}

export function logStageLinks(stages) {
  const links = [];
  for (const key of ['build', 'tests', 'review', 'postcheck']) {
    const index = stages.findIndex((stage) => stage.key === key), stage = stages[index];
    links.push('<button type="button" class="link" data-act="stage" data-stage="' + key + '">' + (index + 1) + '. ' + esc(stage.label) + '</button>');
  }
  return links.join(' · ');
}

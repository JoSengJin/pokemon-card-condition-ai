import { esc } from './core.js';

export const ICON = { done: '✓', active: '', action: '!', failed: '✗', warn: '!', todo: '', skipped: '–' };

export function pipelineBar(stages, key, cur, changed) {
  return '<ol class="pipe" aria-label="작업 단계">' + stages.map((s, i) =>
    '<li class="node s-' + s.status + (s.key === key ? ' sel' : '') + (s.key === cur ? ' cur' : '') + (changed.includes(s.key) ? ' changed' : '') + '">' +
      '<button type="button" data-act="stage" data-stage="' + s.key + '" title="' + esc(s.desc) + '" aria-current="' + (s.key === key ? 'step' : 'false') + '">' +
      '<span class="dot">' + (ICON[s.status] || '') + '</span><span class="nl">' + (i + 1) + '. ' + esc(s.label) + '</span><span class="nt">' + esc(s.text) + '</span></button></li>').join('') + '</ol>';
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
  return ['build', 'tests', 'review', 'postcheck'].map((k) => '<button type="button" class="link" data-act="stage" data-stage="' + k + '">' + (stages.findIndex((x) => x.key === k) + 1) + '. ' + esc(stages.find((x) => x.key === k).label) + '</button>').join(' · ');
}

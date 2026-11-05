import { ui } from './core.js';

import { renderHeader, renderList, renderMain, renderProbes } from './view-list.js';

import { renderTask } from './view-task.js';

import { renderMainRuntime } from './view-list.js';
import { renderPipeline } from './view-pipeline.js';

export function render() {
  if (!ui.state) return;
  // 다시 그려도 입력 중이던 칸의 포커스·커서를 지킨다(1초 갱신 때문에 입력이 끊기지 않게).
  const a = document.activeElement, k = a && a.dataset && a.dataset.keep, pos = k && a.selectionStart;
  const old = document.getElementById('log'), top = old ? old.scrollTop : 0; // 따라가기를 끈 사람의 스크롤 위치
  renderHeader(ui.state); renderMain(ui.state, ui); renderMainRuntime(ui.state); renderPipeline(ui.state.mainRuntime && ui.state.mainRuntime.pipeline); renderProbes(ui.state); renderList(ui.state, ui); renderTask(ui.state, ui);
  const el = k && document.querySelector('[data-keep="' + k + '"]');
  if (el && el !== a) { el.focus(); if (typeof pos === 'number' && el.setSelectionRange) el.setSelectionRange(pos, pos); }
  const log = document.getElementById('log');
  if (log) log.scrollTop = ui.keep.logFollow === false ? top : log.scrollHeight;
  // 좁은 화면에서 단계 줄이 넘치면 고른 노드가 보이도록 가로로만 옮긴다(페이지는 움직이지 않음).
  const pipe = document.querySelector('.pipe'), sel = pipe && pipe.querySelector('.node.sel');
  if (sel) pipe.scrollLeft = sel.offsetLeft - (pipe.clientWidth - sel.offsetWidth) / 2;
}

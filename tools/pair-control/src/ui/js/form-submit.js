import { api, say, ui } from './core.js';

import { renderSpecs, resetSpecs } from './form-specs.js';
import { formBody } from './form-body.js';
import { updatePlan } from './form-plan.js';

export async function onSubmit(ev) {
  ev.preventDefault();
  document.getElementById('prepareBtn').disabled = true;
  say('준비·배정 요청 중…', 'muted');
  try {
    const d = await api('tasks', formBody());
    say('준비 완료: ' + d.detail + ' — 아래 파이프라인에서 "작업 시작"을 누르세요', 'ok');
    ui.selected = d.taskId;
    document.getElementById('assign').reset(); resetSpecs(); renderSpecs();
  } catch (e) { say('준비·배정 실패: ' + e.message, 'bad'); }
  updatePlan();
  setTimeout(ui.refreshNow, 0);
}

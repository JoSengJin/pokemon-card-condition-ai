import { ui } from './core.js';
import { onContractClick } from './form-contract.js';
import { onScopeClick } from './form-scope.js';
import { onSpecClick, onSpecInput, renderSpecs, resetSpecs } from './form-specs.js';
import { schedulePlan, updatePlan } from './form-plan.js';
import { onSubmit } from './form-submit.js';
import { loadProgress, applyDraft } from './form-progress.js';

export function initForm() {
  const f = document.getElementById('assign');
  f.addEventListener('input', (ev) => { onSpecInput(ev.target); schedulePlan(); });
  f.addEventListener('change', () => { if (ui.state) ui.rerender(); schedulePlan(); });
  f.addEventListener('click', (ev) => { if (onSpecClick(ev.target.closest('[data-spec]'))) schedulePlan(); });
  f.addEventListener('click', onScopeClick);
  f.addEventListener('click', onContractClick);
  f.addEventListener('submit', onSubmit);
  document.getElementById('progSel').addEventListener('change', applyDraft);
  resetSpecs(); renderSpecs(); updatePlan(); loadProgress();
}

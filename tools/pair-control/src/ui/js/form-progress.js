import { api, esc } from './core.js';

import { schedulePlan } from './form-plan.js';

export async function loadProgress() {
  const sel = document.getElementById('progSel'), info = document.getElementById('progInfo');
  try {
    const d = await api('progress');
    sel.innerHTML = '<option value="">직접 입력</option>' + d.items.map((i) => '<option value="' + esc(i.id) + '">' + esc(i.id + ' ' + i.title + ' (배점 ' + i.weight + ', ' + i.earned + '점)') + '</option>').join('');
    info.textContent = '출처 ' + d.source.file + ' @ ' + d.source.ref + ' ' + d.source.sha.slice(0, 12) + ' · 미완료 ' + d.items.length + '개';
  } catch (e) { sel.disabled = true; info.textContent = '진행률 항목을 불러오지 못함: ' + e.message; }
}

export async function applyDraft() {
  const id = document.getElementById('progSel').value, info = document.getElementById('progInfo'), f = document.getElementById('assign');
  if (!id) { info.textContent = ''; return; }
  try {
    const d = await api('progress/draft', { id });
    f.goal.value = d.draft.goal; f.doneCriteria.value = d.draft.doneCriteria.join('\n'); f.prompt.value = d.draft.prompt;
    if (d.suggestedFiles.length) f.allowedFiles.value = d.suggestedFiles.join('\n');
    info.innerHTML = '완료 조건·현재 평가 원문을 상세 지시에 인용했습니다. 점수는 바꾸지 않습니다. ' +
      (d.suggestedFiles.length ? '제안 파일을 3번 칸에 채웠습니다 — 필요하면 고치세요. ' : '<span class="warn">제안할 코드 파일이 없습니다 — 허용 파일을 직접 고르세요.</span>') +
      (d.skippedEvidence.length ? ' <span class="muted">제외: ' + d.skippedEvidence.map((x) => esc(x.path + ' (' + x.why + ')')).join(', ') + '</span>' : '');
    schedulePlan();
  } catch (e) { info.innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; }
}

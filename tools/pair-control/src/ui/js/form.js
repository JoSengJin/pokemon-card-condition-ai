// 새 작업 만들기 폼. 입력하면 서버의 plan(읽기 전용)으로 자동 준비될 값을 미리 보여 주고,
// 제출하면 Mastra prepare-task workflow가 worktree·브랜치·계약을 만든다.
import { api, esc, say, ui } from './core.js';
import { onScopeClick } from './form-scope.js';
import { onSpecClick, onSpecInput, renderSpecs, resetSpecs, specs } from './form-specs.js';

let planTimer = null, planSeq = 0;

export function initForm() {
  const f = document.getElementById('assign');
  f.addEventListener('input', (ev) => { onSpecInput(ev.target); schedulePlan(); });
  f.addEventListener('change', () => { if (ui.state) ui.rerender(); schedulePlan(); });
  f.addEventListener('click', (ev) => { if (onSpecClick(ev.target.closest('[data-spec]'))) schedulePlan(); });
  f.addEventListener('click', onScopeClick);
  f.addEventListener('submit', onSubmit);
  document.getElementById('progSel').addEventListener('change', applyDraft);
  resetSpecs(); renderSpecs(); updatePlan(); loadProgress();
}

function formBody() {
  const b = Object.fromEntries(new FormData(document.getElementById('assign')).entries());
  const [allowedFiles, conflictGroups, requiredModules, doneCriteria] = [[b.allowedFiles, '\n'], [b.conflictGroups, ','], [b.requiredModules, ','], [b.doneCriteria, '\n']]
    .map(([v, sep]) => String(v || '').split(sep).map((x) => x.trim()).filter(Boolean));
  return {
    ...b, allowedFiles, conflictGroups, requiredModules, doneCriteria,
    checks: specs.c.map((c, i) => ({ id: 'c' + (i + 1), name: c.name || '검사 ' + (i + 1), executable: c.executable, args: c.args, cwd: c.cwd || '.' })),
    postChecks: specs.p.map((c, i) => ({ id: 'p' + (i + 1), name: c.name || '통합 후 검사 ' + (i + 1), executable: c.executable, args: c.args, cwd: '.' })),
  };
}

function schedulePlan() { clearTimeout(planTimer); planTimer = setTimeout(updatePlan, 250); }

async function updatePlan() {
  const seq = ++planSeq, f = document.getElementById('assign');
  const preview = document.getElementById('preview'), btn = document.getElementById('prepareBtn');
  document.getElementById('scenarioBox').hidden = f.mode.value !== 'mock';
  const b = formBody();
  if (!b.goal && !b.allowedFiles.length) { preview.innerHTML = '<div class="muted">입력하면 자동으로 준비될 값이 여기에 보입니다.</div>'; btn.disabled = true; return; }
  try {
    const p = await api('plan', b);
    if (seq !== planSeq) return; // 더 최근 입력의 미리보기가 이미 요청됨
    const t = p.task, mk = p.createWorktree ? ' <span class="chip">새로 만듦</span>' : '';
    const kv = !t ? '' : '<div class="kv"><div>task ID</div><div class="mono">' + esc(t.taskId) + '</div>' +
      '<div>브랜치</div><div class="mono">' + esc(t.branch) + mk + '</div><div>작업 폴더</div><div class="mono">' + esc(t.worktree) + mk + '</div>' +
      '<div>시작 시점</div><div><span class="mono">' + esc(t.baseSha.slice(0, 12)) + '</span> · ' + esc(p.baseRef + ' · ' + p.baseSubject) + '</div>' +
      '<div>고칠 수 있는 곳</div><div class="mono">' + t.allowedFiles.map(esc).join(', ') + (p.scopeDefault ? ' <span class="chip">기본 범위</span>' : '') + '</div>' +
      '<div>실행 환경</div><div>' + esc({ none: 'Python 불필요', python: '자체 .venv 필요', 'python-project': '자체 .venv + 프로젝트 import 필요' }[t.env]) + (p.envAuto ? ' <span class="chip">자동</span>' : '') + '</div>' +
      '<div>작업 테스트</div><div class="mono small">' + (t.checks.map((c) => esc([c.executable].concat(c.args).join(' '))).join('<br>') || '<span class="bad">없음 — 승인할 수 없음</span>') + '</div>' +
      '<div>계약 파일</div><div class="mono">docs/collaboration/tasks/' + esc(t.taskId) + '.md <span class="chip">작업 브랜치에 커밋</span></div></div>';
    const bad = p.checks.filter((c) => !c.ok);
    preview.innerHTML = '<b>자동으로 준비될 값</b>' + kv +
      (bad.length ? bad.map((c) => '<div class="bad">✗ ' + esc(c.name) + ': ' + esc(c.detail) + '</div>').join('') : '<div class="ok">✓ 준비 가능</div>') +
      p.warnings.map((w) => '<div class="warn">⚠ ' + esc(w) + '</div>').join('');
    btn.disabled = !p.ok;
  } catch (e) { preview.innerHTML = '<div class="bad">' + esc(e.message) + '</div>'; btn.disabled = true; }
}

async function onSubmit(ev) {
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

async function loadProgress() {
  const sel = document.getElementById('progSel'), info = document.getElementById('progInfo');
  try {
    const d = await api('progress');
    sel.innerHTML = '<option value="">직접 입력</option>' + d.items.map((i) => '<option value="' + esc(i.id) + '">' + esc(i.id + ' ' + i.title + ' (배점 ' + i.weight + ', ' + i.earned + '점)') + '</option>').join('');
    info.textContent = '출처 ' + d.source.file + ' @ ' + d.source.ref + ' ' + d.source.sha.slice(0, 12) + ' · 미완료 ' + d.items.length + '개';
  } catch (e) { sel.disabled = true; info.textContent = '진행률 항목을 불러오지 못함: ' + e.message; }
}

/** 진행률 미완료 항목의 원문을 목표·완료 조건·상세 지시에 채운다(LLM 없음). */
async function applyDraft() {
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

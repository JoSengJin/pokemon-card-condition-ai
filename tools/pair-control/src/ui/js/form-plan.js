import { api, esc } from './core.js';

import { formBody } from './form-body.js';

export const planState = { timer: null, seq: 0 };

export function schedulePlan() { clearTimeout(planState.timer); planState.timer = setTimeout(updatePlan, 250); }

export async function updatePlan() {
  const seq = ++planState.seq, f = document.getElementById('assign');
  const preview = document.getElementById('preview'), btn = document.getElementById('prepareBtn');
  document.getElementById('scenarioBox').hidden = f.mode.value !== 'mock';
  const b = formBody();
  if (!b.goal && !b.allowedFiles.length) { preview.innerHTML = '<div class="muted">입력하면 자동으로 준비될 값이 여기에 보입니다.</div>'; btn.disabled = true; return; }
  try {
    const p = await api('plan', b);
    if (seq !== planState.seq) return; // 더 최근 입력의 미리보기가 이미 요청됨
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

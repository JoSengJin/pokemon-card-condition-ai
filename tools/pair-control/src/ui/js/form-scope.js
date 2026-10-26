// 허용 파일 채우기 도우미: 받은 프롬프트에서 목록을 옮긴다(서버가 글자 그대로 추출). 비워 두면 서버가 기본 범위를 적용한다.
// 붙여 넣은 프롬프트는 이름 없는 칸이라 작업 생성 요청에 포함되지 않고 저장·커밋되지 않는다.
import { api, esc } from './core.js';

export async function onScopeClick(ev) {
  const b = ev.target.closest('[data-scope]');
  if (!b) return;
  const info = document.getElementById('scopeInfo'), box = document.querySelector('#assign [name=allowedFiles]');
  const text = document.getElementById('scopeText').value;
  if (b.dataset.scope === 'extract' && !text.trim()) { info.innerHTML = '<span class="warn">먼저 위 칸에 받은 프롬프트를 붙여 넣으세요.</span>'; return; }
  try {
    const d = await api('scope', { text });
    const replaced = d.found && box.value.trim() && box.value.trim() !== d.files.join('\n');
    info.innerHTML = '<span class="' + (d.found ? 'ok' : 'warn') + '">' + esc(d.note) + (replaced ? ' 기존 입력을 바꿨습니다.' : '') + '</span>' +
      d.rejected.map((r) => '<div class="muted">제외: <span class="mono">' + esc(r.path) + '</span> — ' + esc(r.why) + '</div>').join('');
    if (!d.found) return;
    box.value = d.files.join('\n');
    box.dispatchEvent(new Event('input', { bubbles: true })); // 폼의 자동 미리보기를 다시 계산하게 한다
  } catch (e) { info.innerHTML = '<span class="bad">' + esc(e.message) + '</span>'; }
}

// 새 작업 폼의 "메인에게 계약 작성 요청 / 메인의 답 붙여넣기" 도우미. 요청문 생성과 답 나누기는 contract-request.js(순수 함수).
// 붙여 넣은 칸은 이름이 없어 작업 생성 요청에 포함되지 않고 저장·커밋되지 않는다. 채워진 폼 칸만 계약에 들어간다.
import { esc, ui } from './core.js';
import { buildMainRequest, parseContractReply } from './contract-request.js';
import { OCCUPYING_STATUSES } from './stages.js';

const FIELDS = { goal: 'goal', doneCriteria: 'doneCriteria', allowedFiles: 'allowedFiles', readDocs: 'readDocs', prompt: 'prompt' };

export async function onContractClick(ev) {
  const b = ev.target.closest('[data-contract]');
  if (!b) return;
  const f = document.getElementById('assign'), info = document.getElementById('contractInfo');
  if (b.dataset.contract === 'request') {
    const s = ui.state || { tasks: [], main: {} };
    const text = buildMainRequest({
      main: (s.main && s.main.agent) || 'codex', agent: f.agent.value,
      active: s.tasks.filter((t) => !t.archivedAt && OCCUPYING_STATUSES.includes(t.status)).map((t) => ({ taskId: t.taskId, agent: t.agent, allowedFiles: t.allowedFiles })),
      hint: f.goal.value,
    });
    const box = document.getElementById('contractReq');
    box.value = text; box.hidden = false;
    try { await navigator.clipboard.writeText(text); info.innerHTML = '<span class="ok">요청문을 복사했습니다. 메인(' + esc((s.main && s.main.agent) || 'codex') + ') 세션에 붙여 넣으세요.</span>'; }
    catch { box.select(); info.innerHTML = '<span class="warn">자동 복사를 못 했습니다. 선택된 텍스트를 직접 복사하세요(⌘C).</span>'; }
    return;
  }
  const r = parseContractReply(document.getElementById('contractReply').value);
  if (r.missing.length === 4) { info.innerHTML = '<span class="warn">"## 목표", "## 완료 조건", "## 허용 파일", "## 상세 지시" 제목을 찾지 못했습니다. 요청문의 답변 형식대로 받아 붙여 넣으세요.</span>'; return; }
  for (const k of Object.keys(FIELDS)) {
    const v = Array.isArray(r[k]) ? r[k].join('\n') : r[k];
    if (v) f[FIELDS[k]].value = v;
  }
  f.goal.dispatchEvent(new Event('input', { bubbles: true })); // 자동 미리보기를 다시 계산
  info.innerHTML = '<span class="ok">폼에 채웠습니다: 목표·완료 조건 ' + r.doneCriteria.length + '개·허용 파일 ' + r.allowedFiles.length + '개·읽을 문서 ' + r.readDocs.length + '개. 내용을 확인하고 고치세요.</span>' +
    (r.missing.length ? '<div class="warn">메인의 답에 없어 비워 둔 항목: ' + esc(r.missing.join(', ')) + '</div>' : '') +
    r.rejected.map((x) => '<div class="muted">경로로 읽지 못해 제외: ' + esc(x) + '</div>').join('');
}

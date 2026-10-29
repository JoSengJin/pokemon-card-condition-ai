// 메인 패널의 "교대 후 연속 처리" 표시. 서버의 pipelineView 요약을 그대로 그린다(계산·판단 없음).
// 세 가지 완료를 섞지 않는다: 메인 인수 완료(세션) / 개별 행동 성공(턴 결과) / 작업 파이프라인 완료(원격 push 검증된 작업만).
import { esc, lbl } from './core.js';

const TURN = { launching: '시작 중', launched: '모델 응답 대기', verified: '응답 검증됨(적용 대기)', applying: '행동 적용 중', applied: '적용 끝', limited: '한도로 종료', stale: '이전 세대 응답(무시)', failed: '실패', unknown: '결과 불명' };
const TURN_CLS = { applied: 'ok', launching: 'info', launched: 'info', verified: 'info', applying: 'info', failed: 'bad', unknown: 'bad', limited: 'warn', stale: 'muted' };

const actionHtml = (a) => '<div class="' + (a.ok ? 'ok' : 'bad') + '">' + (a.ok ? '✓ ' : '✗ ') + esc(a.type + ': ' + a.detail) + '</div>';

function turnHtml(t, current) {
  const head = '세대 ' + t.generation + ' · ' + esc(t.agent) + ' · ' + lbl(esc(TURN[t.status] || t.status), TURN_CLS[t.status] || 'muted') + ' · 행동 성공 ' + t.actionsOk + '/' + t.actionsTotal;
  return '<div class="pipeTurn' + (current ? ' cur' : '') + '">' + (current ? '<b>현재 턴</b> ' : '') + head +
    (t.failure ? ' <span class="warn">' + esc(t.failure) + '</span>' : '') + t.actions.map(actionHtml).join('') + '</div>';
}

const heldHtml = (h) => '<div class="warn">' + esc(h.reason) + ' <span class="muted mono">' + esc(h.key.slice(0, 40)) + '</span></div>';
const taskHtml = (t) => '<div>' + esc(t.taskId) + ' · ' + esc(t.status) + ' · ' + (t.pipelineDone ? lbl('파이프라인 완료(원격 push 검증됨)', 'ok') : lbl('완료 아님(원격 push 검증 전)', 'muted')) + '</div>';

/** p = state.mainRuntime.pipeline. 값이 없으면 영역을 비운다. */
export function renderPipeline(p) {
  const el = document.getElementById('pipeRt');
  if (!el) return;
  if (!p) { el.innerHTML = ''; return; }
  const tk = p.takeover, ev = p.events;
  const takeover = tk ? '메인 인수: ' + esc(tk.from) + ' → <b>' + esc(tk.agent) + '</b> (세대 ' + tk.generation + ') · ' + (tk.acked ? lbl('인수 확인됨', 'ok') : lbl('인수 확인 전', 'info')) : '메인 인수: ' + lbl('진행 중인 교대 세션 없음', 'muted');
  const last = p.turns.slice(0, -1).reverse();
  el.innerHTML = '<div class="pipeHead"><b>교대 후 연속 처리</b></div><div>' + takeover + '</div>' +
    '<div class="muted">이벤트 대기 ' + ev.pending + ' · 턴 진행 ' + ev.launched + ' · 적용 ' + ev.applied + ' · 보류 ' + ev.held + ' · 결과 불명 ' + ev.unknown + '</div>' +
    (p.currentTurn ? turnHtml(p.currentTurn, true) : '<div class="muted">모델 턴 없음</div>') +
    (last.length ? '<details open><summary class="small muted">이전 턴 ' + last.length + '개</summary>' + last.map((t) => turnHtml(t, false)).join('') + '</details>' : '') +
    (p.heldReasons.length ? '<div class="pipeHeld"><b>보류·결과 불명 사유</b>' + p.heldReasons.map(heldHtml).join('') + '</div>' : '') +
    (p.tasks.length ? '<div class="pipeTasks"><b>작업별 완료 상태</b>' + p.tasks.map(taskHtml).join('') + '</div>' : '');
}

import { api, say, ui } from './core.js';
import { ACTIONS, STAY } from './action-routes.js';
import { askText } from './action-confirm.js';
import { bodyOf } from './action-body.js';

export async function run(act, el) {
  const a = ACTIONS[act];
  const tid = el.dataset.task || ui.selected; // 보관 목록의 버튼은 선택과 다른 작업을 가리킨다
  const t = ui.state && ui.state.tasks.find((x) => x.taskId === tid);
  if (!a.g && !t) return;
  const ask = askText(act, t, el);
  if (ask && !confirm(ask)) return;
  const body = bodyOf(act, t, el);
  if (body === null) return;
  say(a.n + ' 요청 중…', 'muted');
  try {
    const d = await api(a.g || 'tasks/' + encodeURIComponent(t.taskId) + '/' + a.p, a.get ? undefined : body);
    const m = keepResult(act, t, d);
    say(m[0], m[1]);
    if (t && !a.g && !STAY.has(act)) delete ui.stage[t.taskId]; // 고정을 풀면 renderTask가 지금 단계를 연다
  } catch (e) {
    say(a.n + ' 실패: ' + e.message, 'bad');
    if (act === 'maincheck') ui.mainBlockers = { error: e.message };
  }
  setTimeout(ui.refreshNow, 0);
}

export function keepResult(act, t, d) {
  const id = t && t.taskId;
  switch (act) {
    case 'env': return d && d.ready ? ['실행 준비됨', 'ok'] : ['아직 준비 안 됨 — 안내된 명령을 직접 실행하세요', 'warn'];
    case 'prompt': ui.prompt[id] = d.text; return ['프롬프트 생성됨 — 복사해서 에이전트 세션에 붙여 넣으세요', 'ok'];
    case 'handoff': case 'handoffauto': case 'hshow': ui.handoff[id] = d.message + '\n\n' + d.text; if (d.autoNote) return [d.autoNote, d.autoNote.startsWith('자동 확인 안 함') ? 'warn' : 'ok']; return [act === 'handoff' ? '인계됨 — 안내문을 메인 에이전트에게 전달하세요' : '인계 안내문을 불러왔습니다', 'ok'];
    case 'diff': ui.diff = { key: id + ':' + t.result.headSha, text: d.diff || '(변경 없음)' }; return ['diff를 불러왔습니다', 'ok'];
    case 'checks': return ['작업 테스트 시작 — 결과는 작업 테스트 단계에서 확인', 'ok'];
    case 'review': return ['fake 리뷰 CLI 시작(모델 요청 없음)', 'ok'];
    case 'integrate': return ['통합 결과: ' + d.status + ' — ' + (d.statusReason || ''), d.status === 'integrated' ? 'ok' : 'bad'];
    case 'pushcheck': return d.blockers.length ? ['푸시 막힘 ' + d.blockers.length + '건 — 사유를 확인하세요', 'bad'] : ['푸시 가능 — 대상 SHA를 입력하세요', 'ok'];
    case 'push': ui.keep.pushConfirm = ''; return ['푸시 결과: ' + d.status + ' — ' + d.detail, d.status === 'pushed_verified' ? 'ok' : 'bad'];
    case 'verify': return ['원격 확인: ' + d.status + ' — ' + d.detail, d.status === 'pushed_verified' ? 'ok' : 'bad'];
    case 'revert': return ['되돌림 커밋 ' + d.commits.length + '개 준비 · 트리 복원 ' + (d.treeRestored ? '확인됨' : '불일치') + ' — 이제 ①~③으로 푸시하세요', d.treeRestored ? 'ok' : 'warn'];
    case 'pushack': return ['오탐으로 기록했습니다. 다시 점검하세요', 'ok'];
    case 'venv': return d && d.ready ? ['.venv를 만들었고 실행 준비가 끝났습니다 — 이제 시작할 수 있습니다', 'ok'] : ['.venv를 만들었습니다. 남은 준비 항목을 확인하세요', 'warn'];
    case 'unapprove': return ['승인을 취소했습니다 — 검토 단계로 돌아왔습니다(에이전트 재실행 없음)', 'ok'];
    case 'discard': ui.selected = null; return [id + ' 폐기됨 — 아래 "보관된 작업"에 사유와 함께 남습니다(브랜치·작업 폴더는 지우지 않음)', 'ok'];
    case 'archivefin': return [d.archived.length ? '끝난 작업 ' + d.archived.length + '개를 보관했습니다: ' + d.archived.join(', ') : '보관할 끝난 작업이 없습니다', d.archived.length ? 'ok' : 'muted'];
    case 'mainhandover': case 'mainlimit': return d.ok ? ['새 메인 실행 시작 — 인수 확인 결과는 위 메인 패널에서 확인하세요(완료 표시는 다음 행동 수행 뒤에만 나옵니다)', 'ok'] : ['교대하지 못함: ' + (d.detail || d.status) + ' — 상태·복구 지점은 보존됨, 자동 재시도 없음', 'warn'];
    case 'mainclear': return ['한도 풀림을 기록했습니다(재시도·크레딧 구매는 하지 않음)', 'ok'];
    case 'apprgrant': return ['승인 장부에 기록했습니다(기록일 뿐 승인을 새로 만들지 않음)', 'ok'];
    case 'apprrevoke': return ['승인을 철회했습니다', 'ok'];
    case 'archive': ui.selected = null; return [id + ' 보관됨 — 아래 "보관된 작업"에서 해제할 수 있습니다', 'ok'];
    case 'unarchive': ui.selected = id; return [id + ' 보관 해제됨', 'ok'];
    case 'maincheck': ui.mainBlockers = { list: d.blockers }; return ['', ''];
    case 'mainswap': document.getElementById('mainMemo').value = d.memo; ui.mainBlockers = null; return ['메인이 ' + d.role.agent + '(으)로 바뀌었습니다 — 새 메인에게 한 줄로 알려 주세요', 'ok'];
    default: return [ACTIONS[act].n + ' 요청 처리됨', 'ok'];
  }
}

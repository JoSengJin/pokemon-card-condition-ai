// 버튼 동작. 화면의 모든 버튼은 data-act 하나로 표시하고, 여기서 위임 처리한다.
// 서버 요청은 정해진 경로표(ACTIONS)만 쓴다. 임의 경로·명령은 보내지 않는다.
import { api, say, ui } from './core.js';

// p: 작업 경로(tasks/:id/<p>), g: 전체 경로, get: 조회 요청, n: 메시지용 이름
const ACTIONS = {
  start: { p: 'start', n: '시작' }, env: { p: 'recheck-env', n: '준비 상태 확인' }, cancel: { p: 'cancel', n: '중단' },
  finish: { p: 'finish-manual', n: '작업 완료' }, apply: { p: 'apply-exit', n: '결과 반영' }, ack: { p: 'ack-unknown', n: '결과 불명 확정' },
  recollect: { p: 'recollect', n: '다시 수집' }, checks: { p: 'run-checks', n: '작업 테스트 실행' }, review: { p: 'review', n: '리뷰 작업' },
  prompt: { p: 'start-prompt', n: '시작 프롬프트' }, handoff: { p: 'handoff', n: '인계' }, hshow: { p: 'handoff-text', get: true, n: '인계 안내문' },
  hconfirm: { p: 'handoff-confirm', n: '메인 확인' }, hcancel: { p: 'handoff-cancel', n: '인계 취소' }, diff: { p: 'diff', get: true, n: 'diff' },
  approve: { p: 'approve', n: '승인' }, reject: { p: 'reject', n: '거절' }, integrate: { p: 'integrate', n: '통합' }, rereview: { p: 'rereview', n: '재검토' },
  venv: { p: 'create-venv', n: '환경 만들기' }, unapprove: { p: 'unapprove', n: '승인 취소' }, archive: { p: 'archive', n: '보관' }, unarchive: { p: 'archive', n: '보관 해제' },
  pushcheck: { g: 'push/preflight', n: '푸시 점검' }, pushack: { g: 'push/ack', n: '오탐 확인' }, push: { g: 'push/run', n: '푸시' },
  verify: { g: 'push/verify', n: '원격 확인' }, revert: { g: 'push/revert-prepare', n: '되돌림 준비' },
  maincheck: { g: 'main/blockers', get: true, n: '이양 안전 확인' }, mainswap: { g: 'main/swap', n: '메인 이양' },
  limitclear: { g: 'limit/clear', n: '한도 해제' }, probe: { g: 'probes', n: 'CLI 확인' },
};


export function onClick(ev) {
  const el = ev.target.closest('[data-act]');
  if (!el || el.disabled) return;
  const act = el.dataset.act;
  if (el.dataset.stage && ui.selected) ui.stage[ui.selected] = el.dataset.stage;
  if (act === 'select') ui.selected = el.dataset.id;
  else if (act === 'log') ui.keep.logSel = el.dataset.id;
  else if (act === 'logfollow') ui.keep.logFollow = ui.keep.logFollow === false;
  else if (act === 'logpause') ui.keep.logPaused = !ui.keep.logPaused;
  else if (act === 'copy') return copyText(document.getElementById(el.dataset.target), el.dataset.what);
  else if (act === 'maincopy') return copyText(document.getElementById('mainMemo'), '이양 메모');
  else if (ACTIONS[act]) return run(act, el);
  ui.rerender();
}

/** 되돌릴 수 없거나 무거운 동작은 실행 전에 무엇을 하는지 보여 주고 확인받는다. */
function askText(act, t, el) {
  const plan = ui.state.push && ui.state.push.plan;
  switch (act) {
    case 'cancel': return '이 작업에서 이 실행기가 만든 실행 중 프로세스 그룹만 종료합니다(수동 모드는 파일 점유만 해제).';
    case 'finish': return '에이전트 세션의 작업이 끝났고 커밋까지 마쳤습니까? 결과를 수집해 Git 검사로 넘어갑니다.';
    case 'ack': return '결과 불명을 확정합니다. 완료로 보지 않고 잠금만 해제합니다.';
    case 'checks': return '작업 폴더에서 아래 명령을 셸 없이 차례로 실행합니다(SHA ' + t.result.headSha.slice(0, 12) + '):\n' + t.checks.map((c) => '  ' + [c.executable].concat(c.args).join(' ')).join('\n') + '\n\n계속할까요?';
    case 'hconfirm': return '메인 에이전트가 확인을 끝냈습니까? 이 표시는 승인 기록에 남지만 승인을 대신하지 않습니다.';
    case 'approve': return '승인 SHA ' + t.result.headSha + '\n코드·계약·기준 브랜치·관련 파일이 바뀌면 승인은 무효화됩니다.';
    case 'integrate': return '승인 SHA를 재검증한 뒤 통합 checkout에서 ./develop -- git cherry-pick -x 를 실행합니다. push는 하지 않습니다.' + (t.postChecks.length ? '\n이어서 통합 후 검사:\n' + t.postChecks.map((c) => '  ' + [c.executable].concat(c.args).join(' ')).join('\n') : '\n통합 후 검사 없음(미실행으로 표시)');
    case 'push': return '원격 ' + ui.state.push.remote + '/' + ui.state.push.branch + ' 에 ' + plan.commits.length + '개 커밋을 푸시합니다.\n' + plan.remoteHead.slice(0, 12) + ' → ' + plan.localHead.slice(0, 12) + '\n\n푸시는 취소할 수 없습니다(실수는 되돌림 커밋으로만 바로잡습니다). 계속할까요?';
    case 'pushack': return '다음 항목이 실제 비밀이 아니라 가짜·예시 값임을 확인했습니까?\n\n' + plan.findings.filter((f) => f.kind === 'secret_pattern' && !f.acknowledged).map((f) => f.file + ':' + f.line + ' (커밋 ' + (f.commit || '').slice(0, 8) + ')').join('\n') + '\n\n이 확인은 해당 커밋·파일·줄에만 적용되고 기록됩니다.';
    case 'revert': return '푸시한 커밋마다 되돌림(revert) 커밋을 통합 checkout에 만듭니다(로컬만, ./develop 잠금 안). 원격은 바뀌지 않으며, 만든 뒤 ①~③ 절차로 푸시합니다.';
    case 'mainswap': return '메인을 ' + el.dataset.to + '(으)로 이양합니다. 이 화면은 표시·기록만 하며 권한을 강제하지 않습니다. 계속할까요?';
    case 'venv': return '이 작업 폴더에서 아래 명령 하나만 실행합니다(셸 없음, 패키지 설치 없음, 네트워크 없음):\n\n  python3 -m venv .venv\n\n기본 checkout이나 다른 작업 폴더에는 만들지 않습니다.';
    case 'unapprove': return '승인을 취소하고 같은 SHA로 검토 단계로 돌아갑니다.\n에이전트는 다시 실행하지 않으며, 같은 SHA의 작업 테스트 결과는 그대로 유효합니다. 통합 전이라 main은 바뀌지 않습니다.';
    case 'archive': return t.taskId + ' 을(를) 목록에서 숨깁니다. 기록·작업 폴더·브랜치는 지우지 않으며 "보관된 작업"에서 언제든 해제할 수 있습니다.';
    case 'limitclear': return '구독 한도가 풀렸고 추가 크레딧 없이 계속 쓸 수 있음을 확인했습니까?';
    default: return '';
  }
}

/** 요청 본문. null이면 사용자가 입력을 취소한 것이다. */
function bodyOf(act, t, el) {
  switch (act) {
    case 'prompt': return { unattended: !!ui.keep.pUnattended, extraDocs: String(ui.keep.pDocs || '').split(',').map((x) => x.trim()).filter(Boolean) };
    case 'review': return { mode: 'mock', mockScenario: ui.keep.revScenario || 'approve' };
    case 'approve': return { sha: t.result.headSha };
    case 'reject': { const reason = prompt('거절 사유'); return reason === null ? null : { reason }; }
    case 'push': return { confirm: String(ui.keep.pushConfirm || '').trim() };
    case 'pushack': return { fingerprints: ui.state.push.plan.findings.filter((f) => f.kind === 'secret_pattern' && !f.acknowledged).map((f) => f.fingerprint) };
    case 'verify': case 'revert': return { id: el.dataset.id };
    case 'archive': return { archived: true };
    case 'unarchive': return { archived: false };
    case 'mainswap': return { agent: el.dataset.to, reason: document.getElementById('mainReason').value };
    default: return {};
  }
}

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
  } catch (e) {
    say(a.n + ' 실패: ' + e.message, 'bad');
    if (act === 'maincheck') ui.mainBlockers = { error: e.message };
  }
  ui.rerender();
  setTimeout(ui.refreshNow, 0);
}

/** 응답 중 화면에 남길 값(프롬프트·안내문·diff 등)을 저장하고 결과 문구를 고른다. */
function keepResult(act, t, d) {
  const id = t && t.taskId;
  switch (act) {
    case 'env': return d && d.ready ? ['실행 준비됨', 'ok'] : ['아직 준비 안 됨 — 안내된 명령을 직접 실행하세요', 'warn'];
    case 'prompt': ui.prompt[id] = d.text; return ['프롬프트 생성됨 — 복사해서 에이전트 세션에 붙여 넣으세요', 'ok'];
    case 'handoff': case 'hshow': ui.handoff[id] = d.message + '\n\n' + d.text; return [act === 'handoff' ? '인계됨 — 안내문을 메인 에이전트에게 전달하세요' : '인계 안내문을 불러왔습니다', 'ok'];
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
    case 'archive': ui.selected = null; return [id + ' 보관됨 — 아래 "보관된 작업"에서 해제할 수 있습니다', 'ok'];
    case 'unarchive': ui.selected = id; return [id + ' 보관 해제됨', 'ok'];
    case 'maincheck': ui.mainBlockers = { list: d.blockers }; return ['', ''];
    case 'mainswap': document.getElementById('mainMemo').value = d.memo; ui.mainBlockers = null; return ['메인이 ' + d.role.agent + '(으)로 바뀌었습니다 — 새 메인에게 한 줄로 알려 주세요', 'ok'];
    default: return [ACTIONS[act].n + ' 요청 처리됨', 'ok'];
  }
}

async function copyText(el, what) {
  const text = el && (el.value ?? el.textContent); // 칸(textarea)은 value, 로그(pre)는 textContent
  if (!text) return say(what + ': 복사할 내용이 없습니다', 'warn');
  try { await navigator.clipboard.writeText(text); say(what + ' 복사됨', 'ok'); }
  catch { if (el.select) el.select(); else window.getSelection().selectAllChildren(el); say('자동 복사를 못 했습니다. 선택된 텍스트를 직접 복사하세요(⌘C)', 'warn'); }
}

/** data-keep 입력값을 다시 그려도 남도록 ui.keep에 저장한다. 메인 역할을 펼치면 이양 안전 확인을 한다. */
export function onInput(ev) {
  const el = ev.target;
  if (el.id === 'mainBox' && ev.type === 'toggle' && el.open) return run('maincheck', el);
  const k = el.dataset && el.dataset.keep;
  if (!k) return;
  ui.keep[k] = el.type === 'checkbox' ? el.checked : el.tagName === 'DETAILS' ? el.open : el.value;
  if (k === 'logSel' || k === 'logFind') return ui.rerender(); // 로그 선택·찾기는 바로 다시 그린다
  if (k !== 'pushConfirm') return;
  const p = ui.state.push && ui.state.push.plan, v = el.value.trim().toLowerCase();
  const b = document.querySelector('[data-act=push]');
  if (b) b.disabled = !(p && !p.blockers.length && v.length >= 12 && p.localHead.startsWith(v));
}

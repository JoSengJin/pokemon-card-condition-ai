// 파이프라인 앞쪽 단계의 상세 패널: 준비 · 구현 · Git 검사 · 작업 테스트 · 리뷰.
// 각 함수는 HTML 문자열만 만든다. 버튼은 data-act로 표시하고 동작은 actions.js가 처리한다.
import { B, esc, lbl } from './core.js';
import { venvMissing } from './stages.js';

const STARTABLE = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

export function panelPrepare(t) {
  const env = t.envReadiness;
  const can = STARTABLE.includes(t.status) && (!env || env.ready);
  return '<div class="kv"><div>작업 폴더</div><div class="mono">' + esc(t.worktree) + '</div>' +
    '<div>브랜치</div><div class="mono">' + esc(t.branch) + '</div><div>기준 SHA</div><div class="mono">' + esc(t.baseSha) + '</div>' +
    '<div>작업 계약</div><div class="mono">' + esc(t.contractPath) + ' @ ' + esc((t.contractSha || '').slice(0, 12)) + '</div>' +
    '<div>고칠 수 있는 곳</div><div class="mono">' + t.allowedFiles.map(esc).join('<br>') + '</div></div>' +
    '<h4>실행 환경 ' + (env ? (env.ready ? lbl('준비됨', 'ok') : lbl('준비 안 됨', 'bad')) : '') + '</h4>' +
    (env ? env.checks.map((c) => '<div>' + (c.ok ? lbl('✓', 'ok') : lbl('✗', 'bad')) + ' ' + esc(c.name) + ' <span class="muted">' + esc(c.detail) + '</span></div>').join('') : '') +
    (env && env.fixes.length ? '<p class="small">' + (venvMissing(env) ? '"환경 만들기"를 누르면 이 작업 폴더에 <code>python3 -m venv .venv</code>만 실행합니다(패키지 설치 없음). 직접 하려면 아래 명령을 실행한 뒤 "준비 상태 다시 확인"을 누르세요.' : '아래 명령을 직접 실행한 뒤 "준비 상태 다시 확인"을 누르세요(도구는 설치하지 않습니다).') + '</p>' + env.fixes.map((f) => '<pre class="cmd">' + esc(f) + '</pre>').join('') : '') +
    '<div class="actions">' + B('venv', '환경 만들기(.venv)', venvMissing(env) && STARTABLE.includes(t.status), 'primary') + B('start', t.mode === 'manual' ? '작업 시작(파일 점유)' : '에이전트 시작', can, 'primary') + B('env', '준비 상태 다시 확인', true) + '</div>';
}

export function panelBuild(t, ui) {
  const s = t.status, e = t.exec;
  const manual = t.mode === 'manual';
  const k = ui.keep;
  const promptBox = !manual ? '' : '<h4>에이전트에게 줄 시작 프롬프트</h4>' +
    '<p class="small muted">' + esc(t.agent) + ' 세션에 붙여 넣으세요. 작업 위치(로컬 경로)는 복사할 때만 만들고 파일에 커밋하지 않습니다.</p>' +
    '<div class="row small"><label class="inline"><input type="checkbox" data-keep="pUnattended"' + (k.pUnattended ? ' checked' : '') + '> 무인 실행(사람 정답 추정·재요청 금지 문구 추가)</label>' +
    '<input data-keep="pDocs" value="' + esc(k.pDocs || '') + '" placeholder="추가로 먼저 읽을 문서(쉼표, 저장소 상대경로)">' + B('prompt', '프롬프트 만들기', true) + '</div>' +
    '<textarea id="pText" readonly rows="7" placeholder="여기에 생성된 프롬프트가 나타납니다">' + esc(ui.prompt[t.taskId] || '') + '</textarea>' +
    '<div class="actions">' + B('copy', '복사', !!ui.prompt[t.taskId], '', ' data-target="pText" data-what="시작 프롬프트"') + '</div>';
  const run = !e ? '' : '<h4>도구가 실행한 에이전트 프로세스</h4><div class="kv small"><div>명령</div><div class="mono">' + esc(e.display.join(' ')) + '</div>' +
    '<div>PID / PGID</div><div class="mono">' + esc(e.pid + ' / ' + e.pgid) + (e.groupAlive ? ' (실행 중)' : ' (종료)') + '</div>' +
    '<div>종료코드 / 신호</div><div class="mono">' + esc((e.exitCode ?? '—') + ' / ' + (e.signal ?? '—')) + '</div><div>토큰 · 비용</div><div>미측정</div></div>';
  return '<p>' + (manual ? '수동 모드: 도구는 에이전트를 실행하지 않고 파일 점유만 유지합니다. 에이전트 세션에서 작업·커밋을 마친 뒤 "작업 완료 — 결과 수집"을 누르세요.'
    : t.mode === 'real' ? '도구가 실제 ' + esc(t.agent) + ' CLI를 구독 로그인으로 실행합니다.' : '연습(mock) 프로세스입니다. 코드 품질을 검증하지 않습니다.') + '</p>' +
    (t.statusReason ? '<p class="muted">' + esc(t.statusReason) + '</p>' : '') + promptBox + run +
    '<div class="actions">' + B('finish', '작업 완료 — 결과 수집', s === 'manual_working', 'primary') +
    B('apply', '재시작 후 결과 반영', s === 'exit_observed', 'primary') +
    B('cancel', manual ? '작업 취소(파일 점유 해제)' : '실행 중단(이 실행기 프로세스만)', ['running', 'cancelling', 'orphan_running', 'manual_working'].includes(s), 'danger') +
    B('ack', '결과 불명 확정(완료 아님)', s === 'unknown', 'danger') + B('start', '다시 시작', ['failed', 'cancelled', 'abandoned'].includes(s)) +
    (e ? B('log', '로그 보기', true, 'link') : '') + '</div>';
}

export function panelGit(t, ui) {
  const r = t.result;
  if (!r) return '<p class="muted">구현이 끝나면 도구가 브랜치·커밋·허용 파일을 자동으로 검사합니다.</p>';
  const key = t.taskId + ':' + r.headSha;
  const diff = ui.diff && ui.diff.key === key ? ui.diff.text : '';
  return r.checks.map((c) => '<div>' + (c.ok ? lbl('✓', 'ok') : lbl('✗', 'bad')) + ' ' + esc(c.name) + ' <span class="muted">' + esc(c.detail) + '</span></div>').join('') +
    '<div class="kv small" style="margin-top:6px"><div>결과 SHA</div><div class="mono">' + esc(r.headSha) + '</div>' +
    '<div>변경 파일</div><div class="mono">' + (r.changedFiles.map(esc).join('<br>') || '—') + '</div>' +
    (r.outOfScope.length ? '<div>범위 밖</div><div class="mono bad">' + r.outOfScope.map(esc).join('<br>') + '</div>' : '') + '</div>' +
    '<div class="actions">' + B('diff', diff ? 'diff 다시 불러오기' : 'diff 보기', true) + B('recollect', '결과 다시 수집', t.status === 'review_pending') + '</div>' +
    (diff ? '<pre class="diff">' + esc(diff) + '</pre>' : '');
}

export function panelTests(t) {
  const v = t.verification, sha = t.result && t.result.headSha;
  const stale = v && (v.sha !== sha || v.contractHash !== t.contractHash);
  const names = { pending: '대기', running: '실행 중', passed: '통과', failed: '실패', cancelled: '중단', unknown: '결과 불명', not_run: '미실행' };
  const cls = { passed: 'ok', failed: 'bad', unknown: 'bad', cancelled: 'warn', running: 'info' };
  return '<h4>계약에 적힌 검사</h4>' + ((t.checks || []).map((c) => '<div class="mono small">' + esc([c.executable].concat(c.args).join(' ')) + ' <span class="muted">(cwd ' + esc(c.cwd) + ')</span></div>').join('') || '<p class="bad">검사가 없어 승인할 수 없습니다.</p>') +
    (v ? '<h4>실행 결과 ' + (stale ? lbl('이전 SHA 결과 — 통과로 보지 않음', 'warn') : '') + '</h4>' + v.items.map((i) => '<div class="runrow">' + lbl(esc(names[i.status] || i.status), cls[i.status] || 'muted') +
      ' <b>' + esc(i.name) + '</b> <span class="muted small">code ' + esc(i.exitCode ?? '—') + ' · SHA ' + esc((i.sha || '').slice(0, 12)) + '</span>' +
      (i.execId ? ' <button type="button" class="link" data-act="log" data-id="' + esc(i.execId) + '">로그</button>' : '') + '</div>').join('') +
      (v.note ? '<p class="warn small">' + esc(v.note) + '</p>' : '') : '<p class="muted">아직 실행하지 않았습니다. 미실행은 통과가 아닙니다.</p>') +
    '<div class="actions">' + B('checks', v ? '작업 테스트 다시 실행' : '작업 테스트 실행', t.status === 'review_pending' && (t.checks || []).length > 0 && !(v && v.status === 'running'), 'primary') + '</div>';
}

export function panelReview(t, ui) {
  const r = t.review;
  const other = t.agent === 'claude' ? 'Codex' : 'Claude';
  const sel = ui.keep.revScenario || 'approve';
  const opt = [['approve', '승인 의견'], ['changes_requested', '수정 필요'], ['insufficient_evidence', '근거 부족'], ['garbage', '형식 오류'], ['hang', '끝나지 않음']]
    .map((o) => '<option value="' + o[0] + '"' + (o[0] === sel ? ' selected' : '') + '>fake: ' + o[1] + '</option>').join('');
  return '<p>' + other + '가 고정 SHA·diff·계약·검사 결과 묶음을 <b>별도 프로세스</b>로 검토합니다. 현재 Codex 앱 대화로 보내지 않으며, 결과는 참고일 뿐 사람 승인을 대신하지 않습니다. 지금은 fake 리뷰 CLI(모델 요청 없음)만 연결되어 있습니다.</p>' +
    (r ? '<div class="kv small"><div>리뷰</div><div>' + esc(r.reviewer + ' (' + r.mode + ') · SHA ' + r.sha.slice(0, 12) + ' · ' + r.status + (r.verdict ? ' / ' + r.verdict : '')) + '</div>' +
      (r.summary ? '<div>요약</div><div>' + esc(r.summary) + '</div>' : '') + (r.note ? '<div>메모</div><div class="warn">' + esc(r.note) + '</div>' : '') + '</div>' +
      (r.execId ? '<button type="button" class="link" data-act="log" data-id="' + esc(r.execId) + '">리뷰 로그</button>' : '') : '') +
    '<div class="actions"><select data-keep="revScenario">' + opt + '</select>' + B('review', other + ' 리뷰 실행(mock)', t.status === 'review_pending' && !(r && r.status === 'running')) + '</div>';
}

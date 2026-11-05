import { B, esc, lbl } from './core.js';
import { venvMissing } from './stages.js';

export const STARTABLE = ['assigned', 'blocked', 'failed', 'cancelled', 'rejected', 'abandoned'];

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
  // 수동 모드는 도구가 볼 출력이 없어, 작업 폴더의 변화(새 커밋·변경 파일·범위 밖)를 대신 보여 준다(읽기만 함).
  const a = s === 'manual_working' && ui.activity[t.taskId];
  const activity = !a ? '' : '<h4>작업 폴더 활동 <span class="muted small">출력이 없는 수동 모드의 대신 표시 · 읽기만 함</span></h4>' +
    '<div class="small">새 커밋 ' + a.commits.length + '개 · 변경 파일 ' + a.changed.length + '개 · 미커밋 ' + a.dirty.length + '개 · ' + lbl('범위 밖 ' + a.outOfScope.length + '개', a.outOfScope.length ? 'bad' : 'ok') + '</div>' +
    a.commits.map((c) => '<div class="small"><span class="mono">' + esc(c.sha) + '</span> ' + esc(c.subject) + ' <span class="muted">' + esc((c.at || '').slice(11, 19)) + '</span></div>').join('') +
    a.outOfScope.map((f) => '<div class="mono small bad">' + esc(f) + '</div>').join('') +
    (a.dirty.length ? '<div class="small muted">미커밋</div>' + a.dirty.map((f) => '<div class="mono small muted">' + esc(f) + '</div>').join('') : '');
  const run = !e ? '' : '<h4>도구가 실행한 에이전트 프로세스</h4><div class="kv small"><div>명령</div><div class="mono">' + esc(e.display.join(' ')) + '</div>' +
    '<div>PID / PGID</div><div class="mono">' + esc(e.pid + ' / ' + e.pgid) + (e.groupAlive ? ' (실행 중)' : ' (종료)') + '</div>' +
    '<div>종료코드 / 신호</div><div class="mono">' + esc((e.exitCode ?? '—') + ' / ' + (e.signal ?? '—')) + '</div><div>토큰 · 비용</div><div>미측정</div></div>';
  return activity + '<p>' + (manual ? '수동 모드: 도구는 에이전트를 실행하지 않고 파일 점유만 유지합니다. 에이전트 세션에서 작업·커밋을 마친 뒤 "작업 완료 — 결과 수집"을 누르세요.'
    : t.mode === 'real' ? '도구가 실제 ' + esc(t.agent) + ' CLI를 구독 로그인으로 실행합니다.' : '연습(mock) 프로세스입니다. 코드 품질을 검증하지 않습니다.') + '</p>' +
    (t.statusReason ? '<p class="muted">' + esc(t.statusReason) + '</p>' : '') + promptBox + run +
    '<div class="actions">' + B('finish', '작업 완료 — 결과 수집', s === 'manual_working', 'primary') +
    B('apply', '재시작 후 결과 반영', s === 'exit_observed', 'primary') +
    B('cancel', manual ? '작업 취소(파일 점유 해제)' : '실행 중단(이 실행기 프로세스만)', ['running', 'cancelling', 'orphan_running', 'manual_working'].includes(s), 'danger') +
    B('ack', '결과 불명 확정(완료 아님)', s === 'unknown', 'danger') + B('start', '다시 시작', ['failed', 'cancelled', 'abandoned'].includes(s)) +
    '</div>';
}

import { ui } from './core.js';

export function askText(act, t, el) {
  const plan = ui.state.push && ui.state.push.plan;
  switch (act) {
    case 'cancel': return '이 작업에서 이 실행기가 만든 실행 중 프로세스 그룹만 종료합니다(수동 모드는 파일 점유만 해제).';
    case 'finish': return '에이전트 세션의 작업이 끝났고 커밋까지 마쳤습니까? 결과를 수집해 Git 검사로 넘어갑니다.';
    case 'ack': return '결과 불명을 확정합니다. 완료로 보지 않고 잠금만 해제합니다.';
    case 'checks': return '작업 폴더에서 아래 명령을 셸 없이 차례로 실행합니다(SHA ' + t.result.headSha.slice(0, 12) + '):\n' + t.checks.map((c) => '  ' + [c.executable].concat(c.args).join(' ')).join('\n') + '\n\n계속할까요?';
    case 'handoffauto': return '인계한 뒤 메인(' + ((ui.state.main && ui.state.main.agent) || 'codex') + ')을 별도 CLI 프로세스로 실행해 확인시킵니다(read-only, 구독 로그인 가드 통과 시에만). 대화 중인 메인 세션이 아니며 승인을 대신하지 않습니다. 구독 사용량이 소모됩니다.';
    case 'mainhandover': return '새 메인(' + (ui.state.main.agent === 'codex' ? 'claude' : 'codex') + ')을 별도 CLI 프로세스로 실제 실행해 교대합니다(구독 사용량 소모, 구독 로그인 가드 통과 시에만).\n실행 전 체크포인트를 저장하고, 새 메인이 체크포인트와 실제 Git을 대조해 인수 확인을 할 때까지 새 배정·승인·통합이 정지됩니다. 승인 장부 범위 밖 행동은 수행되지 않습니다.';
    case 'mainlimit': return '지금 메인이 한도로 더 일하지 못한다고 보고합니다. 마지막 인계문 없이 저장된 상태로 새 메인(' + (ui.state.main.agent === 'codex' ? 'claude' : 'codex') + ')을 실행해 복구합니다. 진행 중인 구현 에이전트는 중단하지 않습니다.';
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

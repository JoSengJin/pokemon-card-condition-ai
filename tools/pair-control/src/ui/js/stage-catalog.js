export const STAGES = [
  { key: 'prepare', label: '준비', desc: '계약 커밋·작업 폴더·실행 환경. 시작하면 이 작업이 허용 파일을 점유합니다.' },
  { key: 'build', label: '구현', desc: '에이전트가 작업 폴더에서 코딩·커밋합니다. 수동 모드는 에이전트 세션에서 진행하고 끝나면 "작업 완료"를 누릅니다.' },
  { key: 'gitcheck', label: 'Git 검사', desc: '브랜치·커밋·계약 불변·허용 파일 범위만 봅니다. 코드가 맞는지는 검사하지 않습니다.' },
  { key: 'tests', label: '작업 테스트', desc: '계약의 검사 명령을 실행기가 따로 실행합니다. 미실행·이전 SHA 결과는 통과가 아닙니다.' },
  { key: 'review', label: '리뷰', desc: '선택 단계. 다른 에이전트가 고정 SHA 묶음을 별도로 검토합니다. 결과는 참고이며 승인을 대신하지 않습니다.' },
  { key: 'handoff', label: '메인 인계', desc: '메인 에이전트에게 결과를 넘기고 확인받습니다. 안내문을 메인에게 붙여 넣거나 "인계 + 자동 확인"을 쓰며, 자동 확인이 approve가 아니면 사람이 확인 완료를 눌러야 다음 단계로 갑니다.' },
  { key: 'approve', label: '사람 승인', desc: '앞 단계가 모두 끝난 뒤에만 열립니다. diff와 검사 결과를 보고 전체 SHA를 승인하거나 거절합니다.' },
  { key: 'integrate', label: '통합', desc: '승인한 SHA를 다시 확인한 뒤 통합 checkout에서 ./develop 잠금 안으로 cherry-pick 합니다.' },
  { key: 'postcheck', label: '통합 후 검사', desc: '통합 checkout에서 계약의 통합 후 검사를 실행합니다. 지정이 없으면 미실행으로 남습니다.' },
  { key: 'push', label: '푸시', desc: '통합 브랜치를 원격에 올립니다. 취소할 수 없으므로 점검→SHA 입력→푸시→원격 확인 순서입니다.' },
];

export const OCCUPYING_STATUSES = ['starting', 'running', 'manual_working', 'collecting', 'cancelling', 'orphan_running', 'exit_observed', 'unknown',
  'review_pending', 'approved', 'integrating', 'integration_refused', 'integration_conflict', 'integration_blocked'];

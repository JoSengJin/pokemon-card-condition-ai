export const STATUS = {
  assigned: ['배정됨', 'muted'], blocked: ['시작 차단', 'warn'], starting: ['시작 중', 'info'],
  running: ['에이전트 실행 중', 'info'], collecting: ['결과 수집 중', 'info'], cancelling: ['중단 중', 'warn'], cancelled: ['중단됨', 'muted'],
  failed: ['에이전트 실패', 'bad'], orphan_running: ['재시작 전 프로세스 실행 중', 'warn'], exit_observed: ['재시작 후 종료 관찰', 'warn'],
  unknown: ['결과 불명', 'bad'], abandoned: ['결과 불명 확정', 'muted'],
  manual_working: ['수동 작업 중', 'info'], review_pending: ['검토 단계', 'warn'], approved: ['승인됨', 'warn'], rejected: ['거절됨', 'muted'],
  integrating: ['통합 중', 'info'], integrated: ['통합 완료', 'ok'], integrated_check_failed: ['통합 후 검사 실패', 'bad'],
  integration_refused: ['통합 거절', 'bad'], integration_conflict: ['통합 충돌', 'bad'], integration_blocked: ['통합 대기', 'warn'],
};

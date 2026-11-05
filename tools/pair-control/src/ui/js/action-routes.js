export const ACTIONS = {
  start: { p: 'start', n: '시작' }, env: { p: 'recheck-env', n: '준비 상태 확인' }, cancel: { p: 'cancel', n: '중단' },
  finish: { p: 'finish-manual', n: '작업 완료' }, apply: { p: 'apply-exit', n: '결과 반영' }, ack: { p: 'ack-unknown', n: '결과 불명 확정' },
  recollect: { p: 'recollect', n: '다시 수집' }, checks: { p: 'run-checks', n: '작업 테스트 실행' }, review: { p: 'review', n: '리뷰 작업' },
  prompt: { p: 'start-prompt', n: '시작 프롬프트' }, handoff: { p: 'handoff', n: '인계' }, hshow: { p: 'handoff-text', get: true, n: '인계 안내문' },
  handoffauto: { p: 'handoff', n: '인계 + 자동 확인' }, hconfirm: { p: 'handoff-confirm', n: '메인 확인' }, hcancel: { p: 'handoff-cancel', n: '인계 취소' }, diff: { p: 'diff', get: true, n: 'diff' },
  approve: { p: 'approve', n: '승인' }, reject: { p: 'reject', n: '거절' }, integrate: { p: 'integrate', n: '통합' }, rereview: { p: 'rereview', n: '재검토' },
  venv: { p: 'create-venv', n: '환경 만들기' }, unapprove: { p: 'unapprove', n: '승인 취소' }, archive: { p: 'archive', n: '보관' }, unarchive: { p: 'archive', n: '보관 해제' },
  discard: { p: 'discard', n: '폐기' }, archivefin: { g: 'archive-finished', n: '끝난 작업 보관' },
  mainhandover: { g: 'main/handover', n: '메인 교대 실행' }, mainlimit: { g: 'main/handover', n: '한도 소진 교대' }, mainclear: { g: 'main/limit-clear', n: '한도 풀림 확인' },
  apprgrant: { g: 'main/approvals', n: '승인 기록' }, apprrevoke: { g: 'main/approvals/revoke', n: '승인 철회' },
  pushcheck: { g: 'push/preflight', n: '푸시 점검' }, pushack: { g: 'push/ack', n: '오탐 확인' }, push: { g: 'push/run', n: '푸시' },
  verify: { g: 'push/verify', n: '원격 확인' }, revert: { g: 'push/revert-prepare', n: '되돌림 준비' },
  maincheck: { g: 'main/blockers', get: true, n: '이양 안전 확인' }, mainswap: { g: 'main/swap', n: '메인 이양' },
  limitclear: { g: 'limit/clear', n: '한도 해제' }, probe: { g: 'probes', n: 'CLI 확인' },
};

export const STAY = new Set(['mainhandover', 'mainlimit', 'mainclear', 'apprgrant', 'apprrevoke', 'prompt', 'hshow', 'diff', 'archive', 'unarchive', 'discard', 'archivefin']);

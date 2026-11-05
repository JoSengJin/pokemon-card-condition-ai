// 공개 API: 화면 책임별 구현을 직접 내보낸다.
export { STAGES, OCCUPYING_STATUSES } from './stage-catalog.js';
export { testState, reviewState, handoffState, pushStateOf } from './stage-evidence.js';
export { stagesOf, venvMissing } from './stage-state.js';
export { gate, currentKey } from './stage-gate.js';

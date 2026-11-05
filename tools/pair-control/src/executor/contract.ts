// 계약의 공개 API. 경로·검사·작업 스키마·충돌 책임별 구현을 내보낸다.
export { AGENTS, MODES, type Agent, MOCK_SCENARIOS, FORBIDDEN_PREFIXES, FORBIDDEN_FILES, SHARED_CONFIG, DEVELOP_LOCK_PREFIXES, CHECK_EXECUTABLES, CHECK_PLACEHOLDERS, ENV_PROFILES } from './contractConstants.ts';
export { CheckSpec, type CheckSpecT } from './contractCheckSchema.ts';
export { TaskInput, type TaskInputT } from './contractTaskSchema.ts';
export { isForbidden, pathsOverlap, isAllowed } from './contractPaths.ts';
export { effectiveGroups, needsDevelopLock, type ConflictReason, conflicts } from './contractGroups.ts';

import { logEntry } from './log-entry.js';

export const enc = encodeURIComponent;

export const LIVE = ['running', 'cancelling'];

export const LOG_STAGES = ['build', 'tests', 'review', 'postcheck'];

export const EMPTY = {
  build: '(아직 시작 전 — 시작하면 에이전트 출력이 여기에 흐릅니다)',
  tests: '(아직 실행 전 — "작업 테스트 실행"을 누르면 명령별 출력이 여기에 흐릅니다)',
  review: '(리뷰 전 — 리뷰를 실행하면 리뷰 출력이 여기에 흐릅니다)',
  postcheck: '(통합 전 — 통합 후 검사가 실행되면 출력이 여기에 흐릅니다)',
};

export function logTarget(t, key, ui) {
  if (!LOG_STAGES.includes(key)) return null;
  const e = t.exec, r = t.review;
  const list = key === 'build' && e ? [logEntry(e.execId, '에이전트 출력', 'execs/' + enc(e.execId) + '/log?from=', LIVE.includes(e.status), e.exitCode, e.startedAt, e.endedAt, e.pid)]
    : key === 'tests' ? ((t.verification && t.verification.items) || []).filter((i) => i.execId).map((i) => logEntry(i.execId, i.name, 'execs/' + enc(i.execId) + '/log?from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt))
    : key === 'review' && r && r.execId ? [logEntry(r.execId, '리뷰 출력', 'execs/' + enc(r.execId) + '/log?from=', r.status === 'running', null, r.startedAt, r.endedAt)]
    : key === 'postcheck' ? (((t.integration && t.integration.postChecks) || []).filter((i) => i.logPath).map((i) => logEntry('post:' + i.id, i.name, 'tasks/' + enc(t.taskId) + '/post-log?check=' + enc(i.id) + '&from=', i.status === 'running', i.exitCode, i.startedAt, i.endedAt)))
    : [];
  if (!list.length) {
    const manual = key === 'build' && t.mode === 'manual';
    return { empty: manual ? '(수동 모드는 에이전트 세션의 출력을 도구가 받지 못합니다 — 대신 아래 "작업 폴더 활동"을 보여 줍니다)' : key === 'postcheck' && t.integration && t.integration.postStatus === 'not_run' ? '(계약에 통합 후 검사가 없어 실행하지 않았습니다)' : EMPTY[key], list: [], live: false };
  }
  const sel = list.find((x) => x.id === ui.keep.logSel) || list.find((x) => x.live) || list[list.length - 1];
  return { ...sel, list };
}

// 새 메인 세션에 줄 입력 묶음(체크포인트·요청문)과, 새 메인이 돌려준 인수 확인 결과의 파싱·대조.
// 별도 프로세스는 이전 메인의 대화 기억을 승계하지 않으므로 입력 근거·승인 범위·출력 규약을 전부 명시해서 전달한다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { liveHead } from './mainCheckpoint.ts';
import type { Executor } from './executor.ts';
import type { MainAction, MainSession } from './mainTypes.ts';

export const tokenHash = (token: string) => crypto.createHash('sha256').update(token).digest('hex');

function requestText(s: MainSession, token: string, approvedActions: string[]): string {
  return `# 새 메인(${s.agent}) 인수 요청 — 세대 ${s.generation}

당신은 pair-control의 새 메인입니다. 이전 메인(${s.from})의 대화 기억은 전달되지 않습니다. 이 폴더의 checkpoint.json만이 입력 근거입니다.
이 프로세스는 읽기 전용이며 파일 수정·학습·추론·외부 AI 호출·push를 하지 않습니다.

## 할 일
1. checkpoint.json을 읽고, 각 작업의 worktree·branch가 가리키는 실제 Git 헤드(\`git rev-parse refs/heads/<branch>\`)와 liveHead·headSha가 같은지 대조합니다. 다르면 같은 척하지 말고 관찰한 값을 그대로 적습니다.
2. inheritedExecutions(진행 중 실행)는 중단하지 않고 담당만 인수합니다. doNotRetry가 true인 작업·push는 확인 전에 다시 실행하지 않습니다.
3. nextActionCandidates와 승인 장부(approvals) 범위 안에서 다음 행동을 고릅니다. 승인된 행동 종류: ${approvedActions.join(', ') || '(없음)'}.
   범위 밖 행동, force push, 이력 재작성, 승인 범위 확대는 제안하지 않습니다.

## 출력 규약 (마지막 줄에 JSON 한 개만)
{"session_id":"${s.id}","generation":${s.generation},"token":"${token}","checkpoint_hash":"${s.checkpointHash}","observed":{"heads":{"<taskId>":"<관찰한 전체 SHA>"}},"actions":[{"id":"<고유 행동 ID>","type":"approve_task|integrate_task|assign_task|note","taskId":"<작업>","sha":"<승인할 전체 SHA>"}]}

- observed.heads에는 checkpoint.json의 모든 작업을 적습니다. 도구가 실제 Git과 다시 대조하며, 하나라도 다르면 인수를 거부합니다.
- 행동 ID는 중복되면 두 번째부터 무시됩니다. 행동이 필요 없으면 "actions":[] 로 두고 이유를 앞 줄에 적습니다.
`;
}

/** 입력 묶음 폴더(checkpoint.json + TAKEOVER_REQUEST.md)를 만들고 새 메인에게 줄 프롬프트를 돌려준다. */
export function writeBundle(ex: Executor, s: MainSession, token: string, approvedActions: string[]) {
  const bundleDir = path.join(ex.cfg.stateDir, 'main-sessions', s.id);
  fs.mkdirSync(bundleDir, { recursive: true });
  fs.copyFileSync(s.checkpointFile, path.join(bundleDir, 'checkpoint.json'));
  fs.writeFileSync(path.join(bundleDir, 'TAKEOVER_REQUEST.md'), requestText(s, token, approvedActions));
  return { bundleDir, prompt: 'TAKEOVER_REQUEST.md를 읽고 지시대로 수행한 뒤 마지막 줄에 결과 JSON 한 개를 출력하세요. 파일을 수정하지 마세요.' };
}

export interface TakeoverResult { session_id?: string; generation?: number; token?: string; checkpoint_hash?: string; observed?: { heads?: Record<string, string> }; actions?: MainAction[] }

/** 실행 로그의 마지막 줄부터 거슬러 올라가며 session_id를 가진 JSON 객체를 찾는다. */
export function parseResult(logText: string): TakeoverResult | null {
  for (const line of logText.trim().split('\n').reverse()) {
    const l = line.replace(/^\[stdout\]\s*/, '').trim();
    if (!l.startsWith('{')) continue;
    try { const j = JSON.parse(l); if (j && typeof j === 'object' && 'session_id' in j) return j; } catch { /* next */ }
  }
  return null;
}

/** 인수 확인 대조: 세션·세대·토큰·체크포인트 해시가 맞고, 관찰한 헤드가 실제 Git과 같아야 한다. 어긋난 항목을 모두 돌려준다(빈 배열이면 확인됨). */
export async function verifyAck(ex: Executor, s: MainSession, r: TakeoverResult, tasks: { taskId: string }[]): Promise<string[]> {
  const bad: string[] = [];
  if (r.session_id !== s.id) bad.push('세션 ID 불일치');
  if (r.generation !== s.generation) bad.push(`세대 불일치(${r.generation} ≠ ${s.generation})`);
  if (tokenHash(String(r.token ?? '')) !== s.tokenHash) bad.push('세션 토큰 불일치');
  if (r.checkpoint_hash !== s.checkpointHash) bad.push('체크포인트 해시 불일치');
  const seen = r.observed?.heads ?? {};
  for (const { taskId } of tasks) {
    const t = ex.state.tasks[taskId];
    const actual = t ? await liveHead(t) : null;
    if (!seen[taskId]) bad.push(`${taskId}: 관찰한 헤드 없음`);
    else if (seen[taskId] !== actual) bad.push(`${taskId}: 관찰한 헤드가 실제 Git과 다름`);
  }
  return bad;
}

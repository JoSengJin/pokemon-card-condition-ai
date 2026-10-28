// 현재 메인에게 줄 턴 입력 묶음: 최신 체크포인트 + 이벤트별 근거(인계 문서, diff 파일) + 요청문.
// 이전 대화 기억은 전달되지 않으므로 목표·승인 범위·출력 규약을 전부 적는다. diff 해시는 일부러 주지 않는다 — 새 메인이 diff 파일을 직접 읽고 계산해야 한다.
import fs from 'node:fs';
import path from 'node:path';
import * as G from './git.ts';
import type { Executor } from './executor.ts';
import type { MainTurn, PipelineEvent } from './mainTypes.ts';

/** 이벤트 하나의 근거 행(diff 파일은 입력 묶음 폴더에 쓴다). 새 메인이 직접 읽고 계산해야 하므로 diff 해시는 넣지 않는다. */
export async function eventRow(ex: Executor, e: PipelineEvent, dir: string) {
  const t = ex.state.tasks[e.taskId];
  if (!t) return { ...e, task: null };
  const r = t.result, base = { key: e.key, kind: e.kind, taskId: e.taskId, sha: e.sha, implementer: t.agent, branch: t.branch, allowedFiles: t.allowedFiles, contractPath: t.contractPath };
  if (e.kind === 'result_ready' && r?.headSha) {
    fs.mkdirSync(path.join(dir, 'diffs'), { recursive: true });
    fs.writeFileSync(path.join(dir, 'diffs', `${t.taskId}.diff`), (await G.git(t.worktree, 'diff', '--binary', t.baseSha, r.headSha)).stdout);
    const handoff = t.handoff && fs.existsSync(t.handoff.file) ? fs.readFileSync(t.handoff.file, 'utf8') : '';
    return { ...base, changedFiles: r.changedFiles, diffFile: `diffs/${t.taskId}.diff`, handoff, verification: t.verification?.status, mustBeIndependent: t.agent === ex.mainAgent };
  }
  if (e.kind === 'integrated') return { ...base, integrationHead: await G.revParse(ex.cfg.integration.checkout, 'HEAD'), postStatus: t.integration?.postStatus };
  return base;
}

function requestText(t: MainTurn, token: string, approved: string[]): string {
  return `# 메인 턴(${t.agent}) — 세대 ${t.generation}

당신은 pair-control의 현재 메인입니다. 이전 대화 기억은 없습니다. 이 폴더(checkpoint.json, EVENTS.json, diffs/)만이 근거입니다.
이 프로세스는 읽기 전용이며 파일 수정·학습·추론·외부 AI 호출·push를 직접 하지 않습니다. 아래 JSON 한 개를 제안하면 도구가 승인 범위·현재 상태를 다시 검사한 뒤에만 실행합니다.

## 할 일
1. checkpoint.json의 각 작업이 가리키는 실제 Git 헤드를 대조해 observed.heads에 적습니다(다르면 관찰한 값 그대로).
2. EVENTS.json의 이벤트마다 다음만 제안합니다. 승인된 행동 종류: ${approved.join(', ') || '(없음)'}.
   - result_ready: diffs/<작업>.diff를 실제로 읽고 계약(allowedFiles)과 대조합니다. 문제가 없으면 순서대로
     confirm_handoff(taskId, sha=이벤트 sha, reviewedFiles=변경 파일 전체, note=검토한 내용, diffHash=그 diff 파일의 sha256) → approve_task(taskId, sha) → integrate_task(taskId).
     diffHash는 \`shasum -a 256 diffs/<작업>.diff\`로 직접 계산합니다(주어지지 않음). mustBeIndependent=true면 구현 에이전트와 같은 에이전트라 확인할 수 없으므로 행동을 내지 말고 note로 이유를 적습니다.
   - approved: integrate_task만 제안합니다.
   - integrated: 푸시 가능하면 push_main(target=브랜치 이름, sha=이벤트의 integrationHead 전체 SHA)을 제안합니다.
   문제가 있으면 행동 없이 \`note\` 행동으로 이유를 적습니다. 범위 밖 행동·force push·이력 재작성·승인 범위 확대는 제안하지 않습니다.

## 출력 규약 (마지막 줄에 JSON 한 개만)
{"session_id":"${t.id}","generation":${t.generation},"token":"${token}","checkpoint_hash":"${t.checkpointHash}","observed":{"heads":{"<taskId>":"<관찰한 전체 SHA>"}},"actions":[{"id":"<고유 행동 ID>","type":"confirm_handoff|approve_task|integrate_task|push_main|note","taskId":"<작업>","sha":"<전체 SHA>","reviewedFiles":["<파일>"],"note":"<검토 메모>","diffHash":"<sha256>"}]}

- 행동 ID는 고유해야 하며 중복은 무시됩니다. 같은 이벤트에 대한 턴은 이번 한 번뿐입니다.
`;
}

export const turnDir = (ex: Executor, t: MainTurn) => path.join(ex.cfg.stateDir, 'main-sessions', t.id);

export function writeTurnBundle(ex: Executor, t: MainTurn, token: string, rows: unknown[], approved: string[]) {
  const dir = turnDir(ex, t);
  fs.copyFileSync(t.checkpointFile, path.join(dir, 'checkpoint.json'));
  fs.writeFileSync(path.join(dir, 'EVENTS.json'), JSON.stringify({ turn: t.id, events: rows }, null, 2));
  fs.writeFileSync(path.join(dir, 'TURN_REQUEST.md'), requestText(t, token, approved));
  return { bundleDir: dir, prompt: 'TURN_REQUEST.md를 읽고 지시대로 수행한 뒤 마지막 줄에 결과 JSON 한 개를 출력하세요. 파일을 수정하지 마세요.' };
}

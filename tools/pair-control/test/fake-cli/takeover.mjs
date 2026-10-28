// 가짜 CLI 공용: 새 메인 인수 요청(TAKEOVER_REQUEST.md)에 응답한다. 모델 요청·네트워크 없음.
// 시나리오는 이 파일 옆의 .fake-takeover(JSON)로 정한다(자식 프로세스 환경은 정리되어 전달되므로 환경변수를 쓰지 않는다).
//   mode: ok(기본) | badhead(관찰한 헤드가 틀림) | limit(한도 문구 후 종료) | exit1 | nojson | slow(지연 후 정상)
//   actions: 새 메인이 낼 행동 목록(그대로 출력). delayMs: 응답 지연.
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function isTakeover(prompt) { return prompt.includes('TAKEOVER_REQUEST.md'); }

export async function respond(dir) {
  const flag = path.join(path.dirname(fileURLToPath(import.meta.url)), '.fake-takeover');
  const sc = fs.existsSync(flag) ? JSON.parse(fs.readFileSync(flag, 'utf8')) : {};
  const mode = sc.mode ?? 'ok';
  const req = fs.readFileSync(path.join(dir, 'TAKEOVER_REQUEST.md'), 'utf8');
  const cp = JSON.parse(fs.readFileSync(path.join(dir, 'checkpoint.json'), 'utf8'));
  console.log('[fake-main] takeover request read; tasks=' + cp.tasks.length);
  if (sc.delayMs) await new Promise((r) => setTimeout(r, sc.delayMs));
  if (mode === 'limit') { console.log("You've hit your usage limit. Try again later."); process.exit(1); }
  if (mode === 'exit1') process.exit(1);
  if (mode === 'nojson') { console.log('인수했습니다(JSON 없음)'); return; }
  const tpl = JSON.parse(req.split('\n').find((l) => l.startsWith('{"session_id"')));
  const heads = {};
  for (const t of cp.tasks) {
    try { heads[t.taskId] = mode === 'badhead' ? '0'.repeat(40) : execFileSync('git', ['rev-parse', `refs/heads/${t.branch}`], { cwd: t.worktree }).toString().trim(); } catch { heads[t.taskId] = ''; }
  }
  console.log(JSON.stringify({ session_id: tpl.session_id, generation: tpl.generation, token: tpl.token, checkpoint_hash: tpl.checkpoint_hash, observed: { heads }, actions: sc.actions ?? [] }));
}

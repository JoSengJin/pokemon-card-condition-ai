// 가짜 CLI 공용: 새 메인 인수 요청(TAKEOVER_REQUEST.md)에 응답한다. 모델 요청·네트워크 없음.
// 시나리오는 이 파일 옆의 .fake-takeover(JSON)로 정한다(자식 프로세스 환경은 정리되어 전달되므로 환경변수를 쓰지 않는다).
//   mode: ok(기본) | badhead(관찰한 헤드가 틀림) | limit(한도 문구 후 종료) | exit1 | nojson | slow(지연 후 정상)
//   actions: 새 메인이 낼 행동 목록(그대로 출력). delayMs: 응답 지연.
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function isTakeover(prompt) { return prompt.includes('TAKEOVER_REQUEST.md') || prompt.includes('TURN_REQUEST.md'); }

// 메인 턴(TURN_REQUEST.md) 응답. .fake-takeover의 turn 키로 정한다:
//   mode: ok(기본) | limit | exit1 | nojson | badhead | none(행동 없음)   delayMs: 응답 지연   omit: 빼 놓을 행동 종류   badDiffHash: 틀린 diff 해시   forceConfirm: 독립 확인이 아니어도 확인 제안(도구의 거부를 시험)   extra: 덧붙일 행동
function turnActions(dir, sc) {
  const out = [];
  const ev = JSON.parse(fs.readFileSync(path.join(dir, 'EVENTS.json'), 'utf8')).events;
  const id = (t, e) => `${t}-${e.taskId}-${String(e.sha).slice(0, 8)}`;
  for (const e of ev) {
    if (e.kind === 'result_ready') {
      if (e.mustBeIndependent && !sc.forceConfirm) { out.push({ id: id('note', e), type: 'note', note: '구현 에이전트와 같아 확인 불가' }); continue; }
      const h = crypto.createHash('sha256').update(fs.readFileSync(path.join(dir, e.diffFile))).digest('hex');
      out.push({ id: id('confirm', e), type: 'confirm_handoff', taskId: e.taskId, sha: e.sha, reviewedFiles: e.changedFiles, note: '합성 검토: diff를 읽고 계약과 대조함', diffHash: sc.badDiffHash ? '0'.repeat(64) : h });
      out.push({ id: id('approve', e), type: 'approve_task', taskId: e.taskId, sha: e.sha });
      out.push({ id: id('integrate', e), type: 'integrate_task', taskId: e.taskId });
    } else if (e.kind === 'approved') out.push({ id: id('integrate', e), type: 'integrate_task', taskId: e.taskId });
    else if (e.kind === 'integrated') out.push({ id: id('push', e), type: 'push_main', target: 'main', sha: e.integrationHead });
  }
  return [...out.filter((a) => !(sc.omit ?? []).includes(a.type)), ...(sc.extra ?? [])];
}

async function respondTurn(dir, flag) {
  const sc = (fs.existsSync(flag) ? JSON.parse(fs.readFileSync(flag, 'utf8')) : {}).turn ?? {};
  const mode = sc.mode ?? 'ok';
  const req = fs.readFileSync(path.join(dir, 'TURN_REQUEST.md'), 'utf8');
  const cp = JSON.parse(fs.readFileSync(path.join(dir, 'checkpoint.json'), 'utf8'));
  const tpl = JSON.parse(req.split('\n').find((l) => l.startsWith('{"session_id"')));
  fs.appendFileSync(path.join(path.dirname(flag), '.fake-turn-log'), JSON.stringify({ turn: tpl.session_id, generation: tpl.generation, mode }) + '\n');
  console.log('[fake-main] turn request read; tasks=' + cp.tasks.length);
  if (sc.delayMs) await new Promise((r) => setTimeout(r, sc.delayMs));
  if (mode === 'limit') { console.log("You've hit your usage limit. Try again later."); process.exit(1); }
  if (mode === 'exit1') process.exit(1);
  if (mode === 'nojson') { console.log('턴 처리(JSON 없음)'); return; }
  const heads = {};
  for (const t of cp.tasks) {
    try { heads[t.taskId] = mode === 'badhead' ? '0'.repeat(40) : execFileSync('git', ['rev-parse', `refs/heads/${t.branch}`], { cwd: t.worktree }).toString().trim(); } catch { heads[t.taskId] = ''; }
  }
  const actions = mode === 'none' ? [] : turnActions(dir, sc);
  console.log(JSON.stringify({ session_id: tpl.session_id, generation: tpl.generation, token: tpl.token, checkpoint_hash: tpl.checkpoint_hash, observed: { heads }, actions }));
}

export async function respond(dir) {
  const flag = path.join(path.dirname(fileURLToPath(import.meta.url)), '.fake-takeover');
  if (fs.existsSync(path.join(dir, 'TURN_REQUEST.md'))) return respondTurn(dir, flag);
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

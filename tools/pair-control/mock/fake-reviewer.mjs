#!/usr/bin/env node
// fake 리뷰 CLI. 모델 요청 없이 리뷰 묶음을 읽고 review-result.json을 쓴다(리뷰 연결 경로 검증용).
import fs from 'node:fs';
import path from 'node:path';

const arg = (name) => { const i = process.argv.indexOf(`--${name}`); return i > 0 ? process.argv[i + 1] : undefined; };
const scenario = arg('scenario') ?? 'approve';
const bundle = arg('bundle') ?? process.cwd();
const meta = JSON.parse(fs.readFileSync(path.join(bundle, 'meta.json'), 'utf8'));
const out = path.join(bundle, 'review-result.json');
const write = (o) => fs.writeFileSync(out, JSON.stringify(o, null, 2));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

console.log(`[fake-reviewer] task=${meta.taskId} sha=${meta.sha} scenario=${scenario} · 모델 요청 없음`);
for (const f of ['REVIEW_REQUEST.md', 'contract.md', 'diff.patch', 'checks.json']) console.log(`[fake-reviewer] 읽음 ${f} (${fs.statSync(path.join(bundle, f)).size} bytes)`);

switch (scenario) {
  case 'approve': write({ verdict: 'approve', sha: meta.sha, summary: '계약 범위 안의 변경, 작업 테스트 통과 확인(fake)' }); break;
  case 'changes_requested': write({ verdict: 'changes_requested', sha: meta.sha, summary: '완료 조건 미충족(fake)' }); break;
  case 'insufficient_evidence': write({ verdict: 'insufficient_evidence', sha: meta.sha, summary: '작업 테스트 미실행으로 판단 근거 부족(fake)' }); break;
  case 'slow-approve': await sleep(1500); write({ verdict: 'approve', sha: meta.sha, summary: 'fake' }); break;
  case 'wrong-sha': write({ verdict: 'approve', sha: '0'.repeat(40), summary: '다른 SHA를 검토함(fake)' }); break;
  case 'garbage': fs.writeFileSync(out, '통과! LGTM'); break;
  case 'fail': console.error('[fake-reviewer] 실패'); process.exit(5);
  case 'hang': setInterval(() => console.log('[fake-reviewer] heartbeat'), 500); break;
  default: console.error(`unknown scenario ${scenario}`); process.exit(2);
}

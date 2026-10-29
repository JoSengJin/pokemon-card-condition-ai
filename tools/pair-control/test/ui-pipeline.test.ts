// 연속 처리 상태의 화면 연결: (1) 서버가 주는 요약 데이터, (2) 실제 관제 화면(page.html + 화면 모듈)이 브라우저에서 그리는 내용.
// 합성 상태(실제 모델·원격 호출 없음)를 실제 snapshot() API 형식으로 서빙해 화면 렌더를 확인한다. 브라우저(playwright)를 쓸 수 없으면 (2)는 건너뛰고 건너뜀으로 보고한다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import http from 'node:http';
import { createRequire } from 'node:module';
import path from 'node:path';
import { test } from 'node:test';
import { pipelineView } from '../src/executor/pipelineView.ts';
import { mainRuntimeView, snapshot } from '../src/runtime.ts';
import { setup, toolRoot } from './helpers.ts';
import { seed } from './ui-seed.ts';

test('E. 서버 요약: 메인 인수·현재 턴·개별 행동·보류/결과 불명 사유·원격 push 완료를 따로 담는다', async () => {
  const e = setup();
  try {
    await seed(e);
    const v = mainRuntimeView(e.ex, pipelineView(e.ex)).pipeline;
    assert.equal(v.takeover?.acked, true); assert.equal(v.takeover?.agent, 'claude');
    assert.equal(v.currentTurn?.id, 't2', '진행 중인 턴이 현재 턴'); assert.equal(v.currentTurn?.inFlight, true);
    const done = v.turns.find((t) => t.id === 't1')!;
    assert.deepEqual(done.actions.map((a) => a.ok), [true, false]); assert.equal(done.actionsOk, 1);
    assert.ok(v.heldReasons.some((h) => /조건 미확정/.test(h.reason)) && v.heldReasons.some((h) => /결과 불명/.test(h.reason)));
    assert.deepEqual(v.tasks.map((t) => [t.taskId, t.pipelineDone]), [['task-a', true], ['task-b', false]], '원격 push 검증된 작업만 파이프라인 완료');
  } finally { e.cleanup(); }
});

type Page = { goto(u: string): Promise<unknown>; waitForFunction(f: string, o?: unknown): Promise<unknown>; evaluate<T>(f: string): Promise<T>; innerText(sel: string): Promise<string>; screenshot(o: { path: string }): Promise<unknown>; on(ev: string, cb: (e: Error) => void): void };

test('E. 실제 관제 화면(브라우저)이 연속 처리 영역을 그린다', { timeout: 90_000 }, async (t) => {
  let chromium: { launch(o?: unknown): Promise<{ newPage(): Promise<Page>; close(): Promise<void> }> };
  try { chromium = createRequire(import.meta.url)('playwright').chromium; } catch { return t.skip('playwright 없음 — 화면 렌더 미확인'); }
  const e = setup();
  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url ?? '/', 'http://x');
    const send = (code: number, type: string, body: string) => { res.writeHead(code, { 'content-type': type }); res.end(body); };
    if (u.pathname === '/pair') return send(200, 'text/html; charset=utf-8', fs.readFileSync(path.join(toolRoot, 'src/ui/page.html'), 'utf8'));
    if (u.pathname.startsWith('/pair/static/')) return send(200, 'text/javascript; charset=utf-8', fs.readFileSync(path.join(toolRoot, 'src/ui/js', path.basename(u.pathname)), 'utf8'));
    if (u.pathname === '/pair/api/state') return send(200, 'application/json', JSON.stringify({ ok: true, data: await snapshot() }));
    return send(200, 'application/json', JSON.stringify({ ok: true, data: null }));
  });
  let browser: Awaited<ReturnType<typeof chromium.launch>> | null = null;
  try {
    await seed(e);
    await new Promise<void>((r) => server.listen(0, '127.0.0.1', r));
    browser = await chromium.launch();
    const page = await browser.newPage(), errors: string[] = [];
    page.on('pageerror', (err) => errors.push(err.message));
    await page.goto(`http://127.0.0.1:${(server.address() as { port: number }).port}/pair`);
    await page.waitForFunction("document.getElementById('pipeRt') && document.getElementById('pipeRt').innerText.includes('현재 턴')");
    await page.evaluate("document.getElementById('mainBox').open = true");
    const text = await page.innerText('#pipeRt');
    for (const want of ['교대 후 연속 처리', '메인 인수: codex → claude', '인수 확인됨', '현재 턴', '모델 응답 대기', '✓ confirm_handoff', '자기 확인(독립 검토 아님)', '✗ approve_task', '보류·결과 불명 사유', '승인 조건 미확정', '[결과 불명]', '파이프라인 완료(원격 push 검증됨)', '완료 아님(원격 push 검증 전)']) assert.ok(text.includes(want), `화면에 없음: ${want}\n${text}`);
    assert.deepEqual(errors, [], '화면 스크립트 오류 없음');
    if (process.env.PAIR_UI_SHOT) await page.screenshot({ path: process.env.PAIR_UI_SHOT });
  } finally { await browser?.close(); server.close(); e.cleanup(); }
});

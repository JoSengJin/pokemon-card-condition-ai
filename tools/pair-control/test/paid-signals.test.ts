// 과금 신호 문구 판정: 지침 문서 예시의 "billing"은 오탐으로 보지 않고, 공식 오류 문서의 과금·한도 문구는 놓치지 않는다.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { FreeGuard, type Alert } from '../src/executor/freeGuard.ts';

function scan(text: string) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'paid-signals-'));
  const trips: Alert[] = [], limits: Alert[] = [];
  const g = new FreeGuard(dir, (a) => trips.push(a), (a) => limits.push(a));
  const r = g.scanLog(text, 'exec:test');
  fs.rmSync(dir, { recursive: true, force: true });
  return { r, trips: trips.length, limits: limits.length };
}

test('오탐 방지: 코드·지침 문서 예시의 billing 단어는 서비스를 끄지 않는다 (task-1028-3 리뷰 로그 재현)', () => {
  for (const t of [
    '[stderr] 2. **Orders land on the wrong day** (`billing/close_day.py:L40-52`)',
    '[stderr]    - **What this is:** At midnight this job closes the day and bills all orders of that day.',
    'the billing module reads orders and the billing service closes the day',
  ]) assert.deepEqual(scan(t), { r: null, trips: 0, limits: 0 }, t);
});

test('확실한 과금 신호는 계속 서비스 종료: 공식 Claude Code 오류 문서의 문구 포함', () => {
  for (const t of [
    'Your credit balance is too low to access the Anthropic API',
    "You've hit your monthly spend limit",
    'Usage credits required for 1M context',
    'Billing error: payment method declined',
    'billing is required to continue',
    'Please enable billing for this project',
    'insufficient_quota',
    'payment required',
  ]) assert.equal(scan(t).r, 'paid', t);
});

test('구독 한도 도달은 정지만(서비스 유지): Codex 한도 안내에 크레딧 구매 권유가 섞여도 종료하지 않는다', () => {
  const r = scan("You've hit your usage limit. Visit https://chatgpt.com/codex/settings/usage to purchase more credits or try again at 3:00 PM.");
  assert.deepEqual(r, { r: 'limit', trips: 0, limits: 1 });
});

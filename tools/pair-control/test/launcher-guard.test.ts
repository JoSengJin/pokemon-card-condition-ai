import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';
import { PAID_ENV_KEYS } from '../src/executor/paidSignals.mjs';

test('서버 생성 전 launcher 가드: 설정 없음·기존 알림·과금 환경을 차단하고 깨끗한 설정만 통과한다', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'pair-launcher-'));
  try {
    const config = path.join(dir, 'config.json'), alert = path.join(dir, 'alerts/paid-risk.json');
    const guard = new URL('../scripts/launcher-guard.mjs', import.meta.url).href;
    const source = `Object.defineProperty(process, 'platform', { value: 'linux' }); const { enforceLauncherGuard } = await import(${JSON.stringify(guard)}); enforceLauncherGuard(${JSON.stringify(config)}, ${JSON.stringify(alert)}, false); console.log('passed');`;
    const env = { ...process.env };
    for (const key of PAID_ENV_KEYS) delete env[key];
    const run = () => spawnSync(process.execPath, ['--input-type=module', '-e', source], { env, encoding: 'utf8' });
    assert.equal(run().status, 2, '설정이 없으면 서버 시작 전 종료');
    fs.writeFileSync(config, '{}');
    assert.equal(run().stdout.trim(), 'passed');
    env[PAID_ENV_KEYS[0]] = 'fixture-value-must-not-be-logged';
    const paid = run();
    assert.equal(paid.status, 3); assert.ok(fs.existsSync(alert));
    assert.ok(!paid.stderr.includes(env[PAID_ENV_KEYS[0]]!));
    delete env[PAID_ENV_KEYS[0]];
    assert.equal(run().status, 3, '환경이 사라져도 기존 알림 확인 전 차단 유지');
  } finally { fs.rmSync(dir, { recursive: true, force: true }); }
});

#!/usr/bin/env node
// 브라우저 demo용 합성 저장소·worktree를 .demo/에 만든다(Git 제외 경로). 실제 프로젝트 checkout은 건드리지 않는다.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { makeFixture, writeConfig } from './fixture-lib.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const demo = path.join(root, '.demo');
const port = Number(process.argv[2] ?? 4111);
fs.rmSync(path.join(demo, 'state'), { recursive: true, force: true });
const fx = makeFixture(path.join(demo, 'fx'), root);
fs.mkdirSync(demo, { recursive: true });
// 데모 화면의 "진행률 항목에서 채우기"를 보여 주기 위한 합성 진행률 파일(실제 프로젝트 데이터 아님)
const g = (...a) => execFileSync('git', ['-c', 'user.name=fixture', '-c', 'user.email=fixture@localhost', ...a], { cwd: fx.repo, stdio: 'pipe' });
fs.writeFileSync(path.join(fx.repo, 'development-progress.json'), JSON.stringify({
  criterion_version: 'demo-v0', score: 30, max_score: 100,
  categories: [{ id: 'C', title: '범위별 성능(합성)', weight: 14, milestones: [
    { id: 'C1', title: '엣지(합성)', weight: 7, status: 'pending', earned: 0, completion_criterion: 'FN/(TP+FN)<=5%\n양성·정상 각 20판정단위', evidence: ['src_b/file.txt', 'artifacts/x/REPORT.md'], assessment: '통과한 근거가 없다(합성 예시).' },
    { id: 'C2', title: '모서리(합성)', weight: 7, status: 'verified', earned: 7, completion_criterion: '완료', evidence: [], assessment: '확인됨' },
  ] }],
}, null, 2));
g('add', 'development-progress.json'); g('commit', '-q', '-m', 'demo: synthetic progress file'); g('push', '-q', 'origin', 'main');
writeConfig(path.join(demo, 'config.json'), fx, port);
console.log(JSON.stringify({ config: '.demo/config.json', baseSha: fx.baseSha, worktrees: fx.worktrees }, null, 2));

#!/usr/bin/env node
// 브라우저 demo용 합성 저장소·worktree를 .demo/에 만든다(Git 제외 경로). 실제 프로젝트 checkout은 건드리지 않는다.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { makeFixture, writeConfig } from './fixture-lib.mjs';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const demo = path.join(root, '.demo');
const port = Number(process.argv[2] ?? 4111);
fs.rmSync(path.join(demo, 'state'), { recursive: true, force: true });
const fx = makeFixture(path.join(demo, 'fx'), root);
fs.mkdirSync(demo, { recursive: true });
writeConfig(path.join(demo, 'config.json'), fx, port);
console.log(JSON.stringify({ config: '.demo/config.json', baseSha: fx.baseSha, worktrees: fx.worktrees }, null, 2));

// 구조 측정 도구(scripts/structure-trace.mjs)의 누락·오탐 회귀. 검토에서 확인된 문제를 합성 소스로 고정하고, 실제 저장소 경로 수치도 재현한다.
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { test } from 'node:test';

const tool = path.resolve(import.meta.dirname, '..', 'scripts', 'structure-trace.mjs');
const repoRoot = path.resolve(import.meta.dirname, '..');

/** 합성 프로젝트(root/src/*.ts, 선택적 scripts/structure-edges.json)를 만들어 측정 결과를 돌려준다. */
function measure(sources: Record<string, string>, extra: string[] = [], edges?: unknown) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'structure-'));
  try {
    for (const [f, text] of Object.entries(sources)) { fs.mkdirSync(path.dirname(path.join(root, f)), { recursive: true }); fs.writeFileSync(path.join(root, f), text); }
    if (edges) { fs.mkdirSync(path.join(root, 'scripts'), { recursive: true }); fs.writeFileSync(path.join(root, 'scripts', 'structure-edges.json'), JSON.stringify(edges)); }
    const r = spawnSync(process.execPath, [tool, `--root=${root}`, ...extra], { encoding: 'utf8' });
    return { code: r.status, out: r.stdout ? JSON.parse(r.stdout) : null, err: r.stderr };
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
}
const depthOf = (o: any, start: string) => (o.overStarts.find((r: any) => r.start.endsWith(`:${start}`))?.transitions ?? 0);

test('표준 API의 동기 콜백도 한 전이로 세고, 이벤트 등록 콜백은 독립 진입점으로 측정한다', () => {
  const out = measure({ 'src/a.ts': `function leaf() { return 1; }\nexport function sync() { return [1].map(() => leaf()); }\nexport function schedule() { setInterval(() => leaf(), 1); }\n` }, ['--start=sync']).out;
  assert.equal(out.starts[0].transitions, 2, 'sync→map 콜백→leaf');
  const scheduled = measure({ 'src/a.ts': `function leaf() { return 1; }\nexport function schedule() { setInterval(() => leaf(), 1); }\n` }).out;
  assert.ok(!scheduled.overStarts.length);
  const root = measure({ 'src/a.ts': `function leaf() { return 1; }\nexport function schedule() { setInterval(() => leaf(), 1); }\n` }, ['--start=schedule']).out;
  assert.equal(root.starts[0].transitions, 0, '타이머 등록이 콜백을 동기 호출하지 않음');
});

test('반환된 API 래퍼의 매개변수 호출은 모듈에서 전달한 실제 handler로 이어진다', () => {
  const sources = {
    'src/api.ts': `export function act(fn) { return async function wrapped(c) { return fn(c); }; }\n`,
    'src/routes.ts': `import { act } from './api.ts';\nfunction service() { return 1; }\nexport const route = act(async () => service());\n`,
  };
  assert.equal(measure(sources, ['--start=wrapped']).out.starts[0].transitions, 2, 'wrapped→handler→service');
});

test('객체 속성의 함수 이름은 렉시컬 바인딩이 아니므로 같은 이름 import를 가리지 않는다', () => {
  const sources = {
    'src/service.ts': `export function approve() { return 1; }\n`,
    'src/bind.ts': `import { approve } from './service.ts';\nexport function bind() { return { approve: async () => approve() }; }\n`,
  };
  const out = measure(sources, ['--start=approve']).out;
  assert.ok(out.starts.some((row: any) => row.start === 'bind.ts:approve' && row.transitions === 1));
  assert.deepEqual(out.cycles, [], '객체 속성을 자기 재귀로 잘못 연결하지 않음');
});

test('promisify는 감싼 함수의 출처를 따라가며 프로젝트 함수를 외부로 숨기지 않는다', () => {
  const sources = { 'src/a.ts': `import { promisify } from 'node:util';\nfunction inner(cb) { cb(); }\nconst wrapped = promisify(inner);\nexport function caller() { return wrapped(); }\n` };
  assert.equal(measure(sources, ['--start=caller']).out.starts[0].transitions, 1, 'caller→프로젝트 inner');
  const external = measure({ 'src/a.ts': `import { promisify } from 'node:util';\nimport { execFile } from 'node:child_process';\nconst run = promisify(execFile);\nexport function caller() { return run('git'); }\n` }).out;
  assert.ok(Object.keys(external.external).some((reason) => reason.includes('node:child_process:execFile')));
});

test('직접·상호 재귀는 순환으로 보고하며 --check를 실패시킨다', () => {
  const result = measure({ 'src/a.ts': `export function a() { return b(); }\nfunction b() { return a(); }\n` }, ['--check']);
  assert.equal(result.code, 1); assert.ok(result.out.cycles.length > 0);
});

test('getter 읽기도 실제 함수 호출 전이로 센다', () => {
  const result = measure({ 'src/a.ts': `function leaf() { return 1; }\nexport class K { get value() { return leaf(); } }\nexport function read(k: K) { return k.value; }\n` }, ['--start=read']);
  assert.equal(result.out.starts[0].transitions, 2, 'read→getter→leaf');
});

test('함수 정의 수: 익명 콜백·중첩 함수·메서드·.mjs를 모두 세고 7개 초과를 표시한다', () => {
  const body = `export function a() { return [1].map((x) => x).filter((y) => y > 0).some(function (z) { return z; }); }\nconst b = () => { const c = () => 1; return c(); };\nclass K { m() { return 1; } get g() { return 2; } }\n`; // 정의: a + 3콜백 + b + c + m + g = 8
  const { out, code } = measure({ 'src/big.ts': body, 'src/sup.mjs': `export const f = () => 1;\n` }, ['--check']);
  assert.equal(out.perFile['src/big.ts'], 8); assert.equal(out.perFile['src/sup.mjs'], 1);
  assert.deepEqual(out.overFiles.map((o: any) => o.file), ['src/big.ts']); assert.equal(code, 1, '--check는 초과 시 실패');
});

test('프로젝트 메서드 이름이 표준 메서드와 같아도(push) 제외하지 않고, 배열 push는 간선으로 세지 않는다', () => {
  const src = {
    'src/ops.ts': `export class Ops { push(sha: string) { return sha; } }\n`,
    'src/caller.ts': `import { Ops } from './ops.ts';\nexport function viaProject(ops: Ops) { return ops.push('x'); }\nexport function viaArray() { const out: string[] = []; out.push('x'); return out; }\n`,
  };
  assert.equal(measure(src, ['--start=viaProject']).out.starts[0].transitions, 1, 'ops: Ops 타입 주석으로 Ops.push가 확정 간선(이름 때문에 제외하지 않음)');
  const untyped = measure({ ...src, 'src/caller.ts': `export function viaProject(ops) { return ops.push('x'); }\n` }, ['--start=viaProject']);
  assert.equal(untyped.out.starts[0].transitions, 0); assert.equal(untyped.out.unresolvedCount, 1, '타입을 모르면 간선으로 세지 않고 미확인으로 보고');
  assert.equal(measure(src, ['--start=viaArray']).out.starts[0].transitions, 0, '배열 push는 프로젝트 push로 오인하지 않음');
});

test('콜백 매개변수: 호출 지점에서 넘긴 함수가 호출 간선으로 이어진다(runPush의 verify 사례)', () => {
  const src = {
    'src/scope.ts': `export function verifyScope(p: string) { return leaf(p); }\nfunction leaf(p: string) { return p; }\n`,
    'src/push.ts': `export async function runPush(sha: string, verify?: (p: string) => Promise<void>) { await verify?.(sha); }\n`,
    'src/dispatch.ts': `import { runPush } from './push.ts';\nimport { verifyScope } from './scope.ts';\nexport async function pushNow(sha: string) { await runPush(sha, async (p) => { verifyScope(p); }); }\n`,
  };
  const { out } = measure(src, ['--start=pushNow']);
  const r = out.starts[0];
  assert.equal(r.transitions, 4, 'pushNow→runPush→콜백→verifyScope→leaf'); assert.match(r.path, /runPush .*<익명@.*verifyScope.*leaf/);
});

test('프레임워크 호출(run.resume)을 같은 이름의 Executor.resume에 잘못 연결하지 않고 미확인으로 나열한다', () => {
  const src = {
    'src/executor.ts': `export class Executor { private async resume() { return 1; } }\n`,
    'src/runtime.ts': `export async function resumeStep(wf: any) { const run = await wf.createRun({}); return run.resume({}); }\n`,
  };
  const { out } = measure(src, ['--start=resumeStep']);
  assert.equal(out.starts[0].transitions, 0, 'Executor.resume으로 이어지지 않음');
  assert.ok(out.unresolvedCount >= 1, '확정하지 못한 호출은 미확인으로 보고');
});

test('수동 간선은 근거가 있어야 하며 가중치로 깊이에 반영된다', () => {
  const src = { 'src/a.ts': `export function a(cb: () => void) { cb(); }\n`, 'src/b.ts': `export function b() { return 1; }\n` };
  const withEdge = measure(src, ['--start=a'], { edges: [{ from: 'a.ts:a', to: 'b.ts:b', weight: 2, evidence: '합성: 호출 지점에서 b를 넘김' }] });
  assert.equal(withEdge.out.starts[0].transitions, 2);
  const noEvidence = measure(src, ['--start=a'], { edges: [{ from: 'a.ts:a', to: 'b.ts:b' }] });
  assert.notEqual(noEvidence.code, 0);
});

test('실제 저장소: 구조 수정 단계별 측정값(수정 전 6857715 기준 pushNow 7·onMainEnd 12·runPush 5 → 단계 1b 라우팅 평탄화 이후 갱신)', () => {
  const out = JSON.parse(execFileSync(process.execPath, [tool, `--root=${repoRoot}`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }));
  assert.equal(depthOf(out, 'runPush'), 0, 'runPush는 gate 인자로 push 범위를 직접 검증해 4회 이하(초과 목록에 없음)');
  assert.equal(depthOf(out, 'dispatchAction'), 0, 'push·승인·상태 기록 평탄화 뒤 dispatchAction은 4회 이하');
  const direct = JSON.parse(execFileSync(process.execPath, [tool, `--root=${repoRoot}`, '--start=runPush'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] })).starts[0].callees as string[];
  assert.ok(direct.includes('pushFacts.ts:collectPushFacts') && direct.includes('pushAuthorization.ts:verifyAutomaticPush') && direct.includes('pushExecution.ts:executePush'), '수동 호환 경로도 사실 수집→scope→exec 단계 함수를 직접 호출');
  assert.equal(depthOf(out, 'onMainEnd'), 0, '종료 관찰·응답 검증·저장을 각각 4회 이하로 평탄화함');
  assert.ok(Array.isArray(out.unresolved) && out.manualEdges === 11, 'framework 콜백 8개와 HTTP 인자 배열로 전달된 실제 서비스 3개를 연결함');
});


test('반환 객체의 메서드·전달된 콜백·기본 콜백을 실제 호출로 연결한다', () => {
  const src = { 'src/a.ts': `function leaf() { return 1; }
function sink(cb) { return { end() { cb(); } }; }
function bridge(cb) { const writer = sink(cb); writer.end(); }
export function caller() { bridge(() => leaf()); }
export function defaults(cb = () => leaf()) { cb(); }
` };
  const out = measure(src, ['--start=caller']).out;
  assert.equal(out.starts[0].transitions, 4, 'caller→bridge→end→전달 콜백→leaf');
  assert.equal(measure(src, ['--start=defaults']).out.starts[0].transitions, 2);
});

test('생성자 함수 필드와 반환된 리스너를 실제 주입 함수로 연결한다', () => {
  const src = { 'src/a.ts': `function leaf() { return 1; }
function listener() { return function hit() { return leaf(); }; }
export class Guard { constructor(private callback: () => void) {} run() { this.callback(); } }
const guard = new Guard(listener());
export function caller() { guard.run(); }
` };
  const out = measure(src, ['--start=caller']).out;
  assert.equal(out.starts[0].transitions, 3, 'caller→run→hit→leaf');
});

test('프로젝트 객체에 대입한 함수와 계산된 테이블을 이름 추정 없이 연결한다', () => {
  const src = { 'src/a.ts': `function leaf() { return 1; }
export class Executor { ops = {}; }
export function bind(ex: Executor) { ex.ops = { approve: () => leaf() }; }
export function caller(ex: Executor) { const ops = ex.ops; return ops.approve(); }
const panels = { a: () => leaf(), b: () => 0 };
export function render(key) { return panels[key](); }
` };
  assert.equal(measure(src, ['--start=caller']).out.starts[0].transitions, 2);
  assert.equal(measure(src, ['--start=render']).out.starts[0].transitions, 2);
});

test('zod의 parse는 중첩 스키마 검증 함수를 호출하며 외부 경계로 숨기지 않는다', () => {
  const src = { 'src/a.ts': `import { z } from 'zod';
function leaf() { return true; }
const item = z.string().refine(() => leaf());
const schema = z.object({ item });
export function parse(value) { return schema.safeParse(value); }
` };
  assert.equal(measure(src, ['--start=parse']).out.starts[0].transitions, 2, 'parse→refine 콜백→leaf');
});


test('옵션 객체로 전달한 콜백도 여러 서비스 전달 뒤 실제 호출로 이어진다', () => {
  const src = { 'src/a.ts': `function leaf() { return 1; }
function sink(opts) { opts.hit(); }
function bridge(opts) { sink(opts); }
export function caller() { bridge({ hit: () => leaf() }); }
` };
  assert.equal(measure(src, ['--start=caller']).out.starts[0].transitions, 4, 'caller→bridge→sink→hit→leaf');
});


test('실제 workflow 실행 요청은 framework 콜백으로, 도메인 실행은 저장 요청의 독립 진입점으로 이어진다', () => {
  const out = JSON.parse(execFileSync(process.execPath, [tool, `--root=${repoRoot}`, '--start=workflowTick'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }));
  const callees = out.starts[0].callees;
  assert.ok(callees.includes('workflowTaskStart.ts:launchExecute'));
  assert.ok(callees.includes('workflowTaskGates.ts:integrateGateExecute'));
  assert.ok(callees.includes('workflowPrepare.ts:registerExecute'));
  assert.ok(!callees.includes('taskLaunch.ts:launch'), '도메인 실행은 영속 서비스 요청을 감시하는 별도 진입점만 호출');
});


test('배열의 함수 값 저장은 호출이 아니며 ??= 기본값만 보고 프로젝트 push를 외부로 제외하지 않는다', () => {
  const stored = measure({ 'src/a.ts': `function leaf() { return 1; }\nexport function caller() { const out = []; out.push(leaf); return out; }\n` }, ['--start=caller']);
  assert.equal(stored.out.starts[0].transitions, 0, 'push는 leaf 값을 보관할 뿐 호출하지 않음');
  const unknown = measure({ 'src/a.ts': `class Ops { push() { return 1; } }\nexport function caller(value) { (value ??= []).push(1); }\n` }, ['--start=caller']);
  assert.equal(unknown.out.unresolvedCount, 1, '기존 value가 Ops일 수 있으므로 배열 기본값만으로 제외하지 않음');
});

test('Hono validator 팩터리는 검증 콜백을 등록하며 프로젝트 팩터리의 콜백 호출은 그대로 센다', () => {
  const sources = { 'src/a.ts': `import { validator } from 'hono/validator';\nfunction leaf() { return 1; }\nexport function register() { return validator('header', () => leaf()); }\n` };
  assert.equal(measure(sources, ['--start=register']).out.starts[0].transitions, 0);
  const project = { 'src/a.ts': `function leaf() { return 1; }\nfunction validator(cb) { cb(); }\nexport function caller() { validator(() => leaf()); }\n` };
  assert.equal(measure(project, ['--start=caller']).out.starts[0].transitions, 3);
});


test('기존 스키마를 refine한 파생 스키마의 검증 콜백도 import·중첩 참조를 따라 연결한다', () => {
  const src = {
    'src/schema.ts': `import { z } from 'zod';\nfunction leaf() { return true; }\nconst base = z.string();\nexport const derived = base.refine(() => leaf());\n`,
    'src/a.ts': `import { z } from 'zod';\nimport { derived } from './schema.ts';\nconst schema = z.object({ value: derived });\nexport function parse(value) { return schema.safeParse(value); }\n`,
  };
  assert.equal(measure(src, ['--start=parse']).out.starts[0].transitions, 2);
});

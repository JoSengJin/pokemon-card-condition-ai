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

test('실제 저장소: 검토에서 확인된 경로가 재현된다(pushNow 7회, onMainEnd 12회)', () => {
  const out = JSON.parse(execFileSync(process.execPath, [tool, `--root=${repoRoot}`], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }));
  // 구조 수정 전 기준(6857715) 재현이다. 구조 수정 단계에서 값이 줄면 이 테스트를 새 측정값으로 갱신한다.
  assert.equal(depthOf(out, 'pushNow'), 7, 'pushNow→runtime.push→runPush→verify(콜백+함수)→pushScope→commitsBetween→run');
  assert.equal(depthOf(out, 'onMainEnd'), 12);
  assert.ok(Array.isArray(out.unresolved) && out.manualEdges >= 7, '수동 간선과 미확인 목록이 출력됨');
});

test('같은 이름의 프로젝트 정의가 없어도 표준 목록에 없으면 외부로 단정하지 않고 미확인으로 보고한다(별칭·프로퍼티·계산 멤버)', () => {
  const src = {
    'src/svc.ts': `export function leaf() { return 1; }\n`,
    'src/use.ts': `import { leaf } from './svc.ts';
export function viaProp() { const api = { go: leaf }; return api.go(); }
export function viaAlias(ex: any) { const f = ex.approve; return f(); }
export function viaComputed(api: any, k: string) { return api[k](); }
export function viaFactory(make: any) { return make()(); }
`,
  };
  const { out } = measure(src);
  const reasons = Object.fromEntries(out.unresolved.map((u: any) => [u.caller, u.reason]));
  assert.match(reasons.viaProp, /표준 목록에 없는 메서드 go — 외부 여부 미확인/);
  assert.match(reasons.viaAlias, /지역 변수/);
  assert.match(reasons.viaComputed, /계산된 멤버/);
  assert.ok(reasons.viaFactory, '호출 결과를 다시 호출하는 복합 callee도 미확인');
  assert.equal(Object.keys(out.external).length, 0, '이 호출들은 외부로 분류되지 않음');
});

test('외부로 분류한 호출은 이유가 기록되고, 표준 이름이라도 같은 이름의 프로젝트 정의가 있으면 외부로 단정하지 않는다', () => {
  const src = {
    'src/ops.ts': `export class Ops { push(x: string) { return x; } }\n`,
    'src/use.ts': `import { Ops } from './ops.ts';
export function arr() { const out: string[] = []; out.push('a'); return out.length; }
export function unknownBase(o) { return o.push('a'); }
export function fsCall(fs: any) { return JSON.stringify({}); }
`,
  };
  const { out } = measure(src);
  assert.ok(Object.keys(out.external).some((k) => /표준 컨테이너 지역 변수 out/.test(k)), '지역 변수 초기화 근거가 이유로 남음');
  assert.ok(Object.keys(out.external).some((k) => /전역 객체 JSON/.test(k)));
  assert.ok(out.unresolved.some((u: any) => u.caller === 'unknownBase' && /같은 이름 프로젝트 정의 1개/.test(u.reason)), '타입을 모르는 o.push는 프로젝트 Ops.push일 수 있어 미확인');
});

test('수동 간선: 존재하지 않는 호출자·대상이나 호출자 본문에 없는 근거 문구는 거부하고, resolves로 해소한 미확인은 목록에서 빠진다', () => {
  const src = { 'src/a.ts': `export function a(ops) { return ops.go(); }\n`, 'src/b.ts': `export function go() { return 1; }\nexport function other() { return 2; }\n` };
  const bad = (edge: object) => measure(src, [], { edges: [edge] }).code;
  assert.notEqual(bad({ from: 'a.ts:nope', to: 'b.ts:go', evidence: 'x' }), 0);
  assert.notEqual(bad({ from: 'a.ts:a', to: 'b.ts:go', evidence: 'x', via: 'ops.missing' }), 0);
  const ok = measure(src, [], { edges: [{ from: 'a.ts:a', to: 'b.ts:go', evidence: '합성: ops=b의 모듈', via: 'ops.go', resolves: ['ops.go'] }] });
  assert.equal(ok.code, 0); assert.equal(ok.out.unresolved.length, 0);
});

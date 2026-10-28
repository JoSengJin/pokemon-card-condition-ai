// PAIR_CODING 구조 기준 점검: 파일별 함수 정의 수와 시작 함수에서의 최장 호출 전이 수(파일 경계 포함)를 정적으로 센다.
// 사용: node scripts/structure-trace.mjs <시작함수> <점검파일...>   (점검파일은 tools/pair-control 기준 경로)
// 동적 호출(obj.method)은 같은 이름의 프로젝트 함수를 모두 후보로 보고 '동적'으로 표시한다. 재귀는 '재귀'로 표시하며 통과로 세지 않는다.
import fs from 'node:fs';
import path from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import * as acorn from 'acorn';

const root = path.resolve(import.meta.dirname, '..');
const [start, ...files] = process.argv.slice(2);
if (!start || !files.length) { console.error('usage: structure-trace.mjs <start> <files...>'); process.exit(2); }

const FN = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);
const fns = []; // {file, name, node, named}
const counts = {};

function nameOf(node, parent) {
  if (node.id?.name) return node.id.name;
  if (parent?.type === 'VariableDeclarator' && parent.id.name) return parent.id.name;
  if ((parent?.type === 'MethodDefinition' || parent?.type === 'Property') && parent.key?.name) return parent.key.name;
  if (parent?.type === 'PropertyDefinition' && parent.key?.name) return parent.key.name;
  if (parent?.type === 'AssignmentExpression' && parent.left.property?.name) return parent.left.property.name;
  return null;
}

function walk(node, parent, visit) {
  if (!node || typeof node.type !== 'string') return;
  visit(node, parent);
  for (const k of Object.keys(node)) {
    const v = node[k];
    if (Array.isArray(v)) v.forEach((c) => c && typeof c.type === 'string' && walk(c, node, visit));
    else if (v && typeof v.type === 'string') walk(v, node, visit);
  }
}

for (const f of files) {
  const src = stripTypeScriptTypes(fs.readFileSync(path.join(root, f), 'utf8'), { mode: 'transform' });
  const ast = acorn.parse(src, { ecmaVersion: 'latest', sourceType: 'module' });
  counts[f] = { all: 0, named: 0 };
  walk(ast, null, (n, p) => {
    if (!FN.has(n.type)) return;
    const name = nameOf(n, p);
    counts[f].all++;
    if (name) counts[f].named++;
    fns.push({ file: f, name, node: n });
  });
}

const byName = new Map();
for (const fn of fns) if (fn.name) byName.set(fn.name, [...(byName.get(fn.name) ?? []), fn]);

// 함수가 호출하는 이름들(익명 콜백 안의 호출은 바깥 이름 있는 함수에 귀속)
function callsOf(fn) {
  const out = [];
  walk(fn.node.body, fn.node, (n) => {
    if (n.type !== 'CallExpression' && n.type !== 'NewExpression') return;
    const c = n.callee;
    if (c.type === 'Identifier') out.push({ name: c.name, dyn: false });
    else if (c.type === 'MemberExpression' && c.property?.name) out.push({ name: c.property.name, dyn: true });
  });
  return out;
}

// 자기 파일 안의 이름 우선(정적), 아니면 프로젝트 전체 후보(동적)
function targets(fn, call) {
  const cands = byName.get(call.name) ?? [];
  const same = cands.filter((c) => c.file === fn.file && c.node !== fn.node);
  const picked = call.dyn ? cands : same.length ? same : cands;
  return picked.filter((c) => c.node !== fn.node || call.dyn).map((c) => ({ fn: c, dyn: call.dyn || picked.length > 1 }));
}

const key = (f) => `${f.file}:${f.name}:${f.node.start}`;
let best = { depth: 0, path: [], recursion: [], dynamic: false };
function dfs(fn, pathArr, seen, dynamic) {
  if (pathArr.length - 1 > best.depth) best = { ...best, depth: pathArr.length - 1, path: pathArr.slice(), dynamic };
  const owned = fns.filter((x) => x.node !== fn.node && x.file === fn.file && x.node.start >= fn.node.start && x.node.end <= fn.node.end && !x.name);
  void owned;
  for (const call of callsOf(fn)) for (const t of targets(fn, call)) {
    if (seen.has(key(t.fn))) { best.recursion.push([...pathArr.map((p) => p.name), t.fn.name].join(' → ')); continue; }
    seen.add(key(t.fn));
    dfs(t.fn, [...pathArr, t.fn], seen, dynamic || t.dyn);
    seen.delete(key(t.fn));
  }
}
const startFns = fns.filter((f) => f.name === start);
for (const s of startFns) dfs(s, [s], new Set([key(s)]), false);

console.log(JSON.stringify({
  perFile: counts,
  start, maxTransitions: best.depth,
  longestPath: best.path.map((p) => `${path.basename(p.file)}:${p.name}`).join(' → '),
  pathUsesNameBasedDynamicMatch: best.dynamic,
  recursion: [...new Set(best.recursion)].slice(0, 5),
}, null, 2));

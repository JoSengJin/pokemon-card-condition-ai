// PAIR_CODING 구조 기준 점검: 파일별 함수 정의 수와 시작 함수에서의 최장 호출 전이 수(파일 경계 포함)를 정적으로 센다.
// 사용: node scripts/structure-trace.mjs <시작함수|--all> <점검파일...>   (점검파일은 tools/pair-control 기준 경로)
// --all: 점검파일의 이름 있는 모든 함수를 시작점으로 삼아 전이 4회를 넘는 시작점만 나열한다(점검파일 밖 프로젝트 파일도 함께 넘겨야 파일 경계를 센다).
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
const imports = {};
// 배열·문자열·Map 등 표준 객체의 메서드 이름은 같은 이름의 프로젝트 함수로 오인하지 않는다.
const BUILTIN = new Set(['push','pop','add','has','get','set','delete','filter','map','some','every','find','findIndex','forEach','includes','slice','splice','join','concat','flatMap','reduce','sort','reverse','keys','values','entries','startsWith','endsWith','trim','split','replace','test','match','toString','toLowerCase','padStart','then','catch','finally','indexOf','at','unref','write','end','on','once','resolve','reject','call','apply','bind','copyWithin','fill','flat','from','assign','fromEntries','stringify','parse','now','isArray','isInteger','toISOString','localeCompare','slice','exec','digest','update','randomUUID','kill']);
const GLOBALS = new Set(['JSON','Object','Array','Math','Promise','Date','Number','String','Boolean','Set','Map','WeakMap','WeakSet','Error','process','console','Buffer','RegExp','Symbol','Reflect']);
const HINT = { store: 'store.ts', locks: 'locks.ts', guard: 'freeGuard.ts', mainOps: 'runtime.ts' };

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
  imports[f] = {};
  for (const d of ast.body) if (d.type === 'ImportDeclaration') {
    const rel = d.source.value.startsWith('.') ? path.relative(root, path.resolve(path.dirname(path.join(root, f)), d.source.value)) : null; // 프로젝트 파일이면 경로, 외부 모듈이면 null
    for (const sp of d.specifiers) imports[f][sp.local.name] = { file: rel, ns: sp.type === 'ImportNamespaceSpecifier', imported: sp.imported?.name ?? sp.local.name };
  }
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

// 함수가 호출하는 이름들(익명 콜백 안의 호출은 바깥 이름 있는 함수에 귀속).
// 타이머·이벤트 핸들러로 "등록만" 하는 콜백(setInterval/setTimeout/on/once)은 등록 함수의 호출 전이가 아니라 나중에 런타임이 부르는 별도 진입점이므로 따라가지 않는다.
const REGISTER = new Set(['setInterval', 'setTimeout', 'on', 'once', 'addEventListener', 'registerApiRoute']);
const isFn = (n) => n && FN.has(n.type);
function callsOf(fn) {
  const out = [];
  const visit = (n) => {
    if (!n || typeof n.type !== 'string') return;
    if (n.type === 'CallExpression' || n.type === 'NewExpression') {
      const c = n.callee;
      const nm = c.type === 'Identifier' ? c.name : c.type === 'MemberExpression' ? c.property?.name : null;
      if (c.type === 'Identifier') out.push({ name: c.name, dyn: false });
      else if (c.type === 'MemberExpression' && c.property?.name) {
        const o = c.object;
        out.push({ name: c.property.name, dyn: true, base: o.type === 'Identifier' ? o.name : o.type === 'MemberExpression' ? o.property?.name : o.type === 'ThisExpression' ? 'this' : null, baseIsId: o.type === 'Identifier' });
      }
      visit(c);
      for (const a of n.arguments) if (!(REGISTER.has(nm) && isFn(a))) visit(a);
      return;
    }
    for (const k of Object.keys(n)) {
      const v = n[k];
      if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v.type === 'string') visit(v);
    }
  };
  visit(fn.node.body);
  return out;
}

// 호출 대상 해석. 같은 파일 함수 → import한 프로젝트 파일의 함수(정적). 객체 메서드(obj.m)는 객체 이름 힌트(store/locks/guard/mainOps/ex/this)로 후보를 좁히되 확정하지 못하면 이름 일치 후보 전체를 '동적'으로 둔다.
function targets(fn, call) {
  const cands = byName.get(call.name) ?? [], imp = imports[fn.file] ?? {};
  const st = (list) => list.filter((c) => c.node !== fn.node).map((c) => ({ fn: c, dyn: false }));
  if (!call.dyn) {
    const same = cands.filter((c) => c.file === fn.file);
    if (same.length) return st(same);
    const m = imp[call.name];
    if (!m || !m.file) return [];
    return st(cands.filter((c) => c.file.replace(/\.ts$/, '') === m.file.replace(/\.ts$/, '')));
  }
  if (BUILTIN.has(call.name)) return [];
  if (call.baseIsId && (GLOBALS.has(call.base) || (imp[call.base] && !imp[call.base].file))) return [];
  if (call.baseIsId && imp[call.base]?.ns) return st(cands.filter((c) => c.file.replace(/\.ts$/, '') === imp[call.base].file.replace(/\.ts$/, '')));
  const hintFile = HINT[call.base] ?? (call.base === 'ex' || call.base === 'this' ? 'executor.ts' : null);
  const hinted = hintFile ? cands.filter((c) => c.file.endsWith(`/${hintFile}`)) : [];
  const picked = hinted.length ? hinted : cands;
  return picked.map((c) => ({ fn: c, dyn: !hinted.length || picked.length > 1 }));
}

const key = (f) => `${f.file}:${f.name}:${f.node.start}`;
let best = { depth: 0, path: [], recursion: [], dynamic: false };
let cap = 12; // 이름 일치 후보가 많은 프로젝트에서 탐색이 폭증하지 않게 깊이를 자른다(제한 4회 초과 판정에는 충분)
function dfs(fn, pathArr, seen, dynamic) {
  if (pathArr.length - 1 > best.depth) best = { ...best, depth: pathArr.length - 1, path: pathArr.slice(), dynamic };
  const owned = fns.filter((x) => x.node !== fn.node && x.file === fn.file && x.node.start >= fn.node.start && x.node.end <= fn.node.end && !x.name);
  void owned;
  if (pathArr.length - 1 >= cap) return;
  for (const call of callsOf(fn)) for (const t of targets(fn, call)) {
    if (seen.has(key(t.fn))) { best.recursion.push([...pathArr.map((p) => p.name), t.fn.name].join(' → ')); continue; }
    seen.add(key(t.fn));
    dfs(t.fn, [...pathArr, t.fn], seen, dynamic || t.dyn);
    seen.delete(key(t.fn));
  }
}
const trace = (s) => { best = { depth: 0, path: [], recursion: [], dynamic: false }; dfs(s, [s], new Set([key(s)]), false); return best; };
const label = (p) => `${path.basename(p.file)}:${p.name}`;
if (start === '--all') {
  cap = 6;
  const over = fns.filter((f) => f.name).map((f) => { const b = trace(f); return { start: label(f), transitions: b.depth, path: b.path.map(label).join(' → '), nameBasedDynamicMatch: b.dynamic }; }).filter((r) => r.transitions > 4).sort((a, b) => b.transitions - a.transitions);
  console.log(JSON.stringify({ perFile: counts, overLimit: over }, null, 2));
  process.exit(0);
}
for (const s of fns.filter((f) => f.name === start)) trace(s);

console.log(JSON.stringify({
  perFile: counts,
  start, maxTransitions: best.depth,
  longestPath: best.path.map(label).join(' → '),
  pathUsesNameBasedDynamicMatch: best.dynamic,
  recursion: [...new Set(best.recursion)].slice(0, 5),
}, null, 2));

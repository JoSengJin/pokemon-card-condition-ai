// PAIR_CODING 구조 기준 점검: ① 파일당 함수 정의 수(익명 콜백·중첩·메서드 포함) ② 시작 함수별 최장 호출 전이 수(파일·객체 경계 포함).
// 사용: node scripts/structure-trace.mjs [--check] [--start=이름] [--root=경로] [--files=a.ts,b.ts]
//   기본 대상: root의 src/**/*.{ts,js,mjs} + scripts/*.mjs. --check는 기준(7개/4회) 초과가 있으면 종료코드 1.
// 호출 해석은 이름 일치 추정을 쓰지 않는다. 확정 간선만 센다:
//   식별자 호출(같은 파일 함수·import한 함수) / 네임스페이스 import(G.f) / this.m(클래스 메서드) / 타입 주석이 있는 매개변수·필드 체인(ex: Executor → ex.store.save)
//   / 함수 매개변수로 전달된 콜백(호출 지점에서 넘긴 함수 리터럴·함수 이름) / 수동 간선(scripts/structure-edges.json, 근거 필수).
// 확정하지 못한 멤버 호출은 unresolved에 나열한다(통과로 세지 않음 — 사람이 실제 호출자와 대조해야 한다).
// 타이머·이벤트 등록(setInterval/setTimeout/on/once) 콜백은 등록 함수의 호출 전이가 아니라 별도 진입점이다.
// getter/setter 접근은 호출 전이로 세지 않는다(한계: 함수 정의 수에는 포함).
import fs from 'node:fs';
import path from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import * as acorn from 'acorn';

const LIMIT_DEFS = 7, LIMIT_DEPTH = 4;
const FN = new Set(['FunctionDeclaration', 'FunctionExpression', 'ArrowFunctionExpression']);
const REGISTER = new Set(['setInterval', 'setTimeout', 'on', 'once', 'addEventListener', 'registerApiRoute']);
const MODIFIERS = /\b(readonly|private|public|protected)\b(?=\s)/g;
const EXTERNAL = /^(JSON|Object|Array|Math|Promise|Date|Number|String|Boolean|Set|Map|process|console|Buffer|RegExp|Symbol|Reflect|fs|path|crypto|os|Error)$/;

const args = process.argv.slice(2);
const opt = (n) => (args.find((a) => a.startsWith(`--${n}=`)) ?? '').split('=').slice(1).join('=');
const root = path.resolve(opt('root') || path.resolve(import.meta.dirname, '..'));

function listFiles() {
  if (opt('files')) return opt('files').split(',').filter(Boolean);
  const out = [];
  const walk = (d) => { for (const e of fs.readdirSync(path.join(root, d), { withFileTypes: true })) {
    const rel = path.join(d, e.name);
    if (e.isDirectory()) walk(rel); else if (/\.(ts|js|mjs)$/.test(e.name)) out.push(rel);
  } };
  walk('src');
  if (fs.existsSync(path.join(root, 'scripts'))) for (const e of fs.readdirSync(path.join(root, 'scripts'))) if (e.endsWith('.mjs')) out.push(path.join('scripts', e));
  return out.sort();
}

// ---------- 파싱 ----------
const files = listFiles(), parsed = {};
for (const f of files) {
  const orig = fs.readFileSync(path.join(root, f), 'utf8');
  const text = orig.replace(MODIFIERS, (m) => ' '.repeat(m.length)); // 매개변수 프로퍼티·필드 modifier를 길이 보존 공백으로(strip 모드가 지원)
  const code = f.endsWith('.ts') ? stripTypeScriptTypes(text, { mode: 'strip' }) : text; // strip은 오프셋을 보존하므로 text에서 타입 주석을 읽을 수 있다
  parsed[f] = { orig: text, ast: acorn.parse(code, { ecmaVersion: 'latest', sourceType: 'module', allowHashBang: true, locations: true }) };
}

const fns = [], classes = {}, exportsOf = {}, importsOf = {};
for (const f of files) {
  exportsOf[f] = {}; importsOf[f] = {};
  const stack = [];
  const nameOf = (n, p) => n.id?.name || (p?.type === 'VariableDeclarator' && p.id.name) || ((p?.type === 'MethodDefinition' || p?.type === 'Property' || p?.type === 'PropertyDefinition') && (p.key?.name ?? p.key?.value)) || (p?.type === 'AssignmentExpression' && p.left.property?.name) || null;
  const rec = (n, p) => {
    if (!n || typeof n.type !== 'string') return;
    if (n.type === 'ImportDeclaration') {
      const rel = n.source.value.startsWith('.') ? path.normalize(path.join(path.dirname(f), n.source.value)) : null;
      for (const sp of n.specifiers) importsOf[f][sp.local.name] = { file: rel, ns: sp.type === 'ImportNamespaceSpecifier', imported: sp.imported?.name ?? 'default' };
    }
    if (n.type === 'ClassDeclaration') classes[n.id.name] = { file: f, node: n, fields: {} };
    if (FN.has(n.type)) {
      const cls = [...stack].reverse().find((s) => s.type === 'ClassDeclaration');
      const owner = [...stack].reverse().find((s) => FN.has(s.type)) ?? null;
      const fn = { file: f, name: nameOf(n, p) || null, node: n, cls: cls?.id.name ?? null, owner, kind: p?.type === 'MethodDefinition' ? p.kind : 'fn' };
      fns.push(fn); n.__fn = fn;
    }
    stack.push(n);
    for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach((c) => c && typeof c.type === 'string' && rec(c, n)); else if (v && typeof v.type === 'string') rec(v, n); }
    stack.pop();
  };
  rec(parsed[f].ast, null);
  for (const n of parsed[f].ast.body) {
    if (n.type !== 'ExportNamedDeclaration') continue;
    if (n.declaration?.type === 'FunctionDeclaration') exportsOf[f][n.declaration.id.name] = n.declaration.id.name;
    if (n.declaration?.type === 'VariableDeclaration') for (const d of n.declaration.declarations) exportsOf[f][d.id.name] = d.id.name;
    if (n.source) { const rel = path.normalize(path.join(path.dirname(f), n.source.value)); for (const sp of n.specifiers) exportsOf[f][sp.exported.name] = { from: rel, name: sp.local.name }; }
  }
}
for (const c of Object.values(classes)) { // 클래스 필드 타입(`store: Store<State>`)
  const src = parsed[c.file].orig.slice(c.node.start, c.node.end);
  for (const m of src.matchAll(/^\s{0,4}(?:readonly\s+)?(\w+)\s*[?!]?\s*:\s*([A-Z]\w*)/gm)) c.fields[m[1]] = m[2];
}

const byFile = new Map();
for (const fn of fns) { if (!byFile.has(fn.file)) byFile.set(fn.file, []); byFile.get(fn.file).push(fn); }
const topLevel = (file, name) => (byFile.get(file) ?? []).filter((x) => x.name === name && !x.owner && !x.cls);
const resolveExport = (file, name, depth = 0) => {
  const e = exportsOf[file]?.[name];
  if (!e || depth > 5) return topLevel(file, name);
  return typeof e === 'string' ? topLevel(file, e) : resolveExport(e.from, e.name, depth + 1);
};
const methods = (cname, m) => { const c = classes[cname]; return c ? (byFile.get(c.file) ?? []).filter((x) => x.cls === cname && x.name === m) : []; };

const edgesFile = path.join(root, 'scripts', 'structure-edges.json');
const manual = fs.existsSync(edgesFile) ? JSON.parse(fs.readFileSync(edgesFile, 'utf8')).edges ?? [] : [];
for (const m of manual) if (!m.evidence) throw new Error(`수동 간선에는 근거(evidence)가 필요함: ${m.from} -> ${m.to}`);
const findByLabel = (label) => { const [f, n] = label.split(':'); return fns.filter((x) => path.basename(x.file) === f && x.name === n); };

// ---------- 호출 수집 ----------
const idOf = (p) => (p.type === 'AssignmentPattern' ? p.left : p);
const typesOfParams = (fn) => {
  const out = {};
  for (const p of fn.node.params ?? []) {
    const id = idOf(p);
    if (id?.type !== 'Identifier') continue;
    const m = /^\s*\??\s*:\s*([A-Z]\w*)/.exec(parsed[fn.file].orig.slice(id.end, id.end + 80));
    if (m) out[id.name] = m[1];
  }
  return out;
};
const chainUp = (fn) => { const out = []; for (let f = fn; f; f = f.owner?.__fn) out.push(f); return out; };
const scopeParams = (fn) => new Set(chainUp(fn).flatMap((f) => (f.node.params ?? []).map((p) => idOf(p)?.name).filter(Boolean)));
const scopeTypes = (fn) => Object.assign({}, ...chainUp(fn).reverse().map(typesOfParams));
const passedAsArg = new Set(); // 프로젝트 함수에 인자로 넘긴 함수 리터럴(별도 노드)

function callsOf(fn) {
  const calls = [];
  const visit = (n) => {
    if (!n || typeof n.type !== 'string') return;
    if (n !== fn.node && FN.has(n.type) && (passedAsArg.has(n) || (n.__fn.name && n.__fn.owner === fn.node))) return; // 별도 노드
    if (n.type === 'CallExpression' || n.type === 'NewExpression') {
      const c = n.callee, call = { line: n.loc.start.line, args: n.arguments };
      if (c.type === 'Identifier') calls.push({ ...call, kind: 'id', name: c.name });
      else if (c.type === 'MemberExpression' && !c.computed && c.property?.name) {
        const chain = []; let o = c.object;
        while (o?.type === 'MemberExpression' && !o.computed) { chain.unshift(o.property.name); o = o.object; }
        calls.push({ ...call, kind: 'member', name: c.property.name, base: o?.type === 'Identifier' ? o.name : o?.type === 'ThisExpression' ? 'this' : null, chain });
      }
      const nm = c.type === 'Identifier' ? c.name : c.property?.name;
      visit(c);
      for (const a of n.arguments) { if (!(FN.has(a.type) && REGISTER.has(nm))) visit(a); }
      return;
    }
    for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v.type === 'string') visit(v); }
  };
  visit(fn.node.body);
  return calls;
}

function resolve(fn, call) {
  const imp = importsOf[fn.file], types = scopeTypes(fn);
  if (call.kind === 'id') {
    for (let s = fn; s; s = s.owner?.__fn) { const inner = fns.filter((x) => x.owner === s.node && x.name === call.name); if (inner.length) return { to: inner, how: 'local' }; }
    const same = topLevel(fn.file, call.name);
    if (same.length) return { to: same, how: 'same-file' };
    const m = imp[call.name];
    if (m?.file) return { to: resolveExport(m.file, m.imported), how: 'import' };
    if (scopeParams(fn).has(call.name)) return { callbackParam: call.name };
    return { to: [], how: 'external' };
  }
  const { base, chain, name } = call;
  if (base && imp[base]?.ns) return { to: resolveExport(imp[base].file, name), how: 'namespace' };
  if (base && imp[base] && !imp[base].file) return { to: [], how: 'external' };
  let type = base === 'this' ? fn.cls : base ? types[base] : null;
  for (const seg of chain) { type = type && classes[type]?.fields[seg] ? classes[type].fields[seg] : null; if (!type) break; }
  if (type && classes[type]) { const to = methods(type, name); if (to.length) return { to, how: `type:${type}` }; }
  if (base && EXTERNAL.test(base)) return { to: [], how: 'external' };
  return { to: [], how: 'unresolved' };
}

let edgeCache = new Map(), callers = new Map(), unresolved = [];
function edgesOf(fn) {
  if (edgeCache.has(fn)) return edgeCache.get(fn);
  const out = [];
  edgeCache.set(fn, out);
  for (const call of callsOf(fn)) {
    const r = resolve(fn, call);
    if (r.callbackParam) { out.push({ cbParam: r.callbackParam }); continue; }
    if (r.how === 'unresolved') { if (fns.some((x) => x.name === call.name)) unresolved.push({ file: fn.file, line: call.line, caller: fn.name, call: `${call.base ?? ''}${call.chain.map((s) => '.' + s).join('')}.${call.name}`, sameNameDefinitions: fns.filter((x) => x.name === call.name).length }); continue; } // 같은 이름의 프로젝트 함수가 없으면 표준·외부 메서드로 보고 나열하지 않는다
    for (const t of r.to) {
      out.push({ to: t, how: r.how });
      call.args.forEach((a, i) => { // 인자로 넘긴 함수 리터럴·함수 이름은 호출 대상의 해당 위치 매개변수 콜백이다
        const cb = FN.has(a.type) ? a.__fn : a.type === 'Identifier' ? fns.find((x) => x.file === fn.file && x.name === a.name && !x.cls) : null;
        const pname = t.node.params[i] && idOf(t.node.params[i])?.name;
        if (!cb || !pname) return;
        if (!callers.has(t)) callers.set(t, []);
        callers.get(t).push({ param: pname, cb });
        if (FN.has(a.type)) passedAsArg.add(a);
      });
    }
  }
  return out;
}
const computeAll = () => { edgeCache = new Map(); callers = new Map(); unresolved = []; for (const f of fns) edgesOf(f); };
computeAll(); computeAll(); // 두 번째 계산: 콜백 리터럴이 별도 노드로 확정된 상태에서 간선을 다시 만든다
{ const seen = new Set(); unresolved = unresolved.filter((x) => { const k = `${x.file}:${x.line}:${x.call}`; return seen.has(k) ? false : (seen.add(k), true); }); }

function neighbors(fn) {
  const out = [];
  for (const e of edgesOf(fn)) {
    if (e.to) out.push({ to: e.to, w: 1, how: e.how });
    else for (const c of callers.get(fn) ?? []) if (c.param === e.cbParam) out.push({ to: c.cb, w: 1, how: 'callback-param' });
  }
  for (const m of manual) if (findByLabel(m.from).includes(fn)) for (const t of findByLabel(m.to)) out.push({ to: t, w: m.weight ?? 1, how: `manual: ${m.evidence}` });
  return out;
}

// ---------- 깊이 ----------
const label = (f) => `${path.basename(f.file)}:${f.name ?? `<익명@${f.node.loc.start.line}>`}`;
function trace(start) {
  let best = { depth: 0, path: [start], hows: [] };
  const dfs = (fn, p, hows, d, seen) => {
    if (d > best.depth) best = { depth: d, path: p.slice(), hows: hows.slice() };
    if (d >= 24) return;
    for (const n of neighbors(fn)) {
      if (seen.has(n.to)) continue;
      seen.add(n.to); p.push(n.to); hows.push(n.how);
      dfs(n.to, p, hows, d + n.w, seen);
      p.pop(); hows.pop(); seen.delete(n.to);
    }
  };
  dfs(start, [start], [], 0, new Set([start]));
  return best;
}

// ---------- 출력 ----------
const counts = {};
for (const f of files) counts[f] = (byFile.get(f) ?? []).length;
const overFiles = Object.entries(counts).filter(([, c]) => c > LIMIT_DEFS).map(([file, defs]) => ({ file, defs }));
const only = opt('start');
const starts = fns.filter((f) => (f.name || passedAsArg.has(f.node)) && (!only || f.name === only));
const rows = starts.map((s) => { const b = trace(s); return { start: label(s), transitions: b.depth, path: b.path.map(label).join(' → '), hows: b.hows }; });
const overStarts = rows.filter((r) => r.transitions > LIMIT_DEPTH).sort((a, b) => b.transitions - a.transitions);
const result = only ? { perFile: counts, starts: rows, unresolvedCount: unresolved.length } : { limits: { defs: LIMIT_DEFS, depth: LIMIT_DEPTH }, perFile: counts, overFiles, overStarts, unresolved, manualEdges: manual.length };
console.log(JSON.stringify(result, null, 2));
if (args.includes('--check') && (overFiles.length || overStarts.length)) process.exit(1);

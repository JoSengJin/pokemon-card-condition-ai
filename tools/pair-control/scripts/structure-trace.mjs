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
const EXTERNAL = /^(JSON|Object|Array|Math|Promise|Date|Number|String|Boolean|Set|Map|process|console|Buffer|RegExp|Symbol|Reflect|fs|path|crypto|os|Error|document|window|navigator|location|localStorage|sessionStorage|Intl|URL|Response|Request|globalThis)$/;

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
  for (const m of src.matchAll(/^\s*(\w+)\s*[?!]?\s*:\s*([A-Z]\w*)(?:<[^>]*>)?\s*[;=]/gm)) c.fields[m[1]] = m[2]; // 필드 선언(`name: Type;` 또는 `= …`)
}

const dataFields = {}; // interface·type·class 필드의 원문 타입(`failures: {…}[]` 같은 데이터 컬렉션 판별용)
for (const f of files) {
  const text = parsed[f].orig;
  for (const m of text.matchAll(/(?:interface|type)\s+([A-Z]\w*)[^{=]*[={]\s*\{([\s\S]*?)\n\}|(?:interface|type)\s+([A-Z]\w*)[^{=]*\{([^}]*)\}/g)) {
    const name = m[1] ?? m[3], body = m[2] ?? m[4] ?? '';
    for (const q of body.matchAll(/(\w+)\??:\s*([^;\n]+)/g)) (dataFields[name] ??= {})[q[1]] = q[2].trim();
  }
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
const findByLabel = (label) => { const [f, n] = label.split(':'); return fns.filter((x) => path.basename(x.file) === f && x.name === n); };
for (const m of manual) { // 근거 필수 + 호출자·대상이 실제로 존재하고, 호출자 본문에 연결 근거 문구(via)가 실제로 있어야 한다
  if (!m.evidence) throw new Error(`수동 간선에는 근거(evidence)가 필요함: ${m.from} -> ${m.to}`);
  const from = findByLabel(m.from), to = findByLabel(m.to);
  if (!from.length || !to.length) throw new Error(`수동 간선의 호출자 또는 대상이 존재하지 않음: ${m.from} -> ${m.to}`);
  if (m.via && !from.some((f) => parsed[f.file].orig.slice(f.node.start, f.node.end).includes(m.via))) throw new Error(`수동 간선 근거 문구(${m.via})가 호출자 본문에 없음: ${m.from}`);
}

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
const patNames = (t) => (!t ? [] : t.type === 'Identifier' ? [t.name] : t.type === 'ObjectPattern' ? t.properties.flatMap((q) => patNames(q.value ?? q.argument)) : t.type === 'ArrayPattern' ? t.elements.flatMap(patNames) : t.type === 'AssignmentPattern' ? patNames(t.left) : t.type === 'RestElement' ? patNames(t.argument) : []);
const scopeParams = (fn) => new Set(chainUp(fn).flatMap((f) => (f.node.params ?? []).flatMap(patNames)));
const scopeTypes = (fn) => Object.assign({}, ...chainUp(fn).reverse().map(typesOfParams));
const passedAsArg = new Set(); // 프로젝트 함수에 인자로 넘긴 함수 리터럴(별도 노드)
/** 반환 타입 주석(`): Executor`)에서 클래스 이름을 읽는다. */
const returnType = (fn) => { const t = parsed[fn.file].orig; const body = fn.node.body; const from = (fn.node.params.length ? fn.node.params[fn.node.params.length - 1].end : fn.node.start); const m = /^[^)]*\)\s*:\s*(?:Promise<)?([A-Z]\w*)/.exec(t.slice(from, body.start)); return m ? m[1] : null; };
const returnTypeDeep = (fn, d) => { const a = returnType(fn); if (a) return a; const b = fn.node.body; if (d > 3 || !b || b.type !== 'CallExpression' || b.callee.type !== 'Identifier') return null; const t = fns.find((x) => x.file === fn.file && x.name === b.callee.name) ?? (importsOf[fn.file][b.callee.name]?.file ? resolveExport(importsOf[fn.file][b.callee.name].file, importsOf[fn.file][b.callee.name].imported)[0] : null); return t ? returnTypeDeep(t, d + 1) : null; };
/** 지역 변수의 "표준 컨테이너/클래스" 초기값에서 타입을 추론한다(근거: 선언 초기값). kind: 'std'(배열·문자열·Map·Set·Promise 등) 또는 클래스 이름. */
function localType(fn, name) {
  let found = null;
  const visit = (n) => {
    if (!n || typeof n.type !== 'string' || found) return;
    if (n.type === 'VariableDeclarator' && n.id.type === 'Identifier' && n.id.name === name && n.init) {
      const i = n.init, ann = /^\s*:\s*([A-Za-z_][\w.<>\[\], |]*)\s*=/.exec(parsed[fn.file].orig.slice(n.id.end, n.init.start));
      if (ann && /(\[\]|^Array|^Set|^Map|^string|^number|^Record|^Promise)/.test(ann[1].trim())) found = { std: `주석 ${ann[1].trim()}` };
      else if (i.type === 'ArrayExpression') found = { std: '배열 리터럴 초기화' };
      else if (i.type === 'Literal' || i.type === 'TemplateLiteral') found = { std: '리터럴 초기화' };
      else if (i.type === 'NewExpression' && i.callee.type === 'Identifier') found = /^(Set|Map|WeakMap|WeakSet|Array|Promise|Date|RegExp|Error|URL)$/.test(i.callee.name) ? { std: `new ${i.callee.name}` } : classes[i.callee.name] ? { cls: i.callee.name } : null;
      else if (i.type === 'CallExpression' && i.callee.type === 'Identifier') { const r = fns.find((x) => x.file === fn.file && x.name === i.callee.name) ?? (importsOf[fn.file][i.callee.name]?.file ? resolveExport(importsOf[fn.file][i.callee.name].file, importsOf[fn.file][i.callee.name].imported)[0] : null); const rt = r && returnType(r); if (rt && classes[rt]) found = { cls: rt }; }
      else if (i.type === 'AwaitExpression' && i.argument.type === 'CallExpression' && i.argument.callee.type === 'Identifier') { const r = fns.find((x) => x.file === fn.file && x.name === i.argument.callee.name); const rt = r && returnType(r); if (rt && classes[rt]) found = { cls: rt }; }
    }
    if (n !== fn.node && FN.has(n.type)) return;
    for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach(visit); else if (v && typeof v.type === 'string') visit(v); }
  };
  visit(fn.node.body);
  return found;
}

function callsOf(fn) {
  const calls = [];
  const visit = (n) => {
    if (!n || typeof n.type !== 'string') return;
    if (n !== fn.node && FN.has(n.type) && (passedAsArg.has(n) || (n.__fn.name && n.__fn.owner === fn.node))) return; // 별도 노드
    if (n.type === 'CallExpression' || n.type === 'NewExpression') {
      const c = n.callee, call = { line: n.loc.start.line, args: n.arguments };
      if (c.type === 'Identifier') calls.push({ ...call, kind: 'id', name: c.name, isNew: n.type === 'NewExpression' });
      else if (c.type === 'MemberExpression' && c.computed) calls.push({ ...call, kind: 'member', computed: true, name: '[]', base: null, chain: [] });
      else if (c.type === 'MemberExpression' && c.property?.name) {
        const chain = []; let o = c.object;
        while (o?.type === 'MemberExpression' && !o.computed) { chain.unshift(o.property.name); o = o.object; }
        calls.push({ ...call, baseCall: o?.type === 'CallExpression' && o.callee.type === 'Identifier' ? o.callee.name : null, kind: 'member', computed: false, name: c.property.name, base: o?.type === 'Identifier' ? o.name : o?.type === 'ThisExpression' ? 'this' : null, chain });
      }
      else calls.push({ ...call, kind: 'member', computed: true, name: '()', base: null, chain: [] }); // 호출 결과·괄호식 등 복합 callee
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

const GLOBAL_CALLS = new Set(['parseInt', 'parseFloat', 'String', 'Number', 'Boolean', 'Array', 'Object', 'Error', 'Date', 'Promise', 'Symbol', 'BigInt', 'require', 'setTimeout', 'setInterval', 'clearTimeout', 'clearInterval', 'setImmediate', 'queueMicrotask', 'encodeURIComponent', 'decodeURIComponent', 'fetch', 'structuredClone', 'isNaN', 'Boolean', 'Map', 'Set', 'WeakMap', 'WeakSet', 'RegExp', 'URL', 'AbortSignal', 'TextDecoder', 'TextEncoder']);
// 표준 라이브러리 메서드 이름(배열·문자열·Map·Set·Promise·스트림·해시·자식 프로세스). 같은 이름의 프로젝트 정의가 하나도 없을 때만 "표준 메서드"로 분류하고 이유를 기록한다.
const STANDARD = new Set('push pop shift unshift map filter some every find findIndex findLast forEach includes indexOf lastIndexOf join slice splice concat flat flatMap reduce sort reverse fill keys values entries startsWith endsWith trim trimStart trimEnd split replace replaceAll match matchAll test exec toString toLowerCase toUpperCase padStart padEnd repeat localeCompare at charAt charCodeAt substring toFixed add has get set delete clear then catch finally toISOString toJSON getTime getFullYear stringify parse now isArray isInteger isFinite fromEntries assign freeze create entries from of resolve reject all allSettled race write end on once off emit unref ref kill pipe destroy digest update randomUUID randomBytes createHash exit cwd hrtime resume pause abort send close listen fromCharCode normalize querySelector querySelectorAll getElementById closest addEventListener removeEventListener setAttribute getAttribute removeAttribute appendChild removeChild remove focus blur click dispatchEvent select writeText toggle contains classList scrollIntoView scrollTo json text blob header safeParse'.split(' '));
const FRAMEWORK = new Set('createRun getWorkflow getWorkflowRunById safeParse addIssue suspend bail resume start getSuspendedStep'.split(' '));
const LOCAL_VARS = (fn) => { const names = new Set(); const walk = (n) => { if (!n || typeof n.type !== 'string') return; if (n.type === 'VariableDeclarator') { const collect = (t) => { if (t.type === 'Identifier') names.add(t.name); else if (t.type === 'ObjectPattern') t.properties.forEach((q) => collect(q.value ?? q.argument)); else if (t.type === 'ArrayPattern') t.elements.forEach((q) => q && collect(q)); }; collect(n.id); } if (n !== fn.node && FN.has(n.type)) return; for (const k of Object.keys(n)) { const v = n[k]; if (Array.isArray(v)) v.forEach(walk); else if (v && typeof v.type === 'string') walk(v); } }; walk(fn.node.body); return names; };

/** 호출 대상 해석. how: 확정(local·same-file·import·namespace·type:X), external(reason 기록), unresolved(reason 기록). */
function resolve(fn, call) {
  const imp = importsOf[fn.file], types = scopeTypes(fn);
  if (call.kind === 'id') {
    for (let s = fn; s; s = s.owner?.__fn) { const inner = fns.filter((x) => x.owner === s.node && x.name === call.name); if (inner.length) return { to: inner, how: 'local' }; }
    const same = topLevel(fn.file, call.name);
    if (same.length) return { to: same, how: 'same-file' };
    if (call.isNew && imp[call.name]?.file) { const ic = classes[imp[call.name].imported]; if (ic) { const to = methods(imp[call.name].imported, 'constructor'); return to.length ? { to, how: `new:${call.name}` } : { to: [], how: 'class-no-constructor' }; } }
    const m = imp[call.name];
    if (m?.file) { const to = resolveExport(m.file, m.imported); return to.length ? { to, how: 'import' } : { to: [], how: 'unresolved', reason: `import:${m.file}에서 ${m.imported} 정의를 찾지 못함` }; }
    if (m) return { to: [], how: 'external', reason: `외부 모듈 import(${m.imported})` };
    if (scopeParams(fn).has(call.name)) return { callbackParam: call.name };
    if (call.isNew && classes[call.name]) { const to = methods(call.name, 'constructor'); return to.length ? { to, how: `new:${call.name}` } : { to: [], how: 'class-no-constructor' }; }
    if (chainUp(fn).some((f) => LOCAL_VARS(f).has(call.name))) return { to: [], how: 'unresolved', reason: '지역 변수(별칭·구조분해 포함)를 호출 — 대상 미확인' };
    if (GLOBAL_CALLS.has(call.name)) return { to: [], how: 'external', reason: `전역 표준 함수 ${call.name}` };
    return { to: [], how: 'unresolved', reason: '선언을 찾지 못한 식별자 호출' };
  }
  const { base, chain, name } = call;
  if (call.computed) return { to: [], how: 'unresolved', reason: '계산된 멤버 호출' };
  if (base && imp[base]?.ns) { const to = resolveExport(imp[base].file, name); return to.length ? { to, how: 'namespace' } : { to: [], how: 'unresolved', reason: `${imp[base].file}에서 ${name} 정의를 찾지 못함` }; }
  if (base && imp[base] && !imp[base].file) return { to: [], how: 'external', reason: `외부 모듈 ${base}의 멤버` };
  let type = base === 'this' ? fn.cls : base ? types[base] : null;
  if (!type && !base && call.baseCall) { const rf = fns.find((x) => x.file === fn.file && x.name === call.baseCall); const rt = rf && returnTypeDeep(rf, 0); if (rt) type = rt; }
  if (!type && base && !chain.length) { const lt = chainUp(fn).map((f) => localType(f, base)).find(Boolean); if (lt?.cls) type = lt.cls; else if (lt?.std && !fns.some((x) => x.name === name && x.cls === null && false)) return { to: [], how: 'external', reason: `표준 컨테이너 지역 변수 ${base}(${lt.std})의 메서드 ${name}` }; }
  let rawType = null;
  for (const seg of chain) {
    const nxt = type && (classes[type]?.fields[seg] ?? (dataFields[type]?.[seg] && /^[A-Z]\w*$/.test(dataFields[type][seg]) ? dataFields[type][seg] : null));
    if (!nxt && type && dataFields[type]?.[seg]) rawType = dataFields[type][seg];
    type = nxt; if (!type) break;
  }
  if (rawType && /(\[\]|^Array<|^Set<|^Map<|^Record<|^string\b|^Partial<Record)/.test(rawType) && !(rawType.includes('=>')) && chain.length) return { to: [], how: 'external', reason: `데이터 컬렉션 필드(${chain.join('.')}: ${rawType.slice(0, 40)})의 메서드 ${name}` };
  if (type && classes[type]) { const to = methods(type, name); if (to.length) return { to, how: `type:${type}` }; return { to: [], how: 'unresolved', reason: `${type}에 ${name} 메서드 없음` }; }
  if (base && EXTERNAL.test(base)) return { to: [], how: 'external', reason: `전역 객체 ${base}` };
  const defined = fns.filter((x) => x.name === name).length;
  if (!defined && FRAMEWORK.has(name)) return { to: [], how: 'external', reason: `프레임워크(Mastra·zod) 메서드 ${name}(같은 이름의 프로젝트 정의 없음)` };
  if (!defined && STANDARD.has(name)) return { to: [], how: 'external', reason: `표준 메서드 ${name}(같은 이름의 프로젝트 정의 없음)` };
  return { to: [], how: 'unresolved', reason: defined ? `같은 이름 프로젝트 정의 ${defined}개 — 호출 대상 미확정` : `표준 목록에 없는 메서드 ${name} — 외부 여부 미확인` };
}

let edgeCache = new Map(), callers = new Map(), unresolved = [], external = [];
function edgesOf(fn) {
  if (edgeCache.has(fn)) return edgeCache.get(fn);
  const out = [];
  edgeCache.set(fn, out);
  for (const call of callsOf(fn)) {
    const r = resolve(fn, call);
    if (r.callbackParam) { out.push({ cbParam: r.callbackParam, call }); continue; }
    if (r.how === 'unresolved' || r.how === 'external') { (r.how === 'unresolved' ? unresolved : external).push({ file: fn.file, line: call.line, caller: fn.name, call: `${call.base ?? ''}${(call.chain ?? []).map((q) => '.' + q).join('')}${call.kind === 'id' ? call.name : '.' + call.name}`, reason: r.reason }); continue; }
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
const computeAll = () => { edgeCache = new Map(); callers = new Map(); unresolved = []; external = []; for (const f of fns) edgesOf(f); };
computeAll(); computeAll(); // 두 번째 계산: 콜백 리터럴이 별도 노드로 확정된 상태에서 간선을 다시 만든다
unresolved = unresolved.filter((u) => !manual.some((m) => (m.resolves ?? []).includes(u.call) && findByLabel(m.from).some((f) => f.name === u.caller && path.basename(f.file) === path.basename(u.file)))); // 수동 간선이 근거와 함께 해소한 호출(resolves 목록)
{ const dedupe = (list) => { const seen = new Set(); return list.filter((x) => { const k = `${x.file}:${x.line}:${x.call}`; return seen.has(k) ? false : (seen.add(k), true); }); }; unresolved = dedupe(unresolved); external = dedupe(external); }

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
function summarizeExternal() { // 외부로 분류한 호출은 이유별 개수와 예시 위치를 남긴다(추적 가능)
  const by = {};
  for (const e of external) { const k = e.reason; (by[k] ??= { count: 0, sample: `${e.file}:${e.line} ${e.call}` }).count++; }
  return by;
}
const only = opt('start');
const starts = fns.filter((f) => (f.name || passedAsArg.has(f.node)) && (!only || f.name === only));
const rows = starts.map((s) => { const b = trace(s); return { start: label(s), transitions: b.depth, path: b.path.map(label).join(' → '), hows: b.hows, ...(only ? { callees: [...new Set(neighbors(s).map((n) => label(n.to)))] } : {}) }; });
const overStarts = rows.filter((r) => r.transitions > LIMIT_DEPTH).sort((a, b) => b.transitions - a.transitions);
const result = only ? { perFile: counts, starts: rows, unresolvedCount: unresolved.length } : { limits: { defs: LIMIT_DEFS, depth: LIMIT_DEPTH }, perFile: counts, overFiles, overStarts, unresolved, external: summarizeExternal(), manualEdges: manual.length };
console.log(JSON.stringify(result, null, 2));
if (args.includes('--check') && (overFiles.length || overStarts.length)) process.exit(1);

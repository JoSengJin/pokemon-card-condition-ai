import { namedFunction } from './trace-bindings.mjs';

export function returnType(ctx, fn) {
  const body = fn.node.body, params = fn.node.params;
  const from = params.length ? params[params.length - 1].end : fn.node.start;
  const match = /^[^)]*\)\s*:\s*(?:Promise<)?([A-Z]\w*)/.exec(ctx.parsed[fn.file].orig.slice(from, body.start));
  return match ? match[1] : null;
}

export function localType(ctx, fn, decl) {
  const init = decl.init;
  if (decl.id.type !== 'Identifier' || !init) return null;
  const annotation = /^\s*:\s*([A-Za-z_][\w.<>\[\], |]*)\s*=/.exec(ctx.parsed[fn.file].orig.slice(decl.id.end, init.start));
  if (annotation && /(\[\]|^Array|^Set|^Map|^string|^number|^Record|^Promise)/.test(annotation[1].trim())) return { std: '주석 ' + annotation[1].trim() };
  if (init.type === 'ArrayExpression') return { std: '배열 리터럴 초기화' };
  if (init.type === 'Literal' || init.type === 'TemplateLiteral') return { std: '리터럴 초기화' };
  if (init.type === 'MemberExpression' && !init.computed) {
    const chain = []; let base = init;
    while (base.type === 'MemberExpression' && !base.computed) { chain.unshift(base.property.name); base = base.object; }
    if (base.type === 'Identifier') return { alias: { base: base.name, chain } };
  }
  if (init.type === 'NewExpression' && init.callee.type === 'Identifier') {
    const name = init.callee.name;
    return /^(Set|Map|WeakMap|WeakSet|Array|Promise|Date|RegExp|Error|URL)$/.test(name) ? { std: 'new ' + name } : ctx.classes[name] ? { cls: name } : null;
  }
  const call = init.type === 'AwaitExpression' ? init.argument : init;
  if (call.type !== 'CallExpression' || call.callee.type !== 'Identifier') return null;
  const target = namedFunction(ctx, fn.file, call.callee.name), type = target && ctx.returns.get(target);
  if (type && ctx.classes[type]) return { cls: type };
  if (target && ctx.returnedMembers.has(target)) return { members: ctx.returnedMembers.get(target) };
  if (target && ctx.returnedFunctions.has(target)) return { fn: ctx.returnedFunctions.get(target) };
  return null;
}

export function indexReturnTypes(ctx) {
  for (const fn of ctx.fns) ctx.returns.set(fn, returnType(ctx, fn));
  // 주석 없는 단순 반환 별칭도 고정점까지 읽는다. 재귀 함수 호출 없이 데이터만 전파한다.
  let changed = true;
  for (let pass = 0; changed && pass < ctx.fns.length; pass++) {
    changed = false;
    for (const fn of ctx.fns) {
      const body = fn.node.body;
      if (ctx.returns.get(fn) || body?.type !== 'CallExpression' || body.callee.type !== 'Identifier') continue;
      const target = namedFunction(ctx, fn.file, body.callee.name), type = target && ctx.returns.get(target);
      if (type) { ctx.returns.set(fn, type); changed = true; }
    }
  }
}

import { FN, REGISTER } from './trace-config.mjs';
import { children } from './trace-ast.mjs';
import { namedFunction } from './trace-bindings.mjs';

export function callsOf(ctx, fn) {
  const calls = [], pending = [fn.node.body];
  while (pending.length) {
    const node = pending.pop(); if (!node || FN.has(node.type)) continue;
    if (node.type === 'CallExpression' || node.type === 'NewExpression') calls.push(describeCall(node));
    if (node.type === 'MemberExpression' && !node.computed && ctx.getterNames.has(node.property?.name)) calls.push({ ...describeCall({ callee: node, arguments: [], loc: node.loc, type: 'CallExpression' }), getter: true });
    pending.push(...children(node));
  }
  return calls;
}

export function describeCall(node) {
  const callee = node.callee, call = { line: node.loc.start.line, args: node.arguments, node, origin: rootIdentifier(node.callee) };
  if (callee.type === 'Identifier') return { ...call, kind: 'id', name: callee.name, isNew: node.type === 'NewExpression' };
  if (callee.type !== 'MemberExpression') return { ...call, kind: 'member', computed: true, name: '[]', base: null, chain: [] };
  const chain = []; let object = callee.object;
  while (object?.type === 'MemberExpression' && !object.computed) { chain.unshift(object.property.name); object = object.object; }
  return { ...call, kind: 'member', computed: callee.computed, name: callee.computed ? '[]' : callee.property.name, chain,
    base: object?.type === 'Identifier' ? object.name : object?.type === 'ThisExpression' ? 'this' : null,
    baseCall: object?.type === 'CallExpression' && object.callee.type === 'Identifier' ? object.callee.name : null };
}

export function argumentFunction(ctx, fn, argument) {
  if (FN.has(argument.type)) return argument.__fn;
  if (argument.type === 'CallExpression' && argument.callee.type === 'Identifier') {
    const target = namedFunction(ctx, fn.file, argument.callee.name);
    return target && ctx.returnedFunctions.get(target);
  }
  if (argument.type !== 'Identifier') return null;
  const scope = ctx.scopes.get(fn);
  for (const owner of scope.chain) { const target = ctx.inner.get(owner.node)?.[argument.name]?.[0]; if (target) return target; }
  return namedFunction(ctx, fn.file, argument.name);
}

export function registers(call, ctx, fn) { return REGISTER.has(call.name) || (ctx.importsOf[fn.file][call.name]?.module === 'hono/validator' && call.name === 'validator'); }

export function rootIdentifier(node) {
  while (node) {
    if (node.type === 'Identifier') return node.name;
    if (node.type === 'MemberExpression') node = node.object;
    else if (node.type === 'CallExpression' || node.type === 'NewExpression') node = node.callee;
    else if (node.type === 'ChainExpression') node = node.expression;
    else return null;
  }
  return null;
}


/** 옵션 객체의 함수 필드도 실제 인수에서만 수집한다. */
export function argumentCallbacks(ctx, fn, argument, prefix) {
  const out = [], pending = [{ argument, prefix }];
  while (pending.length) {
    const item = pending.pop(), cb = argumentFunction(ctx, fn, item.argument);
    if (cb) out.push({ param: item.prefix, cb });
    if (item.argument.type !== 'ObjectExpression') continue;
    for (const property of item.argument.properties) {
      const key = property.key?.name ?? property.key?.value;
      if (key !== undefined && property.value) pending.push({ argument: property.value, prefix: item.prefix + '.' + key });
    }
  }
  return out;
}

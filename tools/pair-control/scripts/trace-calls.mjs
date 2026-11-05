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
  const callee = node.callee, call = { line: node.loc.start.line, args: node.arguments, node };
  if (callee.type === 'Identifier') return { ...call, kind: 'id', name: callee.name, isNew: node.type === 'NewExpression' };
  if (callee.type !== 'MemberExpression' || callee.computed || !callee.property?.name) return { ...call, kind: 'member', computed: true, name: '[]', base: null, chain: [] };
  const chain = []; let object = callee.object;
  while (object?.type === 'MemberExpression' && !object.computed) { chain.unshift(object.property.name); object = object.object; }
  return { ...call, kind: 'member', computed: false, name: callee.property.name, chain,
    base: object?.type === 'Identifier' ? object.name : object?.type === 'ThisExpression' ? 'this' : null,
    baseCall: object?.type === 'CallExpression' && object.callee.type === 'Identifier' ? object.callee.name : null };
}

export function argumentFunction(ctx, fn, argument) {
  if (FN.has(argument.type)) return argument.__fn;
  if (argument.type !== 'Identifier') return null;
  const scope = ctx.scopes.get(fn);
  for (const owner of scope.chain) { const target = ctx.inner.get(owner.node)?.[argument.name]?.[0]; if (target) return target; }
  return namedFunction(ctx, fn.file, argument.name);
}

export function registers(call) { return REGISTER.has(call.name); }

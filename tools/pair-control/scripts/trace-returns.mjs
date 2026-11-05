import { children } from './trace-ast.mjs';
import { FN } from './trace-config.mjs';

export function objectMembers(node) {
  const members = {};
  if (node?.type !== 'ObjectExpression') return members;
  for (const property of node.properties) {
    const key = property.key?.name ?? property.key?.value;
    if (key !== undefined && property.value?.__fn) members[key] = property.value.__fn;
  }
  return members;
}

/** 팩터리가 실제 반환한 함수·객체만 연결한다. 함수 이름으로 반환 대상을 추정하지 않는다. */
export function indexReturns(ctx) {
  ctx.returnedFunctions = new Map(); ctx.returnedMembers = new Map();
  for (const fn of ctx.fns) {
    const body = fn.node.body;
    if (body.__fn) ctx.returnedFunctions.set(fn, body.__fn);
    if (body.type === 'ObjectExpression') ctx.returnedMembers.set(fn, objectMembers(body));
    const pending = [body];
    while (pending.length) {
      const node = pending.pop(); if (!node || FN.has(node.type)) continue;
      if (node.type === 'ReturnStatement') {
        if (node.argument?.__fn) ctx.returnedFunctions.set(fn, node.argument.__fn);
        if (node.argument?.type === 'ObjectExpression') ctx.returnedMembers.set(fn, objectMembers(node.argument));
      }
      pending.push(...children(node));
    }
  }
}

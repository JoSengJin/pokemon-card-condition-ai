import { callsOf, argumentFunction, argumentCallbacks, registers } from './trace-calls.mjs';
import { resolveId } from './trace-resolve-id.mjs';
import { resolveMember } from './trace-resolve-member.mjs';

export function collectGraph(ctx) {
  ctx.callbackForwards = [];
  for (const fn of [...ctx.fns, ...ctx.modules]) {
    const edges = []; ctx.graph.set(fn, edges);
    for (const call of callsOf(ctx, fn)) {
      const result = call.kind === 'id' ? resolveId(ctx, fn, call) : resolveMember(ctx, fn, call);
      if (result.callbackParam) { edges.push({ param: result.callbackParam, owner: result.callbackOwner ?? ctx.scopes.get(fn).paramOwners.get(result.callbackParam), fallbackReason: result.fallbackReason, call }); continue; }
      if (result.how === 'unresolved' || result.how === 'external') recordCall(ctx, fn, call, result.how, result.reason);
      for (const target of result.to ?? []) {
        edges.push({ to: target, w: 1, how: result.how });
        for (let index = 0; index < call.args.length; index++) {
          const parameter = target.node.params[index];
          const id = parameter?.type === 'AssignmentPattern' ? parameter.left : parameter;
          if (id?.type !== 'Identifier') continue;
          const callbacks = argumentCallbacks(ctx, fn, call.args[index], id.name);
          if (!callbacks.length) {
            const argument = call.args[index], owner = argument.type === 'Identifier' && ctx.scopes.get(fn).paramOwners.get(argument.name);
            if (owner) ctx.callbackForwards.push({ owner, param: argument.name, target, targetParam: id.name });
            continue;
          }
          if (!ctx.callbacks.has(target)) ctx.callbacks.set(target, []);
          ctx.callbacks.get(target).push(...callbacks);
        }
      }
      if (result.how !== 'external' || registers(call)) continue;
      for (const argument of call.args) {
        const cb = argumentFunction(ctx, fn, argument);
        if (!cb) continue;
        edges.push({ to: cb, w: 1, how: 'external-callback:' + call.name });
        if (call.isNew && call.name === 'Promise') for (const param of cb.node.params) if (param.type === 'Identifier') {
          if (!ctx.externalParams.has(cb)) ctx.externalParams.set(cb, new Set());
          ctx.externalParams.get(cb).add(param.name);
        }
      }
    }
  }
}

export function recordCall(ctx, fn, call, kind, reason) {
  ctx[kind].push({ file: fn.file, line: call.line, caller: fn.name,
    call: (call.base ?? '') + (call.chain ?? []).map((part) => '.' + part).join('') + (call.kind === 'id' ? call.name : '.' + call.name), reason });
}

export function settleCallbacks(ctx) {
  propagateCallbacks(ctx);
  for (const [fn, edges] of ctx.graph) {
    const out = [];
    for (const edge of edges) {
      if (edge.to) { out.push(edge); continue; }
      let found = false;
      for (const caller of ctx.callbacks.get(edge.owner) ?? []) if (caller.param === edge.param) { out.push({ to: caller.cb, w: 1, how: 'callback-param' }); found = true; }
      if (found) continue;
      const parameter = edge.owner?.node.params.find((item) => (item.type === 'AssignmentPattern' ? item.left.name : item.name) === edge.param);
      if (parameter?.type === 'AssignmentPattern' && parameter.right.__fn) { out.push({ to: parameter.right.__fn, w: 1, how: 'default-callback' }); continue; }
      if (edge.fallbackReason) { recordCall(ctx, fn, edge.call, 'external', edge.fallbackReason); continue; }
      const external = ctx.externalParams.get(edge.owner)?.has(edge.param);
      recordCall(ctx, fn, edge.call, external ? 'external' : 'unresolved', external ? 'Promise 생성자가 제공한 완료 콜백' : '콜백 매개변수의 실제 전달 함수 미확인');
    }
    ctx.graph.set(fn, out);
  }
}

export function propagateCallbacks(ctx) {
  let changed = true;
  while (changed) {
    changed = false;
    for (const forward of ctx.callbackForwards) for (const source of ctx.callbacks.get(forward.owner) ?? []) {
      if (source.param !== forward.param && !source.param.startsWith(forward.param + '.')) continue;
      const param = forward.targetParam + source.param.slice(forward.param.length);
      if (!ctx.callbacks.has(forward.target)) ctx.callbacks.set(forward.target, []);
      const targets = ctx.callbacks.get(forward.target); let present = false;
      for (const target of targets) if (target.param === param && target.cb === source.cb) present = true;
      if (!present) { targets.push({ param, cb: source.cb }); changed = true; }
    }
  }
}

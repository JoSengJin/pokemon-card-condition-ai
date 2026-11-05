import { GLOBAL_CALLS } from './trace-config.mjs';
import { exported } from './trace-bindings.mjs';

export function resolveId(ctx, fn, call) {
  const imports = ctx.importsOf[fn.file], scope = ctx.scopes.get(fn);
  for (const owner of scope.chain) { const inner = ctx.inner.get(owner.node)?.[call.name]; if (inner?.length) return { to: inner, how: 'local' }; }
  const same = ctx.top[fn.file + ':' + call.name];
  if (same?.length) return { to: same, how: 'same-file' };
  const factory = ctx.factories[fn.file + ':' + call.name];
  if (factory) return factory;
  const imp = imports[call.name];
  if (call.isNew && imp?.file && ctx.classes[imp.imported]) return { to: ctx.methods[imp.imported + ':constructor'] ?? [], how: 'new:' + call.name };
  if (imp?.file) { const to = exported(ctx, imp.file, imp.imported); return to.length ? { to, how: 'import' } : { to: [], how: 'unresolved', reason: 'import:' + imp.file + '에서 ' + imp.imported + ' 정의를 찾지 못함' }; }
  if (imp) return { to: [], how: 'external', reason: '외부 모듈 import(' + imp.imported + ')' };
  if (scope.params.has(call.name)) return { callbackParam: call.name };
  if (call.isNew && ctx.classes[call.name]) return { to: ctx.methods[call.name + ':constructor'] ?? [], how: 'new:' + call.name };
  if (scope.names.has(call.name)) return { to: [], how: 'unresolved', reason: '지역 변수(별칭·구조분해 포함)를 호출 — 대상 미확인' };
  if (GLOBAL_CALLS.has(call.name)) return { to: [], how: 'external', reason: '전역 표준 함수 ' + call.name };
  return { to: [], how: 'unresolved', reason: '선언을 찾지 못한 식별자 호출' };
}

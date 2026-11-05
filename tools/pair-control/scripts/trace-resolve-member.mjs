import { EXTERNAL, FRAMEWORK, STANDARD } from './trace-config.mjs';
import { exported, exportedValue, namedFunction } from './trace-bindings.mjs';
import { schemaFor } from './trace-schema.mjs';
import { memberTargets } from './trace-members.mjs';

export function resolveMember(ctx, fn, call) {
  const { base, chain, name } = call, imports = ctx.importsOf[fn.file], scope = ctx.scopes.get(fn);
  const assigned = memberTargets(ctx, fn, call);
  if (assigned.length) return { to: assigned, how: call.computed ? 'computed-table' : 'assigned-member' };
  const returned = !call.chain.length && (scope.objects.get(base) ?? scope.locals.get(base)?.members)?.[name];
  if (returned) return { to: [returned], how: 'returned-object' };
  if (call.computed) return { to: [], how: 'unresolved', reason: '계산된 멤버 호출' };
  const receiver = call.node.callee.object;
  if (name === 'push' && receiver?.type === 'AssignmentExpression' && receiver.operator === '=' && receiver.right.type === 'ArrayExpression') return { to: [], how: 'external', reason: '배열 리터럴을 대입한 수신 객체의 push' };
  const value = imports[base]?.file ? exportedValue(ctx, imports[base].file, imports[base].imported) : ctx.values[fn.file + ':' + base];
  const constructor = value?.node?.type === 'NewExpression' && value.node.callee.type === 'Identifier' ? ctx.importsOf[value.file][value.node.callee.name] : null;
  if (constructor?.module.startsWith('node:') && !chain.length) return { to: [], how: 'external', reason: 'Node 표준 클래스 인스턴스 ' + constructor.module + ':' + constructor.imported + '.' + name + '(전달 프로젝트 콜백은 별도 연결)' };
  const global = ctx.values[fn.file + ':' + base]?.node;
  if (!chain.length && (global?.type === 'ArrayExpression' || (global?.type === 'NewExpression' && /^(Set|Map|WeakSet|WeakMap|Array|Date|RegExp)$/.test(global.callee.name) && !ctx.top[fn.file + ':' + global.callee.name] && !imports[global.callee.name]))) return { to: [], how: 'external', reason: '표준 컨테이너의 모듈 변수 ' + base + '의 메서드 ' + name };
  const schema = schemaFor(ctx, fn, call);
  if (schema) {
    if (['parse', 'safeParse', 'parseAsync', 'safeParseAsync'].includes(name) && schema.validators.size) return { to: [...schema.validators], how: 'schema-validator:' + schema.key };
    return { to: [], how: 'external', reason: 'zod 스키마 ' + schema.key + '의 메서드 ' + name };
  }
  if (base && imports[base]?.ns && imports[base].file && chain.length === 1) {
    const value = exportedValue(ctx, imports[base].file, chain[0]);
    if (value?.node?.regex) return { to: [], how: 'external', reason: '정규식 export ' + value.file + ':' + value.name + '의 메서드 ' + name };
  }
  if (base && imports[base]?.ns && imports[base].file) { const to = exported(ctx, imports[base].file, name); return to.length ? { to, how: 'namespace' } : { to: [], how: 'unresolved', reason: imports[base].file + '에서 ' + name + ' 정의를 찾지 못함' }; }
  if (base && imports[base] && !imports[base].file) return { to: [], how: 'external', reason: '외부 모듈 ' + base + '의 멤버' };
  let type = base === 'this' ? fn.cls : base ? scope.types[base] ?? ctx.globalTypes[fn.file + ':' + base] : null;
  if (!type && base && imports[base]?.file) {
    const value = exportedValue(ctx, imports[base].file, imports[base].imported);
    if (value) type = ctx.globalTypes[value.file + ':' + value.name];
  }
  if (!type && !base && call.baseCall) { const target = namedFunction(ctx, fn.file, call.baseCall); type = target && ctx.returns.get(target); }
  if (!type && base) {
    const local = scope.locals.get(base);
    if (local?.cls) type = local.cls;
    else if (local?.std && !chain.length) return { to: [], how: 'external', reason: '표준 컨테이너 지역 변수 ' + base + '(' + local.std + ')의 메서드 ' + name };
  }
  let rawType = null;
  for (const segment of chain) {
    const raw = type && ctx.dataFields[type]?.[segment];
    const next = type && (ctx.classes[type]?.fields[segment] ?? (raw && /^[A-Z]\w*$/.test(raw) ? raw : null));
    if (!next && raw) rawType = raw;
    type = next; if (!type) break;
  }
  if (rawType && /(\[\]|^Array<|^Set<|^Map<|^Record<|^string\b|^Partial<Record)/.test(rawType) && !rawType.includes('=>') && chain.length) return { to: [], how: 'external', reason: '데이터 컬렉션 필드(' + chain.join('.') + ': ' + rawType.slice(0, 40) + ')의 메서드 ' + name };
  if (type && ctx.classes[type]) {
    const to = ctx.methods[type + ':' + name], binding = ctx.constructorParams[type + ':' + name];
    if (to?.length) return { to, how: 'type:' + type };
    if (binding) return { callbackParam: binding.param, callbackOwner: binding.owner };
    return { to: [], how: 'unresolved', reason: type + '에 ' + name + ' 메서드 없음' };
  }
  if (base && EXTERNAL.test(base)) return { to: [], how: 'external', reason: '전역 객체 ' + base };
  const defined = ctx.definedNames.has(name);
  if (scope.params.has(base)) return { callbackParam: [base, ...chain, name].join('.'), callbackOwner: scope.paramOwners.get(base), fallbackReason: !defined && STANDARD.has(name) ? '표준 메서드 ' + name + '(프로젝트 콜백 전달·같은 이름 정의 없음)' : null };
  if (!defined && FRAMEWORK.has(name)) return { to: [], how: 'external', reason: '프레임워크(Mastra·zod) 메서드 ' + name + '(같은 이름의 프로젝트 정의 없음)' };
  if (!defined && STANDARD.has(name)) return { to: [], how: 'external', reason: '표준 메서드 ' + name + '(같은 이름의 프로젝트 정의 없음)' };
  return { to: [], how: 'unresolved', reason: defined ? '같은 이름 프로젝트 정의 존재 — 호출 대상 미확정' : '표준 목록에 없는 메서드 ' + name + ' — 외부 여부 미확인' };
}

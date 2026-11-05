import { EXTERNAL, FRAMEWORK, STANDARD } from './trace-config.mjs';
import { exported, namedFunction } from './trace-bindings.mjs';

export function resolveMember(ctx, fn, call) {
  const { base, chain, name } = call, imports = ctx.importsOf[fn.file], scope = ctx.scopes.get(fn);
  if (call.computed) return { to: [], how: 'unresolved', reason: '계산된 멤버 호출' };
  if (base && imports[base]?.ns && imports[base].file) { const to = exported(ctx, imports[base].file, name); return to.length ? { to, how: 'namespace' } : { to: [], how: 'unresolved', reason: imports[base].file + '에서 ' + name + ' 정의를 찾지 못함' }; }
  if (base && imports[base] && !imports[base].file) return { to: [], how: 'external', reason: '외부 모듈 ' + base + '의 멤버' };
  let type = base === 'this' ? fn.cls : base ? scope.types[base] : null;
  if (!type && !base && call.baseCall) { const target = namedFunction(ctx, fn.file, call.baseCall); type = target && ctx.returns.get(target); }
  if (!type && base && !chain.length) {
    const local = scope.locals.get(base);
    if (local?.cls) type = local.cls;
    else if (local?.std) return { to: [], how: 'external', reason: '표준 컨테이너 지역 변수 ' + base + '(' + local.std + ')의 메서드 ' + name };
  }
  let rawType = null;
  for (const segment of chain) {
    const raw = type && ctx.dataFields[type]?.[segment];
    const next = type && (ctx.classes[type]?.fields[segment] ?? (raw && /^[A-Z]\w*$/.test(raw) ? raw : null));
    if (!next && raw) rawType = raw;
    type = next; if (!type) break;
  }
  if (rawType && /(\[\]|^Array<|^Set<|^Map<|^Record<|^string\b|^Partial<Record)/.test(rawType) && !rawType.includes('=>') && chain.length) return { to: [], how: 'external', reason: '데이터 컬렉션 필드(' + chain.join('.') + ': ' + rawType.slice(0, 40) + ')의 메서드 ' + name };
  if (type && ctx.classes[type]) { const to = ctx.methods[type + ':' + name]; return to?.length ? { to, how: 'type:' + type } : { to: [], how: 'unresolved', reason: type + '에 ' + name + ' 메서드 없음' }; }
  if (base && EXTERNAL.test(base)) return { to: [], how: 'external', reason: '전역 객체 ' + base };
  const defined = ctx.definedNames.has(name);
  if (!defined && FRAMEWORK.has(name)) return { to: [], how: 'external', reason: '프레임워크(Mastra·zod) 메서드 ' + name + '(같은 이름의 프로젝트 정의 없음)' };
  if (!defined && STANDARD.has(name)) return { to: [], how: 'external', reason: '표준 메서드 ' + name + '(같은 이름의 프로젝트 정의 없음)' };
  return { to: [], how: 'unresolved', reason: defined ? '같은 이름 프로젝트 정의 존재 — 호출 대상 미확정' : '표준 목록에 없는 메서드 ' + name + ' — 외부 여부 미확인' };
}

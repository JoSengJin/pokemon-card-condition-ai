import { children } from './trace-ast.mjs';
import { rootIdentifier } from './trace-calls.mjs';
import { exportedValue } from './trace-bindings.mjs';

/** zod에서 만들어진 값만 색인하고, 중첩 스키마의 실제 프로젝트 검증 콜백을 전파한다. */
export function indexSchemas(ctx) {
  ctx.schemas = {};
  for (const [key, value] of Object.entries(ctx.values)) {
    const origin = rootIdentifier(value.node), imported = ctx.importsOf[value.file]?.[origin];
    if (imported?.module === 'zod') ctx.schemas[key] = { key, value, validators: new Set(), dependencies: new Set() };
  }
  let discovered = true;
  while (discovered) {
    discovered = false;
    for (const [key, value] of Object.entries(ctx.values)) {
      if (ctx.schemas[key]) continue;
      const node = value.node, origin = rootIdentifier(node), imported = ctx.importsOf[value.file]?.[origin];
      const base = imported?.file ? exportedValue(ctx, imported.file, imported.imported) : ctx.values[value.file + ':' + origin];
      const method = node?.type === 'CallExpression' && node.callee.type === 'MemberExpression' ? node.callee.property?.name : null;
      if (!base || !ctx.schemas[base.file + ':' + base.name] || (node.type !== 'Identifier' && !['refine', 'superRefine', 'optional', 'nullable', 'default', 'array', 'min', 'max', 'regex', 'trim'].includes(method))) continue;
      ctx.schemas[key] = { key, value, validators: new Set(), dependencies: new Set() }; discovered = true;
    }
  }
  for (const schema of Object.values(ctx.schemas)) {
    const pending = [schema.value.node];
    while (pending.length) {
      const node = pending.pop(); if (!node) continue;
      if (node.type === 'CallExpression' && node.callee.type === 'MemberExpression' && ['refine', 'superRefine'].includes(node.callee.property?.name)) {
        for (const argument of node.arguments) if (argument.__fn) schema.validators.add(argument.__fn);
      }
      if (node.type === 'Identifier') {
        const imported = ctx.importsOf[schema.value.file]?.[node.name];
        const value = imported?.file ? exportedValue(ctx, imported.file, imported.imported) : ctx.values[schema.value.file + ':' + node.name];
        const key = value && value.file + ':' + value.name;
        if (key && key !== schema.key && ctx.schemas[key]) schema.dependencies.add(key);
      }
      pending.push(...children(node));
    }
  }
  let changed = true;
  while (changed) {
    changed = false;
    for (const schema of Object.values(ctx.schemas)) for (const dependency of schema.dependencies) for (const validator of ctx.schemas[dependency].validators) {
      if (!schema.validators.has(validator)) { schema.validators.add(validator); changed = true; }
    }
  }
}

export function schemaFor(ctx, fn, call) {
  const imported = ctx.importsOf[fn.file]?.[call.base];
  const value = imported?.file ? exportedValue(ctx, imported.file, imported.imported) : ctx.values[fn.file + ':' + call.base];
  const schema = value && ctx.schemas[value.file + ':' + value.name];
  if (schema && !call.chain.length) return schema;
  const origin = ctx.importsOf[fn.file]?.[call.origin];
  return origin?.module === 'zod' ? { key: origin.module, validators: new Set() } : null;
}

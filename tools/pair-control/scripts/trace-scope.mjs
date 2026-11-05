import { localDeclarations, patternNames } from './trace-ast.mjs';
import { localType } from './trace-scope-types.mjs';
import { namedFunction } from './trace-bindings.mjs';

export function indexScopes(ctx) {
  for (const fn of [...ctx.fns, ...ctx.modules]) {
    const scope = { params: new Set(), paramOwners: new Map(), objects: new Map(), types: {}, locals: new Map(), names: new Set(), chain: [] };
    for (let current = fn; current; current = current.owner?.__fn) scope.chain.push(current);
    for (let i = scope.chain.length - 1; i >= 0; i--) {
      const owner = scope.chain[i];
      for (const parameter of owner.node.params ?? []) {
        for (const name of patternNames(parameter)) { scope.params.add(name); scope.paramOwners.set(name, owner); }
        const id = parameter.type === 'AssignmentPattern' ? parameter.left : parameter;
        if (id?.type !== 'Identifier') continue;
        const match = /^\s*\??\s*:\s*([A-Z]\w*)/.exec(ctx.parsed[owner.file].orig.slice(id.end, id.end + 80));
        if (match) scope.types[id.name] = match[1];
        const annotation = /^\s*\??\s*:\s*(string|number|boolean|Array<[^>]+>|(?:string|number|boolean|[A-Z]\w*)\[\])/.exec(ctx.parsed[owner.file].orig.slice(id.end, id.end + 120));
        if (annotation) scope.locals.set(id.name, { std: '매개변수 주석 ' + annotation[1] });
        const returned = /^\s*\??\s*:\s*ReturnType<\s*typeof\s+(\w+)\s*>/.exec(ctx.parsed[owner.file].orig.slice(id.end, id.end + 120));
        const target = returned && namedFunction(ctx, owner.file, returned[1]);
        if (target && ctx.returnedMembers.has(target)) scope.objects.set(id.name, ctx.returnedMembers.get(target));
      }
      for (const decl of localDeclarations(owner)) {
        for (const name of patternNames(decl.id)) scope.names.add(name);
        if (decl.id.type === 'Identifier') scope.locals.set(decl.id.name, localType(ctx, owner, decl));
      }
    }
    ctx.scopes.set(fn, scope);
  }
}

import path from 'node:path';
import { FN } from './trace-config.mjs';
import { children, nameOf } from './trace-ast.mjs';

export function indexFunctions(ctx) {
  for (const file of ctx.files) {
    ctx.exportsOf[file] = {}; ctx.importsOf[file] = {};
    const pending = [{ node: ctx.parsed[file].ast, parent: null, owner: null, cls: null }];
    while (pending.length) {
      const frame = pending.pop(), node = frame.node;
      let owner = frame.owner, cls = frame.cls;
      if (node.type === 'ClassDeclaration') { cls = node.id.name; ctx.classes[cls] = { file, node, fields: {} }; }
      if (FN.has(node.type)) {
        const binding = node.type === 'FunctionDeclaration' || frame.parent?.type === 'VariableDeclarator';
        const fn = { file, name: nameOf(node, frame.parent), binding, node, cls, owner: owner?.node ?? null, kind: frame.parent?.type === 'MethodDefinition' ? frame.parent.kind : 'fn' };
        ctx.fns.push(fn); node.__fn = fn; owner = fn;
      }
      const nodes = children(node);
      for (let i = nodes.length - 1; i >= 0; i--) pending.push({ node: nodes[i], parent: node, owner, cls });
    }
  }
}

export function indexModules(ctx) {
  for (const file of ctx.files) for (const node of ctx.parsed[file].ast.body) {
    if (node.type === 'ImportDeclaration') {
      const rel = node.source.value.startsWith('.') ? path.normalize(path.join(path.dirname(file), node.source.value)) : null;
      for (const spec of node.specifiers) ctx.importsOf[file][spec.local.name] = { file: rel, module: node.source.value, ns: spec.type === 'ImportNamespaceSpecifier', imported: spec.imported?.name ?? 'default' };
    }
    if (node.type !== 'ExportNamedDeclaration') continue;
    if (node.declaration?.type === 'FunctionDeclaration') ctx.exportsOf[file][node.declaration.id.name] = node.declaration.id.name;
    if (node.declaration?.type === 'VariableDeclaration') for (const decl of node.declaration.declarations) ctx.exportsOf[file][decl.id.name] = decl.id.name;
    if (node.source) {
      const rel = path.normalize(path.join(path.dirname(file), node.source.value));
      for (const spec of node.specifiers) ctx.exportsOf[file][spec.exported.name] = { from: rel, name: spec.local.name };
    }
  }
}

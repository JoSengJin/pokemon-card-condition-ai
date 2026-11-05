import { FN } from './trace-config.mjs';

export function children(node) {
  const out = [];
  for (const key of Object.keys(node)) {
    if (key.startsWith('__')) continue;
    const value = node[key];
    if (Array.isArray(value)) { for (const child of value) if (child && typeof child.type === 'string') out.push(child); }
    else if (value && typeof value.type === 'string') out.push(value);
  }
  return out;
}

export function nameOf(node, parent) {
  return node.id?.name || (parent?.type === 'VariableDeclarator' && parent.id.name)
    || (['MethodDefinition', 'Property', 'PropertyDefinition'].includes(parent?.type) && (parent.key?.name ?? parent.key?.value))
    || (parent?.type === 'AssignmentExpression' && parent.left.property?.name) || null;
}

export function patternNames(pattern) {
  const names = [], pending = [pattern];
  while (pending.length) {
    const node = pending.pop(); if (!node) continue;
    if (node.type === 'Identifier') names.push(node.name);
    else if (node.type === 'ObjectPattern') { for (const property of node.properties) pending.push(property.value ?? property.argument); }
    else if (node.type === 'ArrayPattern') pending.push(...node.elements);
    else if (node.type === 'AssignmentPattern') pending.push(node.left);
    else if (node.type === 'RestElement') pending.push(node.argument);
  }
  return names;
}

export function localDeclarations(fn) {
  const out = [], pending = [fn.node.body];
  while (pending.length) {
    const node = pending.pop(); if (!node) continue;
    if (FN.has(node.type)) continue;
    if (node.type === 'VariableDeclarator') out.push(node);
    pending.push(...children(node));
  }
  return out;
}

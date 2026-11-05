export function indexBindings(ctx) {
  ctx.getterNames = new Set();
  for (const fn of ctx.fns) {
    if (fn.kind === 'get') ctx.getterNames.add(fn.name);
    (ctx.byFile[fn.file] ??= []).push(fn);
    ctx.definedNames.add(fn.name);
    if (fn.binding && !fn.owner && !fn.cls && fn.name) (ctx.top[fn.file + ':' + fn.name] ??= []).push(fn);
    if (fn.cls && fn.name) (ctx.methods[fn.cls + ':' + fn.name] ??= []).push(fn);
    if (fn.binding && fn.owner && fn.name) {
      if (!ctx.inner.has(fn.owner)) ctx.inner.set(fn.owner, {});
      (ctx.inner.get(fn.owner)[fn.name] ??= []).push(fn);
    }
  }
  for (const file of ctx.files) for (const name of Object.keys(ctx.exportsOf[file])) {
    let currentFile = file, currentName = name; const seen = new Set();
    while (!seen.has(currentFile + ':' + currentName)) {
      seen.add(currentFile + ':' + currentName);
      const exp = ctx.exportsOf[currentFile]?.[currentName];
      if (!exp || typeof exp === 'string') { ctx.exported[file + ':' + name] = ctx.top[currentFile + ':' + (exp || currentName)] ?? []; break; }
      currentFile = exp.from; currentName = exp.name;
    }
  }
}

export function exported(ctx, file, name) { return ctx.exported[file + ':' + name] ?? ctx.top[file + ':' + name] ?? []; }

export function namedFunction(ctx, file, name) {
  const local = ctx.top[file + ':' + name]?.[0];
  if (local) return local;
  const imp = ctx.importsOf[file]?.[name];
  return imp?.file ? exported(ctx, imp.file, imp.imported)[0] : null;
}

/** node:util.promisify의 대상 출처까지 대조한다. 프로젝트 함수를 감싼 경우 원래 함수로 연결한다. */
export function indexPromiseFactories(ctx) {
  ctx.factories = {};
  for (const file of ctx.files) for (const item of ctx.parsed[file].ast.body) {
    const declaration = item.declaration ?? item;
    if (declaration.type !== 'VariableDeclaration') continue;
    for (const variable of declaration.declarations) {
      const init = variable.init;
      if (variable.id.type !== 'Identifier' || init?.type !== 'CallExpression' || init.callee.type !== 'Identifier') continue;
      const factory = ctx.importsOf[file][init.callee.name], argument = init.arguments[0];
      if (factory?.module !== 'node:util' || factory.imported !== 'promisify' || argument?.type !== 'Identifier') continue;
      const target = namedFunction(ctx, file, argument.name), imported = ctx.importsOf[file][argument.name];
      if (target) ctx.factories[file + ':' + variable.id.name] = { to: [target], how: 'promisify-project' };
      else if (imported && !imported.file) ctx.factories[file + ':' + variable.id.name] = { to: [], how: 'external', reason: 'node:util.promisify가 감싼 외부 함수 ' + imported.module + ':' + imported.imported };
    }
  }
}

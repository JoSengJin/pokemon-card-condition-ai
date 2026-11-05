export function indexTypes(ctx) {
for (const c of Object.values(ctx.classes)) { // 클래스 필드 타입(`store: Store<State>`)
  const src = ctx.parsed[c.file].orig.slice(c.node.start, c.node.end);
  for (const m of src.matchAll(/^\s*(\w+)\s*[?!]?\s*:\s*([A-Z]\w*)(?:<[^>]*>)?\s*[;=]/gm)) c.fields[m[1]] = m[2]; // 필드 선언(`name: Type;` 또는 `= …`)
}

 // interface·type·class 필드의 원문 타입(`failures: {…}[]` 같은 데이터 컬렉션 판별용)
for (const f of ctx.files) {
  const text = ctx.parsed[f].orig;
  for (const m of text.matchAll(/(?:interface|type)\s+([A-Z]\w*)[^{=]*[={]\s*\{([\s\S]*?)\n\}|(?:interface|type)\s+([A-Z]\w*)[^{=]*\{([^}]*)\}/g)) {
    const name = m[1] ?? m[3], body = m[2] ?? m[4] ?? '';
    for (const q of body.matchAll(/(\w+)\??:\s*([^;\n]+)/g)) (ctx.dataFields[name] ??= {})[q[1]] = q[2].trim();
  }
}

}

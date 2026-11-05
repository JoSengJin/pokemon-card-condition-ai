export function gate(stages) {
  let wait = null;
  return stages.map((s) => {
    const out = wait && ['action', 'active'].includes(s.status)
      ? { ...s, status: 'todo', text: '앞 단계(' + wait.label + ') 완료 후', primary: null } : s;
    if (!wait && !['done', 'skipped'].includes(s.status) && !(s.key === 'review' && s.status !== 'active')) wait = s;
    return out;
  });
}

export function currentKey(stages) {
  const live = stages.find((x) => ['action', 'active', 'failed', 'warn'].includes(x.status) && x.key !== 'review');
  if (live) return live.key;
  const done = stages.filter((x) => x.status === 'done');
  return done.length ? done[done.length - 1].key : stages[0].key;
}

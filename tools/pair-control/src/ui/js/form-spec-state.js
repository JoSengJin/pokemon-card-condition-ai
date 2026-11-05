export const specs = { c: [], p: [] };

export function resetSpecs() {
  specs.c = [{ name: '공백 오류 검사', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'], cwd: '.' }];
  specs.p = [];
}

export function onSpecInput(el) {
  const row = el.closest('.specRow');
  if (!row || !el.dataset.k) return false;
  const c = specs[row.dataset.list][Number(row.dataset.i)];
  c[el.dataset.k] = el.dataset.k === 'args' ? el.value.split('\n').map((x) => x.trim()).filter(Boolean) : el.value;
  return true;
}

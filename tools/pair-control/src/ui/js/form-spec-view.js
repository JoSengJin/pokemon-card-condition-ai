import { esc } from './core.js';
import { specs } from './form-spec-state.js';

export function renderSpecs() {
  document.getElementById('checkRows').innerHTML = specRows(specs.c, 'c');
  document.getElementById('postRows').innerHTML = specRows(specs.p, 'p');
}

export function specRows(list, kind) {
  return list.map((c, i) => '<div class="specRow" data-list="' + kind + '" data-i="' + i + '">' +
    '<input data-k="name" value="' + esc(c.name) + '" placeholder="이름">' +
    '<select data-k="executable">' + ['git', 'node', '.venv/bin/python'].map((x) => '<option' + (x === c.executable ? ' selected' : '') + '>' + x + '</option>').join('') + '</select>' +
    '<textarea data-k="args" placeholder="인자 한 줄에 하나">' + esc(c.args.join('\n')) + '</textarea>' +
    (kind === 'c' ? '<input data-k="cwd" value="' + esc(c.cwd) + '" title="작업 폴더 기준 cwd">' : '') +
    '<button type="button" data-spec="rm">빼기</button></div>').join('') || '<div class="muted small">없음</div>';
}

export function onSpecClick(el) {
  if (!el) return false;
  const row = el.closest('.specRow');
  if (el.dataset.spec === 'rm' && row) specs[row.dataset.list].splice(Number(row.dataset.i), 1);
  else specs[el.dataset.spec === 'add-p' ? 'p' : 'c'].push({ name: '', executable: 'git', args: [], cwd: '.' });
  renderSpecs();
  return true;
}

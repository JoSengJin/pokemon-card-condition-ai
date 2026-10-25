// 새 작업 폼의 고급 설정: 작업 테스트(c)·통합 후 검사(p) 명령 줄 편집.
import { esc } from './core.js';

export const specs = { c: [], p: [] };

export function resetSpecs() {
  specs.c = [{ name: '공백 오류 검사', executable: 'git', args: ['diff', '--check', '{contract}', '{head}'], cwd: '.' }];
  specs.p = [];
}

export function renderSpecs() {
  document.getElementById('checkRows').innerHTML = specRows(specs.c, 'c');
  document.getElementById('postRows').innerHTML = specRows(specs.p, 'p');
}

function specRows(list, kind) {
  return list.map((c, i) => '<div class="specRow" data-list="' + kind + '" data-i="' + i + '">' +
    '<input data-k="name" value="' + esc(c.name) + '" placeholder="이름">' +
    '<select data-k="executable">' + ['git', 'node', '.venv/bin/python'].map((x) => '<option' + (x === c.executable ? ' selected' : '') + '>' + x + '</option>').join('') + '</select>' +
    '<textarea data-k="args" placeholder="인자 한 줄에 하나">' + esc(c.args.join('\n')) + '</textarea>' +
    (kind === 'c' ? '<input data-k="cwd" value="' + esc(c.cwd) + '" title="작업 폴더 기준 cwd">' : '') +
    '<button type="button" data-spec="rm">빼기</button></div>').join('') || '<div class="muted small">없음</div>';
}

/** 명령 줄 입력을 specs에 반영한다. 처리했으면 true. */
export function onSpecInput(el) {
  const row = el.closest('.specRow');
  if (!row || !el.dataset.k) return false;
  const c = specs[row.dataset.list][Number(row.dataset.i)];
  c[el.dataset.k] = el.dataset.k === 'args' ? el.value.split('\n').map((x) => x.trim()).filter(Boolean) : el.value;
  return true;
}

/** 추가·빼기 버튼. 처리했으면 true. */
export function onSpecClick(el) {
  if (!el) return false;
  const row = el.closest('.specRow');
  if (el.dataset.spec === 'rm' && row) specs[row.dataset.list].splice(Number(row.dataset.i), 1);
  else specs[el.dataset.spec === 'add-p' ? 'p' : 'c'].push({ name: '', executable: 'git', args: [], cwd: '.' });
  renderSpecs();
  return true;
}

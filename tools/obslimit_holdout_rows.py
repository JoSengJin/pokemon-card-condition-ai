"""Build C5 holdout rows from pasted label lines `ebay-pair-<id>/back=<정상|제한|미확인>`. 미확인 rows are left out (count reported); the later of repeated lines wins only if identical, else the id is rejected."""
import hashlib
import json
import sys
from pathlib import Path

TARGET = {'정상': 0, '제한': 1}


def parse(text):
    answers = {}
    for line in text.splitlines():
        if '/back=' not in line:
            continue
        key, value = line.strip().split('/back=')
        if answers.setdefault(key, value) != value:
            raise ValueError('Conflicting answers for ' + key)
    return answers


def main(answers_path, out_path, *review_paths):
    answers = parse(Path(answers_path).read_text(encoding='utf-8'))
    rows, unknown = [], 0
    for path in review_paths:
        for r in map(json.loads, Path(path).read_text(encoding='utf-8').splitlines()):
            back = (r.get('side_annotations') or {}).get('back')
            value = answers.get(r.get('id'))
            if r.get('excluded') or not back or value is None:
                continue
            if value not in TARGET:
                unknown += 1
                continue
            digest = hashlib.sha256(Path(back['image']).read_bytes()).hexdigest()
            rows.append(dict(id=r['id'] + '/back/observation_limited', group=r['id'], split='test', image=back['image'], side='back',
                             target=TARGET[value], box=back['box'], image_sha256=digest))
    Path(out_path).write_text(json.dumps(rows, ensure_ascii=False))
    return dict(rows=len(rows), positive=sum(r['target'] for r in rows), unknown=unknown, answered=len(answers))


if __name__ == '__main__':
    print(main(*sys.argv[1:]))

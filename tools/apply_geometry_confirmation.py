"""Copy a manifest, setting box_reviewed only for user-confirmed faces; nothing else changes."""
import hashlib
import json
import sys
from pathlib import Path


def apply(source, pending, answers, output):
    boxes = {p['id']: p['box'] for p in json.loads(Path(pending).read_text())}
    confirmed = {k for k, v in answers.items() if v == '맞음'}
    if not confirmed <= set(boxes):
        raise ValueError('Confirmed face is not a pending face')
    lines, done = [], set()
    for line in Path(source).read_text().splitlines():
        row = json.loads(line)
        for side, annotation in row.get('side_annotations', {}).items():
            ident = f"{row['id']}/{side}"
            if ident in confirmed:
                if annotation['box'] != boxes[ident] or annotation.get('box_reviewed') is True:
                    raise ValueError('Box changed or already reviewed: ' + ident)
                annotation['box_reviewed'] = True
                done.add(ident)
        lines.append(json.dumps(row, ensure_ascii=False))
    if done != confirmed:
        raise ValueError('Faces missing in manifest: ' + str(confirmed - done))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=False)
    output.write_text('\n'.join(lines) + '\n')
    return sorted(done), hashlib.sha256(output.read_bytes()).hexdigest()


if __name__ == '__main__':
    answers = dict(l.split('=') for l in Path(sys.argv[3]).read_text().split())
    print(apply(*sys.argv[1:3], answers, sys.argv[4]))

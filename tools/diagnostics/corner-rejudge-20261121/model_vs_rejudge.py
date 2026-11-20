"""Read-only diagnostic: stored candidate-E OOF scores on the 60 re-judged corner zones, split by whether the original label was reproduced. Labels are not changed; the model never decides a label."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import score  # noqa: E402

D = Path('artifacts/corner-rejudge-20261121')


def auc(pos, neg):
    return sum((x > y) + .5*(x == y) for x in pos for y in neg)/(len(pos)*len(neg)) if pos and neg else None


def main():
    sel = json.loads((D/'selection.json').read_text())
    ans = score.parse((D/'answers.txt').read_text())
    ans.update(score.parse((D/'answers-hi.txt').read_text()))
    obs = json.loads(Path('artifacts/experiments/20261102T140143-82781117/observations.json').read_text())
    s = {r['id']: x for r, x in zip(obs['rows'], obs['scores'])}
    out = {}
    for z in sel:
        a = ans[z['n']]
        kind = 'unknown' if a == '불가' else 'consistent' if (z['target'] == 1) == (a == '결함') else 'flipped'
        out.setdefault(kind, []).append((z['target'], s[z['id']]))
    print({k: dict(n=len(v), auc_original_label=auc([x for t, x in v if t], [x for t, x in v if not t])) for k, v in out.items()})


if __name__ == '__main__':
    main()

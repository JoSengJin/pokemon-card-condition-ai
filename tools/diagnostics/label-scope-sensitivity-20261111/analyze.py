"""읽기 전용 what-if: 후보 판정으로 라벨을 가정 변경했을 때 저장 점수의 FP/FN. 학습·추론·라벨 변경 0."""
import json
import sys
from pathlib import Path
A = Path('artifacts')
EXP = A / 'experiments/20261108T215307-941b3aaa/observations.json'
ANS = A / 'mobile-candidate-review-complete-20261111/candidate-answers.json'
OUT = A / 'label-scope-sensitivity-20261111'


def load():
    obs = json.load(open(EXP)); ans = json.load(open(ANS))['responses']
    rows = {r['id']: dict(group=r['group'], target=r['target'], score=s) for r, s in zip(obs['rows'], obs['scores'])}
    return rows, {a['id'].split('/point-review/')[0]: a['judgment'] for a in ans}


def auc(items):
    pos = [s for t, s in items if t]; neg = [s for t, s in items if not t]
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def scenario(rows, judg, drop_unknown):
    items, fp_groups = [], set()
    for i, r in rows.items():
        j = judg.get(i)
        if drop_unknown and j == 'unknown':
            continue
        t = 1 if (j == 'defect' or r['target'] == 1) else 0
        items.append((t, r['score']))
        if r['target'] == 0 and t == 1 and r['score'] >= 0.5:
            fp_groups.add(r['group'])
    pos = [s for t, s in items if t]; neg = [s for t, s in items if not t]
    return dict(positives=len(pos), negatives=len(neg), FN=sum(s < 0.5 for s in pos), FP=sum(s >= 0.5 for s in neg),
                FN_rate=round(sum(s < 0.5 for s in pos) / len(pos), 4), FP_rate=round(sum(s >= 0.5 for s in neg) / len(neg), 4),
                AUC=round(auc(items), 5), relabeled_fp_groups=len(fp_groups))


def main():
    rows, judg = load()
    base = scenario(rows, {}, False)
    res = dict(S0=base, S1=scenario(rows, judg, False), S2=scenario(rows, judg, True))
    (OUT / 'results.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))


if __name__ == '__main__':
    sys.exit(main())

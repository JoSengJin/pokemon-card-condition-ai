"""확대 기준 별도 보기 라벨 생성(설계 zoom-standard-label-design-20261111 규칙). 원 라벨 불변, 학습·추론 0."""
import json
from pathlib import Path
from analyze import auc, EXP, OUT as _o
A = Path('artifacts'); OUT = A / 'zoom-standard-view-20261111'
AUD = A / 'candidate-score-audit-20261111/audit.json'


def build():
    obs = json.load(open(EXP)); audit = {x['id'].split('/point-review/')[0]: x for x in json.load(open(AUD))['rows']}
    labels = []
    for r, s in zip(obs['rows'], obs['scores']):
        a = audit.get(r['id']); view, rule = r['target'], 'R0_original'
        if a and a['target'] == 0 and a['judgment'] == 'defect':
            if a['inside_region'] and a['coverage'] >= 1 - 1e-9: view, rule = 1, 'R1_normal_label_candidate_defect'
            else: rule = 'R1x_defect_but_candidate_outside_region_not_promoted'
        elif a and a['target'] == 0 and a['judgment'] == 'unknown': view, rule = None, 'R3_normal_label_candidate_unknown'
        labels.append(dict(id=r['id'], group=r['group'], original=r['target'], view=view, rule=rule, score=s))
    return labels


def score(items):
    pos = [s for t, s in items if t]; neg = [s for t, s in items if not t]
    return dict(positives=len(pos), negatives=len(neg), FN=sum(s < .5 for s in pos), FP=sum(s >= .5 for s in neg),
                FN_rate=round(sum(s < .5 for s in pos) / len(pos), 4), FP_rate=round(sum(s >= .5 for s in neg) / len(neg), 4), AUC=round(auc(items), 5))


def main():
    L = build(); (OUT / 'labels.json').write_text(json.dumps(dict(note='evaluation view only; original labels unchanged', labels=L), ensure_ascii=False))
    import collections
    res = dict(rules=dict(collections.Counter(x['rule'] for x in L)),
               original=score([(x['original'], x['score']) for x in L]),
               zoom_view_unknown_excluded=score([(x['view'], x['score']) for x in L if x['view'] is not None]),
               zoom_view_unknown_original=score([(x['view'] if x['view'] is not None else x['original'], x['score']) for x in L]))
    (OUT / 'results.json').write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()

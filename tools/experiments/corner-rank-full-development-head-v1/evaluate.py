"""Join sealed truth to paired scores and compute the fixed card-level endpoints."""
from collections import Counter
from math import comb, inf, isfinite, nextafter, sqrt

from score import events

ARMS = ('e', 'rank')
LIMITS = {'miss': .10, 'false_alarm': .20}
Z95 = 1.6448536269514722


def wilson(errors, n):
    if not n:
        return None
    rate = errors/n
    z2 = Z95**2
    return (rate + z2/(2*n) + Z95*sqrt(rate*(1-rate)/n + z2/(4*n*n)))/(1 + z2/n)


def matched_budget(events_by_arm):
    normal = {a: [r['maximum'] for r in events_by_arm[a] if r['event'] == 'false_alarm'] for a in ARMS}
    budget = 10*len(normal['e'])//81
    choices = {}
    for arm, scores in normal.items():
        count = len(scores)
        thresholds = {count: 0.0}
        for score, ties in sorted(Counter(scores).items()):
            count -= ties
            thresholds[count] = nextafter(score, inf)
        choices[arm] = thresholds
    common = max(n for n in choices['e'].keys() & choices['rank'].keys() if n <= budget)
    return {'budget': budget, 'actual': common, 'exact': common == budget, 'arms': {
        a: {'threshold': choices[a][common], 'misses': sum(
            r['maximum'] < choices[a][common] for r in events_by_arm[a] if r['event'] == 'miss')}
        for a in ARMS}}


def paired_summary(before, after, limit):
    before_errors = {r['id'] for r in before if r['error']}
    after_errors = {r['id'] for r in after if r['error']}
    recovered, new = before_errors-after_errors, after_errors-before_errors
    b, m = len(recovered), len(recovered)+len(new)
    pvalue = sum(comb(m,k) for k in range(b,m+1))/2**m
    n = len(before)
    upper_e, upper_rank = wilson(len(before_errors),n), wilson(len(after_errors),n)
    return dict(n=n, e=len(before_errors), rank=len(after_errors),
                delta_pp=100*(len(after_errors)-len(before_errors))/n if n else None,
                both=sorted(before_errors & after_errors), recovered=sorted(recovered), new=sorted(new),
                neither=n-len(before_errors | after_errors), p_one_sided=pvalue,
                wilson95_e=upper_e, wilson95_rank=upper_rank,
                d3_e=bool(n and upper_e <= limit), d3_rank=bool(n and upper_rank <= limit),
                superiority=bool(b > len(new) and pvalue <= .05))


def compare(predictions, answers):
    ids = [row['id'] for row in predictions]
    if len(ids) != len(set(ids)) or ids != [row['id'] for row in answers]:
        raise ValueError('Frozen request and truth IDs/order differ')
    ledger, held = {a: [] for a in ARMS}, []
    subgroup = {}
    for row, truth in zip(predictions, answers, strict=True):
        if row['identity'] != truth['identity']:
            raise ValueError('Frozen photo or box differs')
        human = events(dict.fromkeys(truth['corners'], .0), truth['corners'])[0]
        scored = all(set(row[a]) == set(truth['corners']) and
                     all(isfinite(v) and 0<=v<=1 for v in row[a].values()) for a in ARMS)
        if not scored:
            held.append(row['id'])
        for dimension, labels in [('language', [truth['language']]), ('edition', [truth['edition']]),
                                  ('restriction', truth['restrictions'])]:
            for label in set(labels):
                sub = subgroup.setdefault(f'{dimension}:{label}', dict(
                    miss=0,false_alarm=0,held=0,e_miss=0,e_false_alarm=0,rank_miss=0,rank_false_alarm=0,
                    recovered_miss=0,recovered_false_alarm=0,new_miss=0,new_false_alarm=0))
                sub[human] += 1
                sub['held'] += int(not scored)
                if scored:
                    e, rank = (events(row[a],truth['corners'])[1] for a in ARMS)
                    sub['e_'+human] += int(e)
                    sub['rank_'+human] += int(rank)
                    sub['recovered_'+human] += int(e and not rank)
                    sub['new_'+human] += int(rank and not e)
        if scored:
            for a in ARMS:
                kind, error, maximum = events(row[a],truth['corners'])
                ledger[a].append(dict(id=row['id'],event=kind,error=error,maximum=maximum))
    if held:
        return dict(held=held, endpoints=None, d3=False, superiority=False, matched=None, subgroups=subgroup)
    endpoints = {kind: paired_summary(*([r for r in ledger[a] if r['event']==kind] for a in ARMS), limit)
                 for kind,limit in LIMITS.items()}
    return dict(held=[], endpoints=endpoints, d3=all(v['d3_rank'] for v in endpoints.values()),
                superiority=all(v['superiority'] for v in endpoints.values()),
                matched=matched_budget(ledger), subgroups=subgroup)

"""Score the blind corner re-judgment: flip rate f from the defect/normal disagreement with the earlier labels (symmetric independent-flip assumption), Wilson interval, 3-class kappa, pre-registered decision (see docs/superpowers/plans/2026-11-21-corner-blind-rejudge.md)."""
import math
import re

BOUND, Z = .11, 1.96


def parse(text):
    """'z12=결함' lines -> {12: '결함'|'정상'|'불가'|'미확인'}."""
    return {int(m.group(1)): m.group(2) for m in re.finditer(r'^z(\d+)=(정상|결함|불가|미확인)\s*$', text, re.M)}


def wilson(k, n):
    p, den = k/n, 1 + Z*Z/n
    mid, half = (p + Z*Z/(2*n))/den, Z*math.sqrt(p*(1 - p)/n + Z*Z/(4*n*n))/den
    return mid - half, mid + half


def score(selection, answers):
    flip = lambda d: (1 - math.sqrt(max(0., 1 - 2*d)))/2
    used = [(z['target'], answers[z['n']]) for z in selection if answers.get(z['n']) in ('정상', '결함')]
    unknown = sum(answers.get(z['n']) == '불가' for z in selection)
    disagree = sum((t == 1) != (a == '결함') for t, a in used)
    d = disagree/len(used)
    lo, hi = wilson(disagree, len(used))
    f, f_lo, f_hi = flip(d), flip(lo), flip(min(hi, .5))
    pa = sum((t == 1) == (a == '결함') for t, a in used)/len(used)
    p1, p2 = sum(t == 1 for t, _ in used)/len(used), sum(a == '결함' for _, a in used)/len(used)
    pe = p1*p2 + (1 - p1)*(1 - p2)
    decision = 'label_definition' if f >= BOUND else 'independent_data' if f_hi < BOUND else 'undetermined'
    return dict(used=len(used), unknown=unknown, unknown_rate=unknown/len(selection), disagree=disagree, d=d, f=f, f_ci=[f_lo, f_hi],
                kappa_binary=(pa - pe)/(1 - pe) if pe < 1 else None, decision=decision, unknown_too_high=unknown/len(selection) > .2)

"""Fixed warm card-level benchmark for the same two frozen heads."""
from hashlib import sha256
from math import ceil
from statistics import mean
from time import perf_counter_ns

import torch

from score import OFFSETS, score_card
from evaluate import ARMS

PHASES = {'e': OFFSETS[:1], 'rank': OFFSETS}


def timed(body, request, head, device, offsets):
    calls = {'backbone': 0}
    if device == 'mps':
        torch.mps.synchronize()
    start = perf_counter_ns()
    error = None
    try:
        scores = score_card(body, request, head, device, offsets, calls)
        inspected = {area for area, score in scores.items() if score >= .20}
        alarm = max(scores.values()) >= .60
        output = dict(scores=scores, inspected=inspected, alarm=alarm)
        if len(output['scores']) != 4:
            raise ValueError('Incomplete corner output')
    except (OSError, ValueError, RuntimeError) as exc:
        error = type(exc).__name__
    if device == 'mps':
        torch.mps.synchronize()
    return {'ms': (perf_counter_ns()-start)/1e6, 'backbone': calls['backbone'], 'error': error}


def benchmark(body, requests, answers, warm, heads, device):
    if len(warm) != 20:
        raise ValueError('Expected 20 preregistered warm-up cards')
    salt = 'corner-latency-v1/'
    cohorts = [[r for r,t in zip(requests,answers,strict=True)
                if any(t['corners'].values()) == positive] for positive in (True,False)]
    sample = [pair for group in cohorts for pair in sorted(
        group,key=lambda r:sha256((salt+r['id']).encode()).digest())[:25]]
    if len(sample) != 50:
        raise ValueError('Expected 25 defect and 25 normal cards for timing')
    for r in warm:
        for a in ARMS:
            score_card(body,r,heads[a],device,PHASES[a])
    rounds = []
    for turn in range(5):
        order = sorted(sample,key=lambda r:sha256((salt+str(turn)+'/'+r['id']).encode()).digest())
        for index,r in enumerate(order):
            arms = ARMS if (index+turn)%2 == 0 else ARMS[::-1]
            rounds.append(dict(id=r['id'], round=turn, order=arms,
                **{a: timed(body,r,heads[a],device,PHASES[a]) for a in arms}))
    good = [r for r in rounds if all(r[a]['error'] is None for a in ARMS)]
    values = {a:[r[a]['ms'] for r in good] for a in ARMS}
    values['rank_minus_e'] = [r['rank']['ms']-r['e']['ms'] for r in good]
    summary = {a:dict(mean_ms=mean(times),p95_ms=sorted(times)[ceil(.95*len(times))-1])
               for a,times in values.items() if times}
    return dict(valid=len(good)==250, successful_pairs=len(good), attempts=len(rounds), warmup_per_arm=20,
                p95_difference_ms=summary['rank']['p95_ms']-summary['e']['p95_ms'] if good else None,
                summary=summary, calls={a:sum(r[a]['backbone'] for r in rounds) for a in ARMS}, trials=rounds)

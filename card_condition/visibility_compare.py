"""Development diagnostics: score shifts must not masquerade as detection gains."""
import math

from .score_diagnostics import score_diagnostics
from .quality_rates import error_rates, rate_change
from .visibility_model import TARGET, class_group_weights


def checked_rows(report):
    if report.get('target') != TARGET or report.get('evaluation_kind') != 'validation_observation_limit':
        raise ValueError('Expected observation validation report')
    rows = report['predictions']
    keys = [(r['card_id'], r['side']) for r in rows]
    if not rows or len(set(keys)) != len(keys):
        raise ValueError('Empty or duplicate observation predictions')
    for row in rows:
        value = row['probabilities'][TARGET]
        if (row['split'] != 'val' or type(row['labels'][TARGET]) is not int
                or row['labels'][TARGET] not in (0, 1) or type(value) not in (int, float)
                or not math.isfinite(value) or not 0 <= value <= 1):
            raise ValueError('Invalid observation validation prediction')
    return rows


def quality_summary(report):
    rows = checked_rows(report)
    weights = class_group_weights(rows)
    scores = [r['probabilities'][TARGET] for r in rows]
    targets = [r['labels'][TARGET] for r in rows]
    # Clipping only avoids log(0) in diagnostics; never changes stored predictions.
    losses = [-math.log(max(1e-15, p if t else 1-p)) for t, p in zip(targets, scores)]
    bce = sum(w*l for w,l in zip(weights, losses)) / sum(weights)
    ranking = score_diagnostics(rows, [TARGET])[TARGET]
    counts = dict(tp=0, tn=0, fp=0, fn=0)
    for t, p in zip(targets, scores):
        guess = int(p >= .5)
        counts[('t' if t == guess else 'f') + ('p' if guess else 'n')] += 1
    beats_null = bce < math.log(2) and ranking['auroc'] > .5
    return dict(metrics_at_05=counts, rates_at_05=error_rates(counts), balanced_bce=bce, constant_half_bce=math.log(2),
        auroc=ranking['auroc'], average_precision=ranking['average_precision'],
        class_mean_scores={name: sum(p for t,p in zip(targets,scores) if t == label)/targets.count(label)
                           for label,name in ((0,'clear'),(1,'limited'))},
        beats_null_baseline=beats_null,
        status='baseline_only_not_production' if beats_null else 'insufficient_discrimination',
        production_ready=False, requires_gemini=True)


def tp_at_fp_budget(rows, budget):
    # Post-hoc ranking diagnostic only; this does not choose a deployable threshold.
    return max([0] + [sum(r['labels'][TARGET] == 1 and r['probabilities'][TARGET] >= threshold for r in rows)
        for threshold in {r['probabilities'][TARGET] for r in rows}
        if sum(r['labels'][TARGET] == 0 and r['probabilities'][TARGET] >= threshold for r in rows) <= budget])


def compare_reports(reference, candidate):
    left, right = checked_rows(reference), checked_rows(candidate)
    def identity(report, row):
        return (row['group'], row['split'], row['image'], row['box'], row['labels'],
                row['visibility_issues'], row['image_hashes'], report['input_hashes'][row['image']])
    before = {(r['card_id'],r['side']): r for r in left}
    after = {(r['card_id'],r['side']): r for r in right}
    if before.keys() != after.keys() or any(identity(reference,before[k]) != identity(candidate,after[k]) for k in before):
        raise ValueError('Validation photos, boxes, groups or truth differ; comparison refused')
    summaries = [quality_summary(report) for report in (reference,candidate)]
    budget = summaries[0]['metrics_at_05']['fp']
    detected = [tp_at_fp_budget(rows,budget) for rows in (left,right)]
    changes = [dict(card_id=k[0],side=k[1],truth=before[k]['labels'][TARGET],
        before=before[k]['probabilities'][TARGET],after=after[k]['probabilities'][TARGET],
        delta=after[k]['probabilities'][TARGET]-before[k]['probabilities'][TARGET]) for k in before]
    improves_ranking = (summaries[1]['auroc'] > summaries[0]['auroc']
        and summaries[1]['average_precision'] > summaries[0]['average_precision'] and detected[1] >= detected[0])
    return dict(reference=summaries[0],candidate=summaries[1],same_validation=True,
        rate_comparison_at_05=rate_change(summaries[0]['metrics_at_05'],summaries[1]['metrics_at_05']),
        fp_budget=budget,reference_tp_at_budget=detected[0],candidate_tp_at_budget=detected[1],
        paired_changes=changes,mean_delta=sum(r['delta'] for r in changes)/len(changes),
        increased=sum(r['delta'] > 0 for r in changes),faces=len(changes),
        ranking_improved=improves_ranking,
        research_candidate_only=improves_ranking and summaries[1]['beats_null_baseline'],
        production_ready=False,requires_gemini=True,actual_calls_saved=0,
        limitations=['Reused validation; not independent performance evidence.',
            'FP budget is fixed by reference at 0.5. Best TP within budget is post-hoc diagnostic only.',
            'Scores are not calibrated. Baseline checks do not authorize production or erase human restrictions.'])

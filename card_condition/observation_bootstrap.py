"""Paired physical-group resampling of fixed crossfit errors, not a final CI."""
import math
import random

TARGET='observation_limited'
REPLICATES=2000
SEED=42


def paired_group_bootstrap(baseline, candidate):
    def index(rows):
        result={}
        for row in rows:
            key=(row['card_id'],row['side'])
            value=row['probabilities'][TARGET]
            if (key in result or row['labels'][TARGET] not in (0,1)
                    or not isinstance(value,(int,float)) or not math.isfinite(value)
                    or not 0<=value<=1 or row['split']!='train'
                    or row['excluded_fit_group']!=row['group']):
                raise ValueError('Invalid train group-crossfit prediction')
            result[key]=row
        return result
    before=index(baseline);after=index(candidate)
    if not before or before.keys()!=after.keys():
        raise ValueError('Bootstrap requires identical nonempty prediction faces')
    groups={}
    for key,row in before.items():
        other=after[key]
        for field in ('group','labels','image_hashes','box','visibility_issues'):
            if row[field]!=other[field]:
                raise ValueError('Bootstrap prediction inputs or truth differ')
        # Each group carries both candidates' confusion counts in the same draw.
        counts=groups.setdefault(row['group'],[0]*6)
        truth=row['labels'][TARGET]
        counts[truth]+=1
        for offset,record in ((2,row),(4,other)):
            guess=int(record['probabilities'][TARGET]>=.5)
            counts[offset+(1 if truth else 0)]+=int(guess!=truth)
    if len(groups)<2:
        raise ValueError('Bootstrap requires at least two physical groups')
    samples=[];skipped=0;generator=random.Random(SEED);bags=[groups[group] for group in sorted(groups)]
    for _ in range(REPLICATES):
        total=[0]*6
        for bag in generator.choices(bags,k=len(bags)):
            total=[a+b for a,b in zip(total,bag)]
        negatives,positives,base_fp,base_fn,next_fp,next_fn=total
        if not negatives or not positives:
            skipped+=1
            continue
        samples.append(((next_fp-base_fp)/negatives,(next_fn-base_fn)/positives))
    def summarize(column):
        values=sorted(row[column] for row in samples)
        # Nearest-rank empirical quantiles; no normality assumption.
        return dict(empirical_p025=values[max(0,math.ceil(.025*len(values))-1)],
                    empirical_p975=values[math.ceil(.975*len(values))-1]) if values else None
    totals=[sum(bag[i] for bag in bags) for i in range(6)]
    if not totals[0] or not totals[1]:
        raise ValueError('Bootstrap requires both observation truth classes')
    return dict(groups=len(groups),faces=len(before),replicates=REPLICATES,seed=SEED,
        usable_replicates=len(samples),skipped_single_class_replicates=skipped,
        fpr_delta=dict(observed=(totals[4]-totals[2])/totals[0],spread=summarize(0)),
        fnr_delta=dict(observed=(totals[5]-totals[3])/totals[1],spread=summarize(1)),
        resampling_unit='whole physical group; paired candidates',threshold=.5,
        model_refitted=False,affects_selection=False,
        limitations=['Conditional sensitivity of fixed predictions on reused training groups, not independent final accuracy.',
            'Crossfit models share training groups; this is not a formal confidence interval for the learning algorithm.',
            'Preserving groups avoids treating front/back or repeat photos as independent samples.',
            'Lower delta means fewer errors; intervals crossing zero do not establish a stable direction.',
            'No threshold, feature, checkpoint or adoption criterion is selected from these resamples.'])

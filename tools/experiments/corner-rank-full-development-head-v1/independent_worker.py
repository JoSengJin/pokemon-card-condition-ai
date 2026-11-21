"""Run a future separately authorized independent trial via the common recorder."""
from hashlib import sha256
import json
import os
import sys
from pathlib import Path

import torch


if __name__ == '__main__':
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    plan = json.loads((out/'plan.json').read_text())
    ref = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    if (plan['hypothesis_id'] != 'corner-rank-independent-v1' or
            not all(r['id'].startswith('synthetic-') for r in ref['rows'])):
        raise ValueError('Expected the independent trial plan and its synthetic recorder reference')
    source = Path('tools/experiments/corner-rank-full-development-head-v1')
    if Path(__file__).read_bytes() != (source/Path(__file__).name).read_bytes():
        raise ValueError('Independent worker mirror differs')
    sys.path.insert(0, str(source.resolve()))
    from release import load_release
    from trial import run_sealed
    body, heads = load_release(**plan['freeze'])
    files = dict(plan['sealed_cohort'], warm=plan['warm'])
    freeze = json.loads(Path(plan['freeze']['path']).read_text())
    if files['warm'] != freeze['warm']:
        raise ValueError('Warm-up cohort differs from frozen release')
    result = run_sealed(body, heads, 'mps', files, out)
    x = torch.zeros((3,384))
    x[:,0] = torch.tensor([-1.,0.,1.])
    scores = {a:(x@head['coef']+head['bias']).sigmoid().tolist() for a,head in heads.items()}
    if scores['e'] != ref['before_scores']:
        raise ValueError('Synthetic recorder reference differs')
    sealed_outputs = {name:sha256((out/name).read_bytes()).hexdigest()
                      for name in ('predictions.json','independent-result.json')}
    (out/'diagnostics.json').write_text(json.dumps(sealed_outputs,indent=2)+'\n')
    evidence = dict(kind='sealed_independent_cohort_report', file='independent-result.json',
                    replacement_review=result['replacement_review'],
                    scores_source='synthetic recorder fixture; independent metrics are in the report file')
    (out/'observations.json').write_text(json.dumps(dict(rows=ref['rows'], scores=scores['rank'],
                                                        diagnostic_evidence=evidence),allow_nan=False)+'\n')

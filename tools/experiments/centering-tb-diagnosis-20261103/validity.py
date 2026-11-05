"""Diagnosis only: valid = outer-edge search window not clipped by the photo edge (pad == int(.06*bh)+10). Re-run slack-correction test on valid rows; write conclusion into diag.json."""
import json, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps
sys.path.insert(0, 'artifacts/centering-tb-measurer-v2-20261103'); import worker as W
D = Path('artifacts/centering-tb-diagnosis-20261103')
rows = json.loads(Path('artifacts/centering-tb-measurer-v2-20261103/rows.json').read_text())
s = json.loads((D/'slack.json').read_text()); diag = json.loads((D/'diag.json').read_text())
valid, heur = [], []
for r in rows:
    with Image.open(r['image']) as im: w, h = ImageOps.exif_transpose(im).size
    Y0, Y1 = round(r['box'][1]*h), round(r['box'][3]*h); bh = Y1-Y0
    valid.append(min(Y0, h-Y1) >= int(.06*bh))
    heur.append(not (s[len(heur)]['slack_top'] == s[len(heur)]['slack_bot'] and s[len(heur)]['tilt_top'] == 0 and s[len(heur)]['tilt_bot'] == 0))
def asym(t, b): return abs(t-b)/(t+b) if abs(t+b) > 1e-6 else 0.
def rk(v): return W.rank(np.array(v))
def stats(idx):
    sub = [s[i] for i in idx]
    raw = [abs(asym(o['v2_top'], o['v2_bot'])-asym(o['ht'], o['hb'])) for o in sub]
    cor = [abs(asym(o['v2_top']-o['slack_top'], o['v2_bot']-o['slack_bot'])-asym(o['ht'], o['hb'])) for o in sub]
    ds = [abs(o['slack_top']-o['slack_bot']) for o in sub]; sl = [abs(o['slack_top'])+abs(o['slack_bot']) for o in sub]
    return dict(n=len(sub), mean_err_raw=float(np.mean(raw)), mean_err_slack_corrected=float(np.mean(cor)),
                spearman_err_vs_total_slack=float(np.corrcoef(rk(raw), rk(sl))[0, 1]), spearman_err_vs_diff_slack=float(np.corrcoef(rk(raw), rk(ds))[0, 1]),
                median_abs_slack=float(np.median([abs(o['slack_top']) for o in sub]+[abs(o['slack_bot']) for o in sub])))
vi = [i for i, v in enumerate(valid) if v]
hi = [i for i, v in enumerate(heur) if v]
out = dict(valid_indices=vi, all36=stats(range(36)), valid=stats(vi), valid_heuristic_indices=hi, valid_heuristic=stats(hi))
better = any(out[k]['mean_err_slack_corrected'] < out[k]['mean_err_raw'] for k in ('valid', 'valid_heuristic'))
out['conclusion'] = 'hypothesis rejected on valid rows too' if not better else 'supported on valid rows -> hold judgement'
diag_out = dict(rows=diag, slack_validity=out); (D/'diag.json').write_text(json.dumps(diag_out, indent=1, default=float))
print(json.dumps(out, indent=1))

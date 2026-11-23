"""Hidden size threshold of the existing back-corner human labels, denominators, case ladder.

Run from the repo root:  .venv/bin/python tools/diagnostics/corner-size-threshold-20261123/run.py [--check]
Reads observations.json 'rows' only (id, box, target); the 'scores' keys are never accessed.
Rules and numeric criteria: docs/collaboration/reports/corner-label-standard-evidence-20261123.md (fixed before results).
Outputs (git-ignored): artifacts/corner-size-threshold-20261123/{measures.json,tables.json,tables.md,ladder.html}
"""
import base64, hashlib, io, json, math, random, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'corner-rejudge-20261121')]
import measure as M
from score import wilson  # reuse: Wilson 95% interval

OBS = Path('artifacts/experiments/20261102T140143-82781117/observations.json')
W1 = Path('artifacts/w1-blind-rejudge-20261123')
B_RESP = Path('artifacts/w1-selfagree-b-20261123/responses')
B_UNLOCK = datetime(2026, 11, 24, 3, 0, tzinfo=timezone(timedelta(hours=9)))
OUT = Path('artifacts/corner-size-threshold-20261123')
SEED, BOOT, RUNGS = 20261123, 2000, 24
FINAL = {1: '결함', 5: '결함', 11: '결함', 12: '결함', 17: '결함', 24: '결함', 38: '경계', 51: '정상', 55: '결함'}  # addendum-user-statement-20261123.txt


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def in_fit(group):
    return int(hashlib.sha256(group.encode()).hexdigest(), 16) % 5 < 3


def logistic(x, y, iters=50):
    """IRLS for logit p = a + b x. Returns (a, b)."""
    X, w = np.column_stack([np.ones(len(x)), x]), np.zeros(2)
    for _ in range(iters):
        p = 1/(1 + np.exp(-X @ w))
        W = p*(1 - p) + 1e-9
        w = w + np.linalg.solve((X*W[:, None]).T @ X + 1e-6*np.eye(2), X.T @ (y - p))
    return float(w[0]), float(w[1])


def auc(x, y):
    pos, neg = x[y == 1], x[y == 0]
    return float(((pos[:, None] > neg[None]).sum() + .5*(pos[:, None] == neg[None]).sum())/(len(pos)*len(neg)))


def rate(k, n):
    lo, hi = wilson(k, n) if n else (float('nan'),)*2
    return dict(k=int(k), n=int(n), rate=round(k/n, 3) if n else None, wilson95=[round(lo, 3), round(hi, 3)])


def measures(rows):
    """Cached pixel measures keyed by zone id + photo hash + box (label-free)."""
    path = OUT / 'measures.json'
    cache = json.loads(path.read_text()) if path.exists() else {}
    for r in rows:
        key = f"{r['id']}|{r['image_sha256']}|{','.join(f'{v:.6f}' for v in r['box'])}"
        if key not in cache:
            cache[key] = M.measure(r)
        r['m'] = cache[key]
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True))


def threshold(rows):
    ok = [r for r in rows if r['m']['status'] == 'ok']
    fit, chk = [r for r in ok if in_fit(r['group'])], [r for r in ok if not in_fit(r['group'])]
    arr = lambda rs: (np.array([r['m']['size_mm'] for r in rs]), np.array([r['target'] for r in rs], float))
    xf, yf = arr(fit)
    a, b = logistic(xf, yf)
    groups, rng, bs, ts = sorted({r['group'] for r in fit}), random.Random(SEED), [], []
    by = {g: [r for r in fit if r['group'] == g] for g in groups}
    for _ in range(BOOT):
        xs, ys = arr([r for g in rng.choices(groups, k=len(groups)) for r in by[g]])
        if 0 < ys.sum() < len(ys):
            a2, b2 = logistic(xs, ys)
            bs.append(b2)
            if b2 > 0: ts.append(-a2/b2)
    ci = lambda v: [round(float(q), 3) for q in np.percentile(v, [2.5, 97.5])] if len(v) else None
    t50 = -a/b if b > 0 else None
    xc, yc = arr(chk)
    pred = (xc >= t50) if t50 is not None else np.zeros(len(xc), bool)
    agree = rate(int((pred == (yc == 1)).sum()), len(yc))
    base = max(yc.mean(), 1 - yc.mean())
    cover = len(ok)/len(rows)
    c1 = dict(slope_ci_above_0=bool(bs and np.percentile(bs, 2.5) > 0), check_beats_majority=bool(agree['wilson95'][0] > base), coverage_ge_30pct=bool(cover >= .30))
    band = None
    if b > 0:
        band = [round((math.log(p/(1 - p)) - a)/b, 3) for p in (.25, .75)]
    return dict(n_all=len(rows), n_measured=len(ok), coverage=round(cover, 3), status_counts=count(r['m']['status'] for r in rows),
                fit=dict(n=len(fit), photos=len(groups), defect=int(yf.sum())), check=dict(n=len(chk), photos=len({r['group'] for r in chk}), defect=int(yc.sum())),
                a=round(a, 4), slope_per_mm=round(b, 4), slope_boot95=ci(bs), t50_mm=round(t50, 3) if t50 is not None else None, t50_boot95=ci(ts), t50_boot_valid=len(ts),
                check_agreement=agree, check_majority_baseline=round(float(base), 3), auc_fit=round(auc(xf, yf), 3), auc_check=round(auc(xc, yc), 3),
                band_p25_p75_mm=band, c1=c1, c1_pass=all(c1.values()))


def count(it):
    out = {}
    for v in it: out[v] = out.get(v, 0) + 1
    return dict(sorted(out.items()))


def resolution(rows):
    ppm = np.array([r['m']['ppm'] for r in rows])
    shown = np.minimum(1.0, 420/(1.5*ppm*88/3))  # review crop: 1.5x zone (zone long side = 88/3 mm), thumbnail 420 px
    q = lambda v: [round(float(x), 2) for x in np.percentile(v, [10, 50, 90])]
    return dict(n=len(rows), px_per_mm_p10_p50_p90=q(ppm), mm_per_px_p10_p50_p90=q(1/ppm)[::-1], floor_2px_mm_p50=round(float(2/np.median(ppm)), 3),
                floor_3px_mm_p50=round(float(3/np.median(ppm)), 3), floor_2px_mm_worst10pct=round(float(2/np.percentile(ppm, 10)), 3),
                review_crop_px_per_mm_p10_p50_p90=q(ppm*shown), review_crop_floor_2px_mm_p50=round(float(2/np.median(ppm*shown)), 3),
                note='px/mm is from the human-confirmed card box; a box wider than the card overstates px/mm (sizes in mm understated)')


def denominators(rows, band):
    """Zone and photo denominators per boundary treatment; boundary = measured size inside the p25-p75 band."""
    is_b = lambda r: band is not None and r['m']['status'] == 'ok' and band[0] <= r['m']['size_mm'] < band[1]
    def table(lab):
        zones = dict(normal=sum(v == 0 for v in lab.values()), defect=sum(v == 1 for v in lab.values()), dropped=sum(v is None for v in lab.values()))
        photos = {}
        for r in rows:
            photos.setdefault(r['group'], []).append(lab[r['id']])
        full = [v for v in photos.values() if None not in v]
        return dict(zones=zones, photos=dict(defect=sum(1 in v for v in full), normal=sum(1 not in v for v in full), dropped=len(photos) - len(full)))
    base = {r['id']: r['target'] for r in rows}
    out = {'as_labelled': table(base), 'boundary_zones': sum(is_b(r) for r in rows), 'boundary_by_label': count(r['target'] for r in rows if is_b(r))}
    out['1_exclude_boundary'] = table({r['id']: None if is_b(r) else r['target'] for r in rows})
    out['2_eval_boundary_as_normal'] = table({r['id']: 0 if is_b(r) else r['target'] for r in rows})
    out['3_boundary_as_defect'] = table({r['id']: 1 if is_b(r) else r['target'] for r in rows})
    ref = out['1_exclude_boundary']
    out['max_relative_change_vs_1'] = round(max(abs(out[k][lvl][c] - ref[lvl][c])/max(ref[lvl][c], 1) for k in ('2_eval_boundary_as_normal', '3_boundary_as_defect')
                                               for lvl in ('zones', 'photos') for c in ('normal', 'defect')), 3)
    return out


def w1(rows, band):
    sel = json.loads((W1 / 'selection.json').read_text())
    new = dict(ln.strip().split('=', 1) for ln in (W1 / 'responses/paste-20261123.txt').read_text().splitlines() if '=' in ln)
    by = {r['id']: r for r in rows}
    zs = []
    for z in sel:
        ans = new[f"z{z['n']}"].split('|')[0]
        zs.append(dict(n=z['n'], prev=z['target'], blind=ans, final=FINAL.get(z['n']), m=by[z['id']]['m']))
    counts = count(z['blind'] for z in zs)
    # denominators on the 60 W1 zones per treatment of 불가/미판정/경계
    den = {}
    for name, unk in (('exclude', None), ('as_normal', 0), ('as_defect', 1)):
        lab = [1 if z['blind'] == '결함' else 0 if z['blind'] == '정상' else unk for z in zs if z['blind'] != '미판정']
        den[f'불가_{name}'] = dict(normal=lab.count(0), defect=lab.count(1), dropped=lab.count(None), 미판정_not_counted=counts.get('미판정', 0))
    binz = [z for z in zs if z['blind'] in ('정상', '결함')]
    dis = [z for z in binz if (z['prev'] == 1) != (z['blind'] == '결함')]
    out = dict(blind_counts=counts, denominators=den, binary=len(binz), disagree=len(dis), measured_binary=sum(z['m']['status'] == 'ok' for z in binz),
               measured_disagree=sum(z['m']['status'] == 'ok' for z in dis), disagree_sizes_mm=sorted(z['m']['size_mm'] for z in dis if z['m']['status'] == 'ok'),
               final_statement={f"z{k}": v for k, v in FINAL.items()})
    if band is not None:
        inb = lambda z: z['m']['status'] == 'ok' and band[0] <= z['m']['size_mm'] < band[1]
        mb = [z for z in binz if z['m']['status'] == 'ok']
        out['agree_in_band'] = rate(sum(z not in dis for z in mb if inb(z)), sum(inb(z) for z in mb))
        out['agree_outside_band'] = rate(sum(z not in dis for z in mb if not inb(z)), sum(not inb(z) for z in mb))
    return out, sel


def b_selfagree(rows, band):
    """B self-agreement near the threshold. Not opened before the unlock; absent responses = not run."""
    now = datetime.now(timezone.utc)
    files = sorted(B_RESP.glob('*.txt')) if now >= B_UNLOCK and B_RESP.exists() else []
    if not files or band is None:
        return dict(status='not_run', reason='before unlock 2026-11-24 03:00 KST' if now < B_UNLOCK else 'no B response file' if not files else 'no band (C1 not passed)')
    mp = json.loads((B_RESP.parent / 'mapping.json').read_text())
    first = dict(ln.strip().split('=', 1) for ln in (W1 / 'responses/paste-20261123.txt').read_text().splitlines() if '=' in ln)
    b = dict(ln.strip().split('=', 1) for ln in files[-1].read_text().splitlines() if '=' in ln and not ln.startswith('#'))
    by = {r['id']: r for r in rows}
    res = {'in_band': [0, 0], 'outside': [0, 0]}
    for zb, info in mp.items():
        v1, v2, m = first[info['old_z']].split('|')[0], b.get(zb, '미판정').split('|')[0], by[info['id']]['m']
        if v2 not in ('정상', '결함') or m['status'] != 'ok' or int(info['old_z'][1:]) in FINAL:
            continue
        slot = res['in_band' if band[0] <= m['size_mm'] < band[1] else 'outside']
        slot[0] += v1 == v2
        slot[1] += 1
    return dict(status='run', file=files[-1].name, file_sha256=sha(files[-1]), in_band=rate(*res['in_band']), outside=rate(*res['outside']))


def ladder(rows, w1_groups, t, write):
    """24 rungs at evenly spaced ranks of measured size; W1 photos excluded (B self-agreement must stay blind)."""
    pool = sorted((r for r in rows if r['m']['status'] == 'ok' and r['group'] not in w1_groups), key=lambda r: (r['m']['size_mm'], r['id']))
    picks = [pool[round(i*(len(pool) - 1)/(RUNGS - 1))] for i in range(RUNGS)]
    arts = []
    for i, r in enumerate(picks, 1):
        im, ppm = M.oriented_crop(r)
        ax, ay = r['m']['apex']
        tip = im.crop([int(max(0, ax - 1.5*ppm)), int(max(0, ay - 1.5*ppm)), int(ax + 5*ppm), int(ay + 5*ppm)])
        tip = tip.resize((390, round(390*tip.height/tip.width)), Image.LANCZOS)
        buf = io.BytesIO()
        tip.save(buf, 'JPEG', quality=85)
        arts.append(f'<article data-i="{i}" data-s="{r["m"]["size_mm"]:.2f}"><h2>{i}번 · 흰 부분 약 {r["m"]["size_mm"]:.2f} mm · 기존 라벨: <b>{"결함" if r["target"] else "정상"}</b></h2>'
                    f'<img alt="" src="data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"><button>여기부터 결함</button></article>')
    note = (f'기존 라벨에서 역산한 50% 지점은 약 {t["t50_mm"]} mm입니다(참고용).' if t['c1_pass'] else
            '크기 측정값만으로는 기존 라벨의 문턱이 식별되지 않았습니다. 순서는 흰 픽셀 측정값 기준일 뿐입니다.')
    html = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>모서리 사례 사다리</title>'
            '<style>body{font:17px/1.5 system-ui;margin:12px;max-width:430px}img{width:100%;display:block}article{border:2px solid #ccc;border-radius:8px;padding:8px;margin:10px 0}'
            'article.cut{border-color:#c00}article.d{background:#fdeaea}h2{font-size:16px;margin:4px 0}button{width:100%;min-height:48px;font-size:17px;margin-top:6px}textarea{width:100%;height:70px;font-size:16px}</style>'
            '<h1>모서리 사례 사다리</h1><p>기존 후면 모서리 구역 24개를 <b>모서리 끝의 흰 부분 크기(픽셀 측정) 순</b>으로 늘어놓았습니다. 각 칸에는 그 구역의 <b>기존 사람 라벨</b>만 표시합니다. '
            'AI 예측·점수는 없고 미리 고른 값도 없습니다. 라벨을 다시 매기는 화면이 아닙니다.</p>'
            f'<p><b>할 일은 하나</b>: "이 정도부터 결함으로 본다"에 해당하는 칸의 버튼을 한 번 누르고, 맨 아래 결과 한 줄을 길게 눌러 복사해 채팅에 붙여넣어 주세요. 고르기 어렵다면 누르지 않아도 됩니다. {note}</p>'
            + ''.join(arts) + '<h2>결과</h2><textarea id="out" readonly>ladder-cut=미선택</textarea>'
            '<script>const a=[...document.querySelectorAll("article")];a.forEach(x=>x.querySelector("button").onclick=()=>{a.forEach(y=>{y.classList.toggle("cut",y===x);'
            'y.classList.toggle("d",+y.dataset.i>=+x.dataset.i)});document.getElementById("out").value="ladder-cut="+x.dataset.i+"|size_mm="+x.dataset.s+"|rungs="+a.length})</script></html>')
    if write: (OUT / 'ladder.html').write_text(html)
    return dict(rungs=RUNGS, pool=len(pool), sizes_mm=[r['m']['size_mm'] for r in picks], labels=[r['target'] for r in picks], ids=[r['id'] for r in picks], html_sha256=hashlib.sha256(html.encode()).hexdigest())


def markdown(t):
    th, rs, d, w = t['threshold'], t['resolution'], t['denominators'], t['w1']
    L = ['# corner-size-threshold tables (generated; do not edit)', '', '## inputs (sha256)'] + [f'- `{k}` {v}' for k, v in t['inputs'].items()]
    L += ['', '## resolution', f"- px/mm p10/p50/p90: {rs['px_per_mm_p10_p50_p90']} (n={rs['n']}); 2 px floor at median {rs['floor_2px_mm_p50']} mm, 3 px {rs['floor_3px_mm_p50']} mm, worst 10% {rs['floor_2px_mm_worst10pct']} mm",
          f"- W1 review crop px/mm p10/p50/p90: {rs['review_crop_px_per_mm_p10_p50_p90']}; 2 px floor at median {rs['review_crop_floor_2px_mm_p50']} mm"]
    L += ['', '## hidden threshold', f"- measured {th['n_measured']}/{th['n_all']} ({th['coverage']}); status {th['status_counts']}",
          f"- fit {th['fit']} / check {th['check']}", f"- slope/mm {th['slope_per_mm']} boot95 {th['slope_boot95']}; t50 {th['t50_mm']} mm boot95 {th['t50_boot95']} (valid {th['t50_boot_valid']}/{BOOT}); band p25-p75 {th['band_p25_p75_mm']}",
          f"- check agreement {th['check_agreement']} vs majority {th['check_majority_baseline']}; AUC fit {th['auc_fit']} check {th['auc_check']}", f"- C1 {th['c1']} -> pass={th['c1_pass']}"]
    L += ['', '## denominators (946 zones, existing labels)', '| treatment | zone normal | zone defect | zone dropped | photo normal | photo defect | photo dropped |', '|---|---|---|---|---|---|---|']
    for k in ('as_labelled', '1_exclude_boundary', '2_eval_boundary_as_normal', '3_boundary_as_defect'):
        z, p = d[k]['zones'], d[k]['photos']
        L.append(f"| {k} | {z['normal']} | {z['defect']} | {z['dropped']} | {p['normal']} | {p['defect']} | {p['dropped']} |")
    L += [f"- boundary zones {d['boundary_zones']} by label {d['boundary_by_label']}; max relative change vs treatment 1: {d['max_relative_change_vs_1']}"]
    L += ['', '## W1 (60 zones)', f"- blind counts {w['blind_counts']}; denominators {w['denominators']}", f"- binary {w['binary']} (measured {w['measured_binary']}), disagree {w['disagree']} (measured {w['measured_disagree']}), sizes {w['disagree_sizes_mm']}",
          f"- agreement in band {w.get('agree_in_band')} / outside {w.get('agree_outside_band')}", '', '## B self-agreement', f"- {t['b']}", '', '## ladder', f"- {t['ladder']}"]
    return '\n'.join(L) + '\n'


def check():
    print(M.selfcheck())
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 3, 4000)
    y = (rng.uniform(size=4000) < 1/(1 + np.exp(-(4*x - 4)))).astype(float)
    a, b = logistic(x, y)
    assert abs(-a/b - 1.0) < .08 and abs(b - 4) < .5, (a, b)
    assert abs(auc(np.array([0., 1, 2, 3]), np.array([0., 0, 1, 1])) - 1) < 1e-9
    assert in_fit('g1') == in_fit('g1')
    print('logistic/auc selfcheck ok')
    stored = OUT / 'tables.json'
    if stored.exists():
        old = json.loads(stored.read_text())
        new = main(write=False)
        for k in ('inputs', 'resolution', 'threshold', 'denominators', 'w1', 'ladder'):
            assert old[k] == new[k], f'{k} differs from stored tables.json'
        print('regenerated tables match stored tables.json (inputs, resolution, threshold, denominators, w1, ladder)')
    else:
        print('tables.json not present: regeneration comparison skipped')


def main(write=True):
    OUT.mkdir(exist_ok=True)
    rows = json.loads(OBS.read_text())['rows']  # rows only
    rows = [{k: r[k] for k in ('id', 'group', 'area', 'image', 'image_sha256', 'box', 'target')} for r in rows]
    measures(rows)
    th = threshold(rows)
    band = th['band_p25_p75_mm'] if th['c1_pass'] else None
    w, sel = w1(rows, band)
    t = dict(inputs={str(p): sha(p) for p in (OBS, W1 / 'selection.json', W1 / 'responses/paste-20261123.txt', W1 / 'responses/addendum-user-statement-20261123.txt', HERE / 'measure.py', HERE / 'run.py')},
             resolution=resolution(rows), threshold=th, denominators=denominators(rows, band), w1=w, b=b_selfagree(rows, band),
             ladder=ladder(rows, {z['group'] for z in sel}, th, write))
    if write:
        (OUT / 'tables.json').write_text(json.dumps(t, ensure_ascii=False, indent=1))
        (OUT / 'tables.md').write_text(markdown(t))
        print(markdown(t))
    return t


if __name__ == '__main__':
    check() if '--check' in sys.argv else main()

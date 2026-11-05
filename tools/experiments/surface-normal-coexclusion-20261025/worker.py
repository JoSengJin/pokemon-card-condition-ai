"""One common-runner diagnostic; no import-time data access, fit or model adoption.

Runs only through ./experiment from the default checkout, from the byte-identical mirror
artifacts/surface-normal-coexclusion-20261025/worker.py (the runner captures code under artifacts/ only).
The primary 147 rows and 11 required cohorts replay the 122011 baseline; diagnostic heads are never submitted.
"""
import collections
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'card_condition').is_dir())
sys.path.insert(0, str(ROOT))
TARGETS = ('a', 'b', 'c', 'ㄴ')
BASE = 'artifacts/experiments/20261025T122011-647b0e9c'
TYPED = 'artifacts/experiments/20261024T063834-3536c642/typed-training-tokens.pt'
LEGACY = 'artifacts/experiments/20261024T060419-45e72d0a/training-tokens.pt'
CURRENT = 'artifacts/experiments/20261024T093945-04a7e5e8/local-heads.pt'


def pair_plan(rows, all_rows, identity):
    """Four controls precede twelve directional pairs; all excluded photos stay out."""
    assert len({r['id'] for r in all_rows}) == len(all_rows)
    assert all(tuple(a[k] for k in ('id', 'group', 'target', 'box')) ==
               tuple(b[k] for k in ('id', 'group', 'target', 'box')) for a, b in zip(rows, all_rows))
    assert len(all_rows) >= len(rows)
    positives = [r['id'] for r in all_rows if r['side'] == 'front' and r['target'] == 1]
    splits = []
    for pairs in (False, True):
        for g in TARGETS:
            held = [i for i, r in enumerate(rows) if r['side'] == 'front' and r['group'] == g]
            assert len(held) == 9 and all(rows[i]['target'] == 0 for i in held)
            for h in (tuple(v for v in TARGETS if v != g) if pairs else (None,)):
                excluded = {g, h} - {None}
                train = [i for i, r in enumerate(all_rows) if r['side'] == 'front' and r['group'] not in excluded]
                removed = [i for i, r in enumerate(all_rows) if r['group'] in excluded]
                assert [all_rows[i]['id'] for i in train if all_rows[i]['target'] == 1] == positives
                assert not ({v for i in train for v in identity[all_rows[i]['image']]}
                            & {v for i in removed for v in identity[all_rows[i]['image']]})
                assert set(range(len(rows), len(all_rows))).issubset(train)
                splits.append(dict(g=g, h=h, train=train, held=held))
    return splits


def fit_excluding(x, masks, tokens, rows, split, fit):
    """Only the injected fit is callable here; the module guard supplies the real fitter."""
    import torch
    train = split['train']
    assert not {rows[i]['group'] for i in train} & {split['g'], split['h']}
    counts = collections.Counter(rows[i]['group'] for i in train)
    y = torch.tensor([rows[i]['target'] for i in train])
    w = torch.tensor([1 / counts[rows[i]['group']] for i in train])
    assert set(y.tolist()) == {0, 1}
    w[y == 1] *= w[y == 0].sum() / w[y == 1].sum()
    coef, bias, diag = fit(x[train], masks[train], y, tokens[train], w,
                           penalty=1., normal_reduction='max_bound')
    assert diag['converged'] is True and math.isfinite(diag['max_gradient']) and diag['max_gradient'] <= 1e-5
    assert torch.isfinite(coef).all() and torch.isfinite(bias).all()
    return coef, bias, diag


def target_scores(x, masks, held, coef, bias):
    """Read only g's valid patches; keep pre-sigmoid logits without clipping."""
    import torch
    values = x[held] @ coef + bias
    assert torch.isfinite(values).all() and masks[held].any(1).all()
    peaks = values.masked_fill(~masks[held], -torch.inf).max(1).values
    probabilities = peaks.sigmoid().tolist()
    return dict(probabilities=probabilities, max_logits=peaks.tolist(), fp=sum(v >= .5 for v in probabilities),
                denominator=len(held), mean_max_logit=float(peaks.mean()))


def judge(measurements, baseline):
    """Frozen technical pattern rules, not hypothesis proofs or adoption criteria."""
    table = {(m['g'], m['h']): m for m in measurements}
    expected = {(g, h) for g in TARGETS for h in (None, *[v for v in TARGETS if v != g])}
    assert len(measurements) == len(table) == 16 and set(table) == expected
    assert all(type(baseline[g]['fp']) is int and math.isfinite(baseline[g]['mean_max_logit']) for g in TARGETS)
    delta, log_delta = {}, {}
    for key, item in table.items():
        assert type(item['fp']) is int and 0 <= item['fp'] <= 9 and item['denominator'] == 9
        assert math.isfinite(item['mean_max_logit'])
        delta[key] = item['fp'] - baseline[key[0]]['fp']
        log_delta[key] = item['mean_max_logit'] - baseline[key[0]]['mean_max_logit']
    assert all(delta[g, None] == 0 for g in TARGETS), 'single-exclusion controls must reproduce FP_L'
    subjects = {}
    for g in TARGETS[1:]:
        same = [h for h in TARGETS[1:] if h != g]
        ds, dc = sum(delta[g, h] for h in same) / 2, delta[g, 'a']
        ls, lc = sum(log_delta[g, h] for h in same) / 2, log_delta[g, 'a']
        raw = {'delta_same>=2': ds >= 2, '|delta_cross|<=1': abs(dc) <= 1, 'delta_same-delta_cross>=2': ds - dc >= 2,
               'dL_same>=0.3': ls >= .3, 'dL_same-dL_cross>=0.3': ls - lc >= .3, 'delta_cross>=2': dc >= 2,
               **{f'|delta({h})-delta_cross|<=1': abs(delta[g, h] - dc) <= 1 for h in same}}
        h1 = [k for k in raw if k.startswith('|delta(')] + ['delta_cross>=2']
        h2 = ['delta_same>=2', '|delta_cross|<=1', 'delta_same-delta_cross>=2', 'dL_same>=0.3', 'dL_same-dL_cross>=0.3']
        subjects[g] = dict(delta_same=ds, delta_cross=dc, dL_same=ls, dL_cross=lc, raw=raw,
                           H1=all(raw[k] for k in h1), H2=all(raw[k] for k in h2))
    fp = {key: item['fp'] for key, item in table.items()}
    raw = {'H2:a_all_|delta|<=1': all(abs(delta['a', h]) <= 1 for h in TARGETS[1:]),
           'H3:FP(c,ㄴ)-FP(c,b)>=3': fp['c', 'ㄴ'] - fp['c', 'b'] >= 3,
           'H3:FP(ㄴ,c)-FP(ㄴ,b)>=3': fp['ㄴ', 'c'] - fp['ㄴ', 'b'] >= 3,
           'H3:delta(c,ㄴ)>=2': delta['c', 'ㄴ'] >= 2, 'H3:delta(ㄴ,c)>=2': delta['ㄴ', 'c'] >= 2,
           'H3:|delta(c,b)|<=1': abs(delta['c', 'b']) <= 1, 'H3:|delta(ㄴ,b)|<=1': abs(delta['ㄴ', 'b']) <= 1}
    conditions = dict(H1=sum(v['H1'] for v in subjects.values()) >= 2,
                      H2=sum(v['H2'] for v in subjects.values()) >= 2 and raw['H2:a_all_|delta|<=1'],
                      H3=all(v for k, v in raw.items() if k.startswith('H3:')))
    matched = [k for k, v in conditions.items() if v]
    return dict(decision=matched[0] if len(matched) == 1 else 'unidentified', matches=matched,
                conditions=conditions, raw=raw, subjects=subjects,
                deltas=[[g, h, delta[g, h], log_delta[g, h]] for g, h in sorted(expected, key=str) if h],
                independent=False, production_adopted=False)


def replay_baseline(root, plan, reference):
    """Verify frozen sources and reuse saved maps/cohorts; do not apply any saved head."""
    import torch
    from PIL import Image
    from card_condition.ebay_dataset import decoded_hash
    tracked = {str(root / name): expected for name, expected in plan['input_sha256'].items()}
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in tracked.items())
    fixed, legacy, current, joint = (torch.load(root / p, map_location='cpu', weights_only=True)
                                     for p in (TYPED, LEGACY, CURRENT, BASE + '/fold-heads.pt'))
    previous = json.loads((root / BASE / 'result.json').read_text())
    observation = json.loads((root / BASE / 'observations.json').read_text())
    prior_ref = json.loads((root / BASE / 'reference.json').read_text())
    assert plan['required_cohorts'] == json.loads((root / BASE / 'plan.json').read_text())['required_cohorts']
    rows, all_rows = reference['rows'], fixed['rows']
    assert len(rows) == 147 and len(all_rows) == 153 and legacy['rows'][:147] == rows
    assert rows == previous['rows'] == observation['rows'] and len(reference['before_scores']) == 147
    assert all(all(a[k] == b[k] for k in ('id', 'group', 'target', 'box', 'image_sha256'))
               for a, b in zip(rows, all_rows))
    assert len({r['id'] for r in all_rows}) == 153
    x, masks, tokens = fixed['features'], fixed['masks'], fixed['point_tokens']
    assert torch.equal(x, legacy['features']) and torch.equal(masks, legacy['masks'])
    assert torch.isfinite(x).all() and masks.dtype == torch.bool and masks.any(1).all()
    front = [i for i, r in enumerate(all_rows) if r['side'] == 'front']
    assert len(front) == 97 and torch.equal(tokens[front], legacy['point_tokens'][front])
    extra = all_rows[147:]
    assert extra == legacy['rows'][147:] and torch.equal(tokens[147:], legacy['point_tokens'][147:])
    assert [r['id'] for r in extra] == plan['training_only_ids']
    assert all(r['group'] == 'ebay-pair-ff69b8955593fc' and r['side'] == 'front' and r['split'] == 'train' for r in extra)
    assert sum(r['target'] == 1 for r in extra) == 2 and len({r['image'] for r in extra}) == 2
    source_hashes = json.loads((root / BASE / 'diagnostics.json').read_text())['source_sha256']
    identity = {}
    for r in all_rows:
        if r['image'] not in identity:
            raw = Path(r['image']).read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            assert digest == source_hashes[str(Path(r['image']))]
            decoded, _ = decoded_hash(raw)
            identity[r['image']] = {digest, decoded}
            tracked[r['image']] = digest
        assert r['image_sha256'] in identity[r['image']]
        if 'decoded_sha256' in r:
            assert r['decoded_sha256'] in identity[r['image']]
    for g, size in zip(TARGETS, ((958, 1330), (388, 500), (428, 585), (675, 930))):
        row = next(r for r in rows if r['side'] == 'front' and r['group'] == g)
        assert Path(row['image']).name.startswith('Screenshot' if g == 'a' else 'img')
        with Image.open(row['image']) as picture:
            assert picture.size == size
    assert current['maps'].shape == joint['maps'].shape == masks[:147].shape
    assert torch.isfinite(current['maps']).all() and len(prior_ref['before_scores']) == 147
    assert torch.isfinite(joint['maps']).all() and ((joint['maps'] >= 0) & (joint['maps'] <= 1)).all()
    replay = [float(joint['maps'][i][masks[i]].max()) for i in range(147)]
    old = [float(current['maps'][i][masks[i]].max()) for i in range(147)]
    assert max(abs(a - b) for a, b in zip(old, prior_ref['before_scores'])) <= 2e-5
    for saved in (previous['scores'], observation['scores'], reference['before_scores']):
        assert len(saved) == 147 and all(math.isfinite(v) for v in saved)
        assert max(abs(a - b) for a, b in zip(replay, saved)) <= 2e-5
        assert all((a >= .5) == (b >= .5) for a, b in zip(replay, saved))
    assert len(reference['required_cohorts']) == len(observation['required_cohorts']) == 11
    for ref, cohort in zip(reference['required_cohorts'], observation['required_cohorts']):
        assert all(cohort[k] == ref[k] for k in ('id', 'rows', 'point_ids'))
        assert cohort['scores'] == ref['before_scores'] and cohort['point_scores'] == ref['point_scores']
    baseline = {}
    for g, expected_fp in zip(TARGETS, (2, 1, 1, 4)):
        held = [i for i, r in enumerate(rows) if r['side'] == 'front' and r['group'] == g]
        values = [old[i] for i in held]
        assert len(values) == 9 and all(0 < v < 1 for v in values)
        baseline[g] = dict(probabilities=values, denominator=9, fp=sum(v >= .5 for v in values),
                           mean_max_logit=sum(math.log(v / (1 - v)) for v in values) / 9)
        assert baseline[g]['fp'] == expected_fp and math.isfinite(baseline[g]['mean_max_logit'])
    return dict(root=root, rows=rows, all_rows=all_rows, x=x, masks=masks, tokens=tokens, identity=identity,
                baseline=baseline, observation=copy.deepcopy(observation), tracked=tracked, replay=replay,
                replay_error=max(abs(a - b) for a, b in zip(replay, previous['scores'])))


def render(ctx, measurements, verdict):
    """Four original photos, each with nine confirmed normal regions and per-pair scores."""
    from PIL import Image, ImageDraw, ImageOps
    out = ctx['out']
    (out / 'images').mkdir()
    panels = []
    for gi, g in enumerate(TARGETS):
        held = [i for i, r in enumerate(ctx['rows']) if r['side'] == 'front' and r['group'] == g]
        cases = [('stored single', ctx['baseline'][g])] + [
            (m['h'], m) for m in measurements if m['g'] == g and m['h'] is not None]
        for ci, (h, values) in enumerate(cases):
            with Image.open(ctx['rows'][held[0]]['image']) as source:
                im = ImageOps.exif_transpose(source).convert('RGB')
            draw = ImageDraw.Draw(im)
            for i, score in zip(held, values['probabilities']):
                box = ctx['rows'][i]['box']
                xy = (box[0] * im.width, box[1] * im.height, box[2] * im.width, box[3] * im.height)
                draw.rectangle(xy, outline='red' if score >= .5 else 'green', width=3)
                draw.text((xy[0] + 2, xy[1] + 2), f'GT=0 p={score:.3f}', fill='black', stroke_width=1, stroke_fill='white')
            im.thumbnail((900, 1000))
            name = f'{gi}-{ci}.png'
            im.save(out / 'images' / name)
            delta = values['fp'] - ctx['baseline'][g]['fp']
            panels.append(f'<article><h3>g={html.escape(g)} / h={html.escape(h)}</h3><img src="images/{name}" '
                          f'alt="9 confirmed normal regions"><p>FP {values["fp"]}/9; 단독 제외 대비 Δ {delta:+d} '
                          f'({100 * delta / 9:+.2f}%p); mean max logit {values["mean_max_logit"]:.4f}</p></article>')
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Normal co-exclusion diagnostic</title><style>body{font:15px/1.6 system-ui;margin:20px;color:#172537;background:#f4f6f9}'
            '.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}article{background:white;padding:12px}'
            'img{max-width:100%}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>정상 카드 공동 제외 진단</h1>'
            f'<p>worker SHA256 {html.escape(ctx["source_sha"])} · 진척30/100 (usable-card-analysis-v1.0, ±0%p). '
            '반복 개발자료 진단, 독립시험·운영채택 아님. 사람 정답은 표시한9구역 정상. 빨강=FP, 초록=정상 반응.</p>'
            '<p>주 평가·required cohort는 기존 기준선 재생이며 아래 진단 head의 품질 통과가 아니다. '
            '4실물·출처/크기 교란·6개 고유 쌍 학습집합의 한계. 미구별은 반증·효과 없음이 아니다. '
            '<a href="diagnostics.json">원시16회·검사·판정</a></p><pre>'
            + html.escape(json.dumps(verdict, ensure_ascii=False, indent=2)) + '</pre><div class="grid">'
            + ''.join(panels) + '</div></html>')
    (out / 'index.html').write_text(page)


def finish(ctx, measurements, heads):
    """Keep diagnostic heads separate and submit the replayed common baseline/cohorts."""
    import torch
    verdict = judge(measurements, ctx['baseline'])
    evidence = dict(kind='normal_coexclusion', decision=verdict['decision'], matches=verdict['matches'],
                    conditions=verdict['conditions'], raw=verdict['raw'],
                    subjects={g: dict(H1=v['H1'], H2=v['H2'], raw=v['raw']) for g, v in verdict['subjects'].items()},
                    controls=[m['replay_error'] for m in measurements if m['h'] is None],
                    pairs=[[m['g'], m['h'], m['fp'], m['mean_max_logit']] for m in measurements if m['h'] is not None],
                    independent=False, production_adopted=False)
    assert len(json.dumps(evidence, ensure_ascii=False, allow_nan=False).encode('utf-8')) <= 4000
    render(ctx, measurements, verdict)
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest() == h for p, h in ctx['tracked'].items())
    diagnostics = dict(baseline=ctx['baseline'], measurements=measurements, verdict=verdict,
                       baseline_replay_error=ctx['replay_error'], source_sha256=ctx['tracked'],
                       independent=False, production_adopted=False, backbone_forwards=0, new_labels=0,
                       gemini_calls=0, codex_model_calls=0)
    (ctx['out'] / 'diagnostics.json').write_text(json.dumps(diagnostics, ensure_ascii=False, indent=2, allow_nan=False))
    torch.save(dict(heads=heads, diagnostic_only=True, production_adopted=False), ctx['out'] / 'diagnostic-heads.pt')
    observation = copy.deepcopy(ctx['observation'])
    observation.update(scores=ctx['replay'], diagnostic_evidence=evidence)
    (ctx['out'] / 'observations.json').write_text(json.dumps(observation, ensure_ascii=False, allow_nan=False))
    print(json.dumps(evidence, ensure_ascii=False, allow_nan=False), flush=True)


if __name__ == '__main__':
    import torch
    from card_condition.detail_bag import fit_detail_head
    assert Path(__file__).resolve().is_relative_to(ROOT / 'artifacts'), 'Use the byte-identical artifacts mirror'
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR']).resolve()
    assert out.is_relative_to(ROOT / 'artifacts/experiments')
    plan = json.loads((out / 'plan.json').read_text())
    reference = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    assert plan['experiment_kind'] == 'diagnostic' and plan['gemini_calls_allowed'] == 0
    assert plan['independent'] is False and plan['production_adopted'] is False
    assert plan['reference_result'] == BASE + '/result.json'
    assert plan['acceptance'] == dict(max_fn=16, max_fp=18, no_new_errors=True, require_actual_point_guard=False)
    assert hashlib.sha256(Path(__file__).read_bytes()).digest() == hashlib.sha256((ROOT / plan['tracked_source']).read_bytes()).digest()
    torch.set_num_threads(2)
    context = replay_baseline(ROOT, plan, reference)
    context.update(out=out, source_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    measurements, heads = [], []
    # Controls come first; any failed reproduction raises before a co-exclusion fit starts.
    # fit_excluding is called here, not from a worker function, so the fit path stays at four transitions.
    for split in pair_plan(context['rows'], context['all_rows'], context['identity']):
        trained = [context['all_rows'][i] for i in split['train']]
        clicks = sum(r['target'] == 1 and int(context['tokens'][i]) >= 0 for i, r in zip(split['train'], trained))
        assert (len(trained), sum(r['target'] for r in trained), clicks) == (88 if split['h'] is None else 79, 53, 20)
        coef, bias, diagnostic = fit_excluding(context['x'], context['masks'], context['tokens'],
                                               context['all_rows'], split, fit_detail_head)
        metrics = target_scores(context['x'], context['masks'], split['held'], coef, bias)
        if split['h'] is None:
            old = context['baseline'][split['g']]['probabilities']
            metrics['replay_error'] = max(abs(a - b) for a, b in zip(old, metrics['probabilities']))
            assert metrics['replay_error'] <= 1e-4
            assert all((a >= .5) == (b >= .5) for a, b in zip(old, metrics['probabilities']))
        measurements.append(dict(g=split['g'], h=split['h'], train_rows=len(split['train']),
                                 train_ids=[r['id'] for r in trained],
                                 held_ids=[context['rows'][i]['id'] for i in split['held']], fit=diagnostic, **metrics))
        heads.append(dict(g=split['g'], h=split['h'], coef=coef, bias=bias))
    finish(context, measurements, heads)

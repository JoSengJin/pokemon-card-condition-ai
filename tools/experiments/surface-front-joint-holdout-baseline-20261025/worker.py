"""Front surface joint-group holdout baseline: same candidate settings, held groups never trained on.

Runs only through ./experiment from the default checkout. Copy this file byte-identically to
artifacts/surface-front-joint-holdout-baseline-20261025/worker.py first (the runner captures code
under artifacts/ only). Back rows keep the current candidate heads. No new labels, thresholds,
backbone forwards or external calls; the result is a development baseline, never an adoption.
"""
import collections
import hashlib
import html
import json
import os
from pathlib import Path
import sys

import torch
from PIL import ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
TYPED = 'artifacts/experiments/20261024T063834-3536c642/typed-training-tokens.pt'
LEGACY = 'artifacts/experiments/20261024T060419-45e72d0a/training-tokens.pt'
CURRENT = 'artifacts/experiments/20261024T093945-04a7e5e8/local-heads.pt'
PROPOSAL = 'artifacts/experiments/20261024T103800-512a2260/joint-fold-proposal.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_folds(proposal, all_rows, rows, identity):
    """Recompute every fold from the frozen proposal; reject leakage, gaps or duplicate held rows."""
    front = [i for i, r in enumerate(rows) if r['side'] == 'front']
    folds, held_all = [], []
    for fold in proposal['folds']:
        held_groups = set(fold['held_groups'])
        train = [i for i, r in enumerate(all_rows) if r['side'] == 'front' and r['group'] not in held_groups]
        held = [i for i in front if rows[i]['group'] in held_groups]
        assert [all_rows[i]['id'] for i in train] == fold['train_ids'] and [rows[i]['id'] for i in held] == fold['held_ids']
        assert not {all_rows[i]['group'] for i in train} & {rows[i]['group'] for i in held}
        assert not ({v for i in train for v in identity[all_rows[i]['image']]}
                    & {v for i in held for v in identity[rows[i]['image']]})
        assert {all_rows[i]['target'] for i in train} == {0, 1}
        folds.append((fold['id'], train, held))
        held_all.extend(held)
    assert sorted(held_all) == front and len(held_all) == len(set(held_all))
    return folds


def joint_holdout_maps(x, mask, tokens, all_rows, rows, folds, base_maps, fit):
    """Front rows from their single held fold; back rows unchanged from the current candidate."""
    maps, fits, heads = [None] * len(rows), [], []
    for fold_id, train, held in folds:
        # Same weighting and objective as the current candidate: group- and class-balanced, L2=1, max_bound.
        counts = collections.Counter(all_rows[i]['group'] for i in train)
        y = torch.tensor([all_rows[i]['target'] for i in train])
        w = torch.tensor([1 / counts[all_rows[i]['group']] for i in train])
        w[y == 1] *= w[y == 0].sum() / w[y == 1].sum()
        coef, bias, diag = fit(x[train], mask[train], y, tokens[train], w, penalty=1., normal_reduction='max_bound')
        assert diag['converged']
        fits.append(dict(fold=fold_id, train_rows=len(train), held_rows=len(held), **diag))
        heads.append(dict(fold=fold_id, coef=coef, bias=bias, train_ids=[all_rows[i]['id'] for i in train]))
        for i in held:
            maps[i] = (x[i] @ coef + bias).sigmoid()
    for i, r in enumerate(rows):
        if r['side'] == 'back':
            maps[i] = base_maps[i]
    assert all(m is not None for m in maps)
    return torch.stack(maps), fits, heads


def front_metrics(rows, scores, before):
    front = [i for i, r in enumerate(rows) if r['side'] == 'front']
    positives = [i for i in front if rows[i]['target'] == 1]
    negatives = [i for i in front if rows[i]['target'] == 0]
    counted = {}
    for name, values in (('before_single_group_heads', before), ('joint_holdout', scores)):
        counted[name] = dict(fn=sum(values[i] < .5 for i in positives), fp=sum(values[i] >= .5 for i in negatives),
                             positives=len(positives), negatives=len(negatives),
                             positive_groups=len({rows[i]['group'] for i in positives}),
                             negative_groups=len({rows[i]['group'] for i in negatives}))
    return dict(**counted,
                new_fn=[rows[i]['id'] for i in positives if before[i] >= .5 > scores[i]],
                new_fp=[rows[i]['id'] for i in negatives if before[i] < .5 <= scores[i]],
                recovered=[rows[i]['id'] for i in front if (before[i] >= .5) != bool(rows[i]['target'])
                           and (scores[i] >= .5) == bool(rows[i]['target'])])


def render(out, rows, all_rows, maps, mask, tokens, scores, before, metrics):
    from card_condition.side_experiment import side_image
    from card_condition.local_wear_cnn import point_input_pixel
    images = out / 'images'
    images.mkdir()
    panels = []
    for i, r in enumerate(rows):
        if r['side'] != 'front':
            continue
        im = side_image(r['image'], r['box'], True, 224)
        draw = ImageDraw.Draw(im)
        v = maps[i].clone()
        v[~mask[i]] = -1
        top = int(v.argmax())
        draw.rectangle((top % 16 * 14, top // 16 * 14, top % 16 * 14 + 13, top // 16 * 14 + 13), outline='blue', width=2)
        if tokens[i] >= 0:
            px, py = point_input_pixel(r['image'], r['box'], all_rows[i]['point'])
            draw.ellipse((px - 4, py - 4, px + 4, py + 4), outline='red', width=2)
        im.save(images / f'{i}.png')
        wrong = (scores[i] >= .5) != bool(r['target'])
        state = ('누락' if r['target'] else '오탐') if wrong else '정답'
        panels.append(f'<article><h3>{html.escape(r["id"])}</h3><img loading="lazy" src="images/{i}.png">'
                      f'<p>사람: {"표면 손상" if r["target"] else "표면 정상"} / joint holdout: {state}<br>'
                      f'단독제외 {before[i]:.4f} → joint {scores[i]:.4f}</p></article>')
    b, j = metrics['before_single_group_heads'], metrics['joint_holdout']
    page = ('<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Front Joint Holdout</title><style>body{font:15px/1.6 system-ui;margin:16px;background:#f3f5f8;color:#172537}'
            'section,article{background:#fff;padding:12px;margin:8px;border-radius:8px}.grid{display:grid;'
            'grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}img{max-width:100%}h3{font-size:13px;overflow-wrap:anywhere}</style>'
            '<h1>앞면 표면 joint holdout 기준선</h1><section><p>반복 개발 자료의 실물 4-fold 공동 제외 평가. 독립 시험이 아니며 모델 채택 없음. '
            '빨강=사람 클릭, 파랑=모델 최대 반응(위치 정답 아님). 뒷면은 현재 후보 그대로.</p>'
            f'<p>앞면 FN {b["fn"]}/{b["positives"]} → {j["fn"]}/{j["positives"]}, FP {b["fp"]}/{b["negatives"]} → {j["fp"]}/{j["negatives"]} '
            f'(손상 {j["positive_groups"]}실물, 정상 {j["negative_groups"]}실물)</p><pre>'
            + html.escape(json.dumps(metrics, ensure_ascii=False, indent=2)) + '</pre><p><a href="result.json">공통 판정</a></p></section>'
            '<div class="grid">' + ''.join(panels) + '</div></html>')
    (out / 'index.html').write_text(page)
    return len(panels)


def prepare():
    """Load and verify frozen inputs; replay the current candidate exactly before any fit."""
    from card_condition.ebay_dataset import decoded_hash
    out = Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
    reference = json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
    contract = json.loads((out / 'plan.json').read_text())['protocol_contract']
    tracked = {str(ROOT / p): sha(ROOT / p) for p in (TYPED, LEGACY, CURRENT, PROPOSAL,
                                                      'card_condition/detail_bag.py', 'card_condition/point_patch_head.py')}
    assert tracked[str(ROOT / PROPOSAL)] == contract['proposal_sha256']
    fixed, legacy, current = (torch.load(ROOT / p, map_location='cpu', weights_only=True) for p in (TYPED, LEGACY, CURRENT))
    proposal = json.loads((ROOT / PROPOSAL).read_text())
    rows, all_rows = reference['rows'], fixed['rows']
    assert legacy['rows'][:147] == rows and len(all_rows) == 153 and proposal['threshold'] == .5
    x, mask, tokens = fixed['features'], fixed['masks'], fixed['point_tokens']
    assert torch.equal(x, legacy['features']) and torch.equal(mask, legacy['masks'])
    assert all(tokens[i] == legacy['point_tokens'][i] for i, r in enumerate(all_rows) if r['side'] == 'front')
    identity = {}
    for r in all_rows:
        if r['image'] not in identity:
            p = Path(r['image'])
            tracked[str(p)] = sha(p)
            identity[r['image']] = {tracked[str(p)], decoded_hash(p.read_bytes())[0]}
        assert r['image_sha256'] in identity[r['image']]
    by = {(h['group'], h['side']): h for h in current['heads']}
    base = torch.stack([(x[i] @ by[r['group'], r['side']]['coef'] + by[r['group'], r['side']]['bias']).sigmoid()
                        for i, r in enumerate(rows)])
    assert torch.allclose(base, current['maps'], atol=2e-5, rtol=0)
    before = [float(base[i][mask[i]].max()) for i in range(len(rows))]
    assert max(abs(a - b) for a, b in zip(before, reference['before_scores'])) < 2e-5
    return dict(out=out, reference=reference, contract=contract, tracked=tracked, fixed=fixed, legacy=legacy,
                rows=rows, all_rows=all_rows, x=x, mask=mask, tokens=tokens, base=base, before=before,
                folds=check_folds(proposal, all_rows, rows, identity))


def finish(ctx, maps, fits, heads):
    """Score, guard sources, and write observations, diagnostics, heads and the photo page."""
    out, reference, rows, mask, base, before = (ctx[k] for k in ('out', 'reference', 'rows', 'mask', 'base', 'before'))
    fixed, legacy, tracked = ctx['fixed'], ctx['legacy'], ctx['tracked']
    scores = [float(maps[i][mask[i]].max()) for i in range(len(rows))]
    assert all(scores[i] == before[i] or abs(scores[i] - before[i]) < 2e-5 for i, r in enumerate(rows) if r['side'] == 'back')
    point_ref, typed_ref = fixed['point_reference'], fixed['typed_point_reference']
    legacy_scores = [float(maps[r['parent_index'], int(legacy['point_tokens'][r['parent_index']])]) for r in point_ref['rows']]
    typed_scores = [float(maps[r['parent_index'], r['human_token']]) for r in typed_ref['rows']]
    required = []
    for cohort in reference['required_cohorts']:
        assert cohort['rows'] in (rows, point_ref['rows'], typed_ref['rows'])
        s = (typed_scores if cohort['rows'] == typed_ref['rows'] else
             legacy_scores if cohort['rows'] == point_ref['rows'] else scores)
        required.append(dict(id=cohort['id'], rows=cohort['rows'], scores=s, point_ids=cohort['point_ids'],
                             point_scores=s if cohort['point_ids'] else []))
    assert all(sha(p) == v for p, v in tracked.items())
    metrics = front_metrics(rows, scores, before)
    metrics['typed_front_point_fn'] = dict(
        before=sum(float(base[r['parent_index'], r['human_token']]) < .5 for r in typed_ref['rows'] if rows[r['parent_index']]['side'] == 'front'),
        joint=sum(v < .5 for r, v in zip(typed_ref['rows'], typed_scores) if rows[r['parent_index']]['side'] == 'front'),
        points=sum(rows[r['parent_index']]['side'] == 'front' for r in typed_ref['rows']))
    (out / 'observations.json').write_text(json.dumps(dict(rows=rows, scores=scores, required_cohorts=required)))
    torch.save(dict(heads=heads, maps=maps, proposal_sha256=ctx['contract']['proposal_sha256']), out / 'fold-heads.pt')
    panels = render(out, rows, ctx['all_rows'], maps, mask, ctx['tokens'], scores, before, metrics)
    (out / 'diagnostics.json').write_text(json.dumps(dict(
        metrics=metrics, fits=fits, panels=panels, source_sha256=tracked, new_backbone_forwards=0, new_labels=0,
        gemini_calls=0, codex_model_calls=0, production_adopted=False, independent=False), ensure_ascii=False, indent=2))
    print(json.dumps(metrics, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    from card_condition.detail_bag import fit_detail_head
    torch.set_num_threads(2)
    context = prepare()
    # Called here, not from a function, so the fit path stays within four call transitions.
    finish(context, *joint_holdout_maps(context['x'], context['mask'], context['tokens'], context['all_rows'],
                                        context['rows'], context['folds'], context['base'], fit_detail_head))

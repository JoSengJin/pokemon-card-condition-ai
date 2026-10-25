"""Synthetic tensors/photos and mocked fit only; never read the project's real caches."""
import ast
import contextlib
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import math
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from PIL import Image
import torch

from card_condition import experiment_record

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / 'tools/experiments/surface-normal-coexclusion-20261025/worker.py'
spec = importlib.util.spec_from_file_location('normal_coexclusion_worker', SOURCE)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def fixture(root):
    """Match the frozen shapes/denominators with generated, uniquely coloured pictures."""
    rows, tokens, images = [], [], {}
    groups = [('a', 9, 0, -1), ('b', 9, 0, -1), ('c', 9, 0, -1), ('ㄴ', 9, 0, -1),
              ('u', 8, 1, -1), ('v', 7, 1, -1), ('x', 9, 1, -1), ('z', 9, 1, -1),
              ('v', 1, 0, -1), ('k', 1, 0, -1), ('n', 1, 0, -1), ('mixed', 1, 0, -1), ('p', 18, 1, 0)]
    groups += [('back', 56, 1, 0)]
    for g, count, target, token in groups:
        for _ in range(count):
            rows.append(dict(id=f'{g}/{len(rows)}', group=g, side='back' if g == 'back' else 'front',
                             split='train', target=target, box=[.1, .1, .9, .9], image=g))
            tokens.append(token)
    for j in range(6):
        rows.append(dict(id=f'extra/{j}', group='ebay-pair-ff69b8955593fc', side='front', split='train',
                         target=int(j < 2), box=[.1, .1, .9, .9], image=f'extra-{j // 3}'))
        tokens.append(0 if j < 2 else -1)
    for row in rows:
        key = row['image']
        if key not in images:
            size = {'a': (958, 1330), 'b': (388, 500), 'c': (428, 585), 'ㄴ': (675, 930)}.get(key, (24, 32))
            name = 'Screenshot.png' if key == 'a' else 'img.png'
            path = root / 'generated' / key / name
            path.parent.mkdir(parents=True)
            Image.new('RGB', size, (len(images) * 11, 80, 140)).save(path)
            images[key] = path
        row['image'] = str(images[key])
        row['image_sha256'] = hashlib.sha256(images[key].read_bytes()).hexdigest()
    probabilities = [.8 if r['target'] else .2 for r in rows]
    for g, fp in zip(worker.TARGETS, (2, 1, 1, 4)):
        idx = [i for i, r in enumerate(rows[:147]) if r['side'] == 'front' and r['group'] == g]
        for i in idx[:fp]:
            probabilities[i] = .8
    x = torch.tensor([math.log(p / (1 - p)) for p in probabilities])[:, None, None].repeat(1, 2, 1)
    masks = torch.ones((153, 2), dtype=torch.bool)
    maps = x[:147, :, 0].sigmoid()
    fixed = dict(rows=rows, features=x, masks=masks, point_tokens=torch.tensor(tokens, dtype=torch.long))
    for path, value in ((worker.TYPED, fixed), (worker.LEGACY, fixed),
                        (worker.CURRENT, dict(maps=maps)), (worker.BASE + '/fold-heads.pt', dict(maps=maps))):
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        torch.save(value, dest)
    cohorts, required, declared = [], [], []
    scores = maps.max(1).values.tolist()
    for i in range(11):
        points = [f'point-{i}'] if i < 2 else []
        cohort_rows = [dict(id=f'point-{i}', target=1, human_token=i)] if points else rows[:147]
        values = [.7 if i == 0 else .3] if points else scores
        cohorts.append(dict(id=f'cohort-{i}', rows=cohort_rows, scores=values, point_ids=points,
                            point_scores=values if points else []))
        required.append(dict(id=f'cohort-{i}', rows=cohort_rows, before_scores=values,
                             point_ids=points, point_scores=values if points else []))
        declared.append(dict(id=f'cohort-{i}', reference_result=f'fake-{i}.json', acceptance={}))
    observation = dict(rows=rows[:147], scores=scores, required_cohorts=cohorts)
    reference = dict(rows=rows[:147], before_scores=scores, required_cohorts=required)
    source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in images.values()}
    documents = {'result.json': dict(rows=rows[:147], scores=scores), 'observations.json': observation,
                 'reference.json': reference, 'plan.json': dict(required_cohorts=declared),
                 'diagnostics.json': dict(source_sha256=source_hashes)}
    for name, value in documents.items():
        (root / worker.BASE / name).write_text(json.dumps(value))
    (root / 'card_condition').mkdir()
    for name in ('detail_bag.py', 'point_patch_head.py'):
        (root / 'card_condition' / name).write_text('# synthetic source placeholder')
    plan = json.loads(SOURCE.with_name('plan.json').read_text())
    plan['required_cohorts'] = declared
    plan['training_only_ids'] = [r['id'] for r in rows[147:]]
    plan['input_sha256'] = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                            for name in plan['input_sha256']}
    out = root / 'artifacts/experiments/synthetic'
    out.mkdir()
    (out / 'plan.json').write_text(json.dumps(plan))
    (out / 'reference.json').write_text(json.dumps(reference))
    canonical = root / plan['tracked_source']
    canonical.parent.mkdir(parents=True)
    shutil.copyfile(SOURCE, canonical)
    mirror = root / plan['code_changes'][0]['path']
    mirror.parent.mkdir(parents=True)
    shutil.copyfile(SOURCE, mirror)
    return plan, reference, out, mirror


class NormalCoexclusionWorkerTest(unittest.TestCase):
    def test_schedule_excludes_groups_photos_and_keeps_positive_and_extra_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, reference, *_ = fixture(root)
            ctx = worker.replay_baseline(root, plan, reference)
            splits = worker.pair_plan(ctx['rows'], ctx['all_rows'], ctx['identity'])
            self.assertEqual(16, len(splits))
            self.assertEqual([(g, None) for g in worker.TARGETS], [(s['g'], s['h']) for s in splits[:4]])
            self.assertEqual({(g, h) for g in worker.TARGETS for h in worker.TARGETS if h != g},
                             {(s['g'], s['h']) for s in splits[4:]})
            self.assertEqual([88] * 4 + [79] * 12, [len(s['train']) for s in splits])
            self.assertEqual(6, len({tuple(s['train']) for s in splits[4:]}))
            for split in splits:
                self.assertTrue(all(ctx['rows'][i]['group'] == split['g'] for i in split['held']))
                self.assertFalse({ctx['all_rows'][i]['group'] for i in split['train']} & {split['g'], split['h']})
                self.assertTrue(all(ctx['all_rows'][i]['side'] == 'front' for i in split['train']))
                self.assertTrue(set(range(147, 153)).issubset(split['train']))
            image = {g: next(r['image'] for r in ctx['all_rows'] if r['group'] == g) for g in ('a', 'c', 'p', 'ebay-pair-ff69b8955593fc')}
            for excluded, retained in (('a', 'p'), ('c', 'ebay-pair-ff69b8955593fc')):
                identity = copy.deepcopy(ctx['identity'])
                identity[image[excluded]].add('same-decoded')
                identity[image[retained]].add('same-decoded')
                with self.subTest(excluded=excluded), self.assertRaises(AssertionError):
                    worker.pair_plan(ctx['rows'], ctx['all_rows'], identity)
            changed = copy.deepcopy(ctx['all_rows'])
            changed[147]['group'] = 'a'
            with self.assertRaises(AssertionError):
                worker.pair_plan(ctx['rows'], changed, ctx['identity'])

    def test_mock_fit_weights_objective_convergence_and_target_mask(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, reference, *_ = fixture(root)
            ctx = worker.replay_baseline(root, plan, reference)
            split = worker.pair_plan(ctx['rows'], ctx['all_rows'], ctx['identity'])[4]
            mock = Mock(return_value=(torch.ones(1), torch.tensor(0.), dict(converged=True, max_gradient=0.)))
            coef, bias, _ = worker.fit_excluding(ctx['x'], ctx['masks'], ctx['tokens'], ctx['all_rows'], split, mock)
            features, masks, y, points, w = mock.call_args.args
            self.assertEqual(dict(penalty=1., normal_reduction='max_bound'), mock.call_args.kwargs)
            self.assertAlmostEqual(float(w[y == 0].sum()), float(w[y == 1].sum()), places=5)
            self.assertTrue(torch.equal(points, ctx['tokens'][split['train']]))
            self.assertTrue(torch.equal(features, ctx['x'][split['train']]))
            target = worker.target_scores(ctx['x'], ctx['masks'], split['held'], coef, bias)
            self.assertEqual(9, target['denominator'])
            masked = ctx['masks'].clone()
            masked[:, 1] = False
            x = ctx['x'].clone()
            x[:, 1] = 999
            self.assertEqual(target, worker.target_scores(x, masked, split['held'], coef, bias))
            for diag in (dict(converged=False, max_gradient=0.), dict(converged=True, max_gradient=2e-5),
                         dict(converged=True, max_gradient=math.nan)):
                mock.return_value = coef, bias, diag
                with self.subTest(diag=diag), self.assertRaises(AssertionError):
                    worker.fit_excluding(ctx['x'], ctx['masks'], ctx['tokens'], ctx['all_rows'], split, mock)
            mock.return_value = coef * math.inf, bias, dict(converged=True, max_gradient=0.)
            with self.assertRaises(AssertionError):
                worker.fit_excluding(ctx['x'], ctx['masks'], ctx['tokens'], ctx['all_rows'], split, mock)
            with self.assertRaises(AssertionError):
                worker.target_scores(ctx['x'] * torch.nan, ctx['masks'], split['held'], coef, bias)

    def test_frozen_rules_boundaries_counterexamples_and_unidentified(self):
        targets = worker.TARGETS
        baseline = {g: dict(fp=n, mean_max_logit=0.) for g, n in zip(targets, (2, 1, 1, 4))}
        same = [(g, h) for g in targets[1:] for h in targets[1:] if h != g]
        cross = [(g, 'a') for g in targets[1:]]
        h2 = {k: (2, .3) for k in same}
        opposite = {('b', 'c'): (0, 0.), ('b', 'ㄴ'): (4, 0.), ('c', 'b'): (4, 0.), ('c', 'ㄴ'): (0, 0.),
                    ('ㄴ', 'b'): (4, 0.), ('ㄴ', 'c'): (0, 0.)}
        # name, (Δfp, mean max logit) overrides, expected decision, expected raw conditions
        cases = [
            ('none', {}, 'unidentified', {}),
            ('H2 at Δ_same=2 and dL=0.3', h2, 'H2', {('c', 'dL_same>=0.3'): True}),
            ('H2 Δ_same just below', {k: (1, .3) for k in same}, 'unidentified', {('c', 'delta_same>=2'): False}),
            ('H2 Δ_same above', {k: (3, .3) for k in same}, 'H2', {}),
            ('H2 dL just below', {k: (2, .3 - 1e-9) for k in same}, 'unidentified', {('b', 'dL_same>=0.3'): False}),
            ('H2 dL just above', {k: (2, .3 + 1e-9) for k in same}, 'H2', {}),
            ('H2 dL gap just below', {**h2, **{k: (0, 1e-9) for k in cross}}, 'unidentified',
             {('b', 'dL_same>=0.3'): True, ('b', 'dL_same-dL_cross>=0.3'): False}),
            ('H2 dL gap just above', {**h2, **{k: (0, -1e-9) for k in cross}}, 'H2', {}),
            ('H2 |Δ_cross|=1', {**{k: (3, .3) for k in same}, **{k: (1, 0.) for k in cross}}, 'H2', {}),
            ('H2 Δ_cross=-1', {**h2, **{k: (-1, 0.) for k in cross}}, 'H2', {}),
            ('H2 gap just below', {**h2, **{k: (1, 0.) for k in cross}}, 'unidentified',
             {('c', '|delta_cross|<=1'): True, ('c', 'delta_same-delta_cross>=2'): False}),
            ('H2 rejects worsened cross', {**{k: (4, .6) for k in same}, **{k: (2, 0.) for k in cross}}, 'unidentified',
             {('b', '|delta_cross|<=1'): False, ('b', '|delta(c)-delta_cross|<=1'): False}),
            ('H2 a target |Δ|=1', {**h2, ('a', 'b'): (1, 0.), ('a', 'c'): (-1, 0.)}, 'H2', {}),
            ('H2 a target |Δ|=2', {**h2, ('a', 'c'): (2, 0.)}, 'unidentified', {'H2:a_all_|delta|<=1': False}),
            ('H2 one img target', {k: v for k, v in h2.items() if k[0] == 'b'}, 'unidentified', {('b', 'delta_same>=2'): True}),
            ('H2 two img targets', {k: v for k, v in h2.items() if k[0] != 'ㄴ'}, 'H2', {}),
            ('H1 at Δ_cross=2 with pair gaps 1',
             {**{k: (2, 0.) for k in cross}, **{k: (1 if k[1] == 'b' else 3, 0.) for k in same}}, 'H1',
             {('c', '|delta(b)-delta_cross|<=1'): True}),
            ('H1 Δ_cross just below', {k: (1, 0.) for k in same + cross}, 'unidentified', {('b', 'delta_cross>=2'): False}),
            ('H1 Δ_cross above', {k: (3, 0.) for k in same + cross}, 'H1', {}),
            ('H1 rejects opposite pairs hidden by mean', {**{k: (2, 0.) for k in cross}, **opposite}, 'unidentified',
             {('b', '|delta(c)-delta_cross|<=1'): False, ('b', '|delta(ㄴ)-delta_cross|<=1'): False}),
            ('H3 at FP gap 3', {('c', 'ㄴ'): (3, 0.), ('ㄴ', 'c'): (3, 0.)}, 'H3', {}),
            ('H3 at Δ=2 and |Δb|=1', {('c', 'ㄴ'): (2, 0.), ('c', 'b'): (-1, 0.), ('ㄴ', 'c'): (2, 0.), ('ㄴ', 'b'): (-1, 0.)},
             'H3', {'H3:delta(c,ㄴ)>=2': True, 'H3:|delta(c,b)|<=1': True}),
            ('H3 FP gap just below', {('c', 'ㄴ'): (3, 0.), ('c', 'b'): (1, 0.), ('ㄴ', 'c'): (3, 0.)}, 'unidentified',
             {'H3:FP(c,ㄴ)-FP(c,b)>=3': False, 'H3:|delta(c,b)|<=1': True}),
            ('H3 Δ just below', {('c', 'ㄴ'): (1, 0.), ('c', 'b'): (-1, 0.), ('ㄴ', 'c'): (3, 0.)}, 'unidentified',
             {'H3:delta(c,ㄴ)>=2': False}),
            ('H3 |Δb| just above', {('c', 'ㄴ'): (3, 0.), ('ㄴ', 'c'): (5, 0.), ('ㄴ', 'b'): (2, 0.)}, 'unidentified',
             {'H3:FP(ㄴ,c)-FP(ㄴ,b)>=3': True, 'H3:|delta(ㄴ,b)|<=1': False}),
            ('H3 one direction', {('c', 'ㄴ'): (3, 0.)}, 'unidentified', {'H3:delta(ㄴ,c)>=2': False}),
            ('H3 rejects recovered existing FP', {('c', 'ㄴ'): (2, 0.), ('c', 'b'): (-1, 0.), ('ㄴ', 'c'): (-1, 0.), ('ㄴ', 'b'): (-4, 0.)},
             'unidentified', {'H3:FP(ㄴ,c)-FP(ㄴ,b)>=3': True, 'H3:delta(ㄴ,c)>=2': False, 'H3:|delta(ㄴ,b)|<=1': False}),
            ('H2 and H3 together', {('c', 'ㄴ'): (4, .8), ('ㄴ', 'c'): (4, .8)}, 'unidentified', {}),
        ]
        for name, changes, decision, raw in cases:
            measurements = [dict(g=g, h=h, fp=baseline[g]['fp'] + changes.get((g, h), (0, 0.))[0], denominator=9,
                                 mean_max_logit=changes.get((g, h), (0, 0.))[1])
                            for g in targets for h in (None, *[v for v in targets if v != g])]
            with self.subTest(name):
                verdict = worker.judge(measurements, baseline)
                self.assertEqual(decision, verdict['decision'])
                self.assertEqual(['H2', 'H3'] if name == 'H2 and H3 together' else [decision] * (decision != 'unidentified'),
                                 verdict['matches'])
                for key, expected in raw.items():
                    found = verdict['subjects'][key[0]]['raw'][key[1]] if isinstance(key, tuple) else verdict['raw'][key]
                    self.assertIs(expected, found, key)
                self.assertFalse(verdict['independent'] or verdict['production_adopted'])
        empty = [dict(g=g, h=h, fp=baseline[g]['fp'], denominator=9, mean_max_logit=0.)
                 for g in targets for h in (None, *[v for v in targets if v != g])]
        for name, index, change in (('nan logit', 5, dict(mean_max_logit=math.nan)), ('inf logit', 5, dict(mean_max_logit=math.inf)),
                                    ('fp above 9', 5, dict(fp=10)), ('float fp', 5, dict(fp=1.)),
                                    ('denominator', 5, dict(denominator=8)), ('control mismatch', 0, dict(fp=3))):
            broken = copy.deepcopy(empty)
            broken[index].update(change)
            with self.subTest(name), self.assertRaises(AssertionError):
                worker.judge(broken, baseline)
        with self.assertRaises(AssertionError):
            worker.judge(empty[:-1], baseline)
        with self.assertRaises(AssertionError):
            worker.judge(empty, dict(baseline, a=dict(fp=2, mean_max_logit=math.nan)))

    def test_replay_preserves_typed_legacy_cohorts_and_rejects_changed_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, reference, *_ = fixture(root)
            ctx = worker.replay_baseline(root, plan, reference)
            self.assertEqual(0., ctx['replay_error'])
            self.assertEqual(reference['before_scores'], ctx['replay'])
            self.assertNotEqual(ctx['observation']['required_cohorts'][0]['point_ids'],
                                ctx['observation']['required_cohorts'][1]['point_ids'])
            original = copy.deepcopy(ctx['observation'])
            ctx['observation']['required_cohorts'][0]['scores'][0] = .1
            self.assertEqual(.7, original['required_cohorts'][0]['scores'][0])
            photo = Path(ctx['all_rows'][0]['image'])
            photo.write_bytes(b'changed')
            with self.assertRaises(AssertionError):
                worker.replay_baseline(root, plan, reference)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, reference, *_ = fixture(root)
            path = root / worker.BASE / 'observations.json'
            changed = json.loads(path.read_text())
            changed['required_cohorts'][0]['point_ids'] = ['typed-not-legacy']
            path.write_text(json.dumps(changed))
            plan['input_sha256'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaises(AssertionError):
                worker.replay_baseline(root, plan, reference)
        for name, offset in (('replay above 2e-5', 3e-5), ('non-finite replay', math.nan)):
            with tempfile.TemporaryDirectory() as folder, self.subTest(name):
                root = Path(folder)
                plan, reference, *_ = fixture(root)
                path = root / worker.BASE / 'fold-heads.pt'
                maps = torch.load(path, weights_only=True)['maps']
                maps[0] += offset
                torch.save(dict(maps=maps), path)
                plan['input_sha256'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
                with self.assertRaises(AssertionError):
                    worker.replay_baseline(root, plan, reference)

    def test_synthetic_main_mocked_fit_order_abort_and_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            plan, reference, out, mirror = fixture(root)
            fitter = Mock(return_value=(torch.ones(1), torch.tensor(0.), dict(converged=True, max_gradient=0.)))
            env = dict(CARD_CONDITION_EXPERIMENT_DIR=str(out), CARD_CONDITION_EXPERIMENT_REFERENCE=str(out / 'reference.json'))
            with patch.dict(os.environ, env), patch('card_condition.detail_bag.fit_detail_head', fitter), \
                    patch.object(sys, 'path', list(sys.path)), contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(mirror), run_name='__main__')
            self.assertEqual(16, fitter.call_count)
            diagnostics = json.loads((out / 'diagnostics.json').read_text())
            self.assertEqual([None] * 4, [m['h'] for m in diagnostics['measurements'][:4]])
            self.assertEqual('unidentified', diagnostics['verdict']['decision'])
            self.assertEqual([], diagnostics['verdict']['matches'])
            saved = json.loads((out / 'observations.json').read_text())
            evidence = saved.pop('diagnostic_evidence')
            self.assertEqual(saved, json.loads((root / worker.BASE / 'observations.json').read_text()))
            self.assertLessEqual(len(json.dumps(evidence, ensure_ascii=False, allow_nan=False).encode()), 4000)
            self.assertEqual(12, len(evidence['pairs']))
            self.assertIn('H3:|delta(ㄴ,b)|<=1', evidence['raw'])
            self.assertEqual(16, len(list((out / 'images').glob('*.png'))))
            page = (out / 'index.html').read_text()
            self.assertEqual(16, page.count('<article>'))
            for text in ('FP ', '/9', '30/100', '독립시험·운영채택 아님', '단독 제외 대비'):
                self.assertIn(text, page)
            for name, bias in (('zero coefficients', None), ('reproduction just above 1e-4', 1e-3)):
                failed = root / 'artifacts/experiments' / name.replace(' ', '-')
                failed.mkdir()
                shutil.copyfile(out / 'plan.json', failed / 'plan.json')
                coef = torch.zeros(1) if bias is None else torch.ones(1)
                fitter = Mock(return_value=(coef, torch.tensor(bias or 0.), dict(converged=True, max_gradient=0.)))
                env['CARD_CONDITION_EXPERIMENT_DIR'] = str(failed)
                with self.subTest(name), patch.dict(os.environ, env), patch('card_condition.detail_bag.fit_detail_head', fitter), \
                        patch.object(sys, 'path', list(sys.path)), self.assertRaises(AssertionError):
                    runpy.run_path(str(mirror), run_name='__main__')
                self.assertEqual(1, fitter.call_count)
                self.assertFalse((failed / 'diagnostics.json').exists())
                self.assertFalse((failed / 'observations.json').exists())

    def test_structure_and_plan_are_frozen(self):
        for source in (SOURCE, Path(__file__)):
            tree = ast.parse(source.read_text())
            self.assertLessEqual(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(tree)), 7)
        tree = ast.parse(SOURCE.read_text())
        names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        graph = {n.name: {c.func.id for c in ast.walk(n) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} & names
                 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        self.assertEqual(dict(pair_plan=set(), fit_excluding=set(), target_scores=set(), judge=set(),
                              replay_baseline=set(), render=set(), finish={'judge', 'render'}), graph)
        guard = next(n for n in tree.body if isinstance(n, ast.If))
        self.assertIn('fit_excluding', {c.func.id for c in ast.walk(guard) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)})
        # Cross-file fit path: fit_excluding -> fit_detail_head -> closure -> detail_bag_loss -> point_bag_loss (4).
        detail = ast.parse((REPO / 'card_condition/detail_bag.py').read_text())
        point = ast.parse((REPO / 'card_condition/point_patch_head.py').read_text())
        defs = {n.name: n for n in ast.walk(detail) if isinstance(n, ast.FunctionDef)}
        defs['point_bag_loss'] = next(n for n in point.body if isinstance(n, ast.FunctionDef) and n.name == 'point_bag_loss')
        edges = {k: {c.func.id for c in ast.walk(v) if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)} & set(defs)
                 for k, v in defs.items()}
        self.assertEqual({'fit_detail_head', 'closure', 'detail_bag_loss', 'point_bag_loss'}, set(defs))
        self.assertEqual({'closure', 'detail_bag_loss'}, edges['fit_detail_head'])
        self.assertEqual(({'detail_bag_loss'}, {'point_bag_loss'}, set()),
                         (edges['closure'], edges['detail_bag_loss'], edges['point_bag_loss']))
        self.assertEqual(set(), {c.func.id for c in ast.walk(defs['point_bag_loss'])
                                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
                         & {n.name for n in point.body if isinstance(n, ast.FunctionDef)})
        # Static plan check against the common runner's own validation rules (no runner execution).
        plan = json.loads(SOURCE.with_name('plan.json').read_text())
        for key in ('hypothesis_id', 'hypothesis', 'change', 'success_criterion', 'failure_criterion'):
            self.assertTrue(plan[key].strip())
        self.assertEqual(dict(max_fn=16, max_fp=18, no_new_errors=True, require_actual_point_guard=False),
                         experiment_record.acceptance_rules(plan['acceptance']))
        self.assertEqual((.5, False, False, 'diagnostic', 0),
                         (plan['threshold'], plan['independent'], plan['production_adopted'],
                          plan['experiment_kind'], plan['gemini_calls_allowed']))
        self.assertEqual(worker.BASE + '/result.json', plan['reference_result'])
        previous = json.loads((REPO / 'tools/experiments/surface-front-joint-holdout-baseline-20261025/plan.json').read_text())
        self.assertEqual(previous['required_cohorts'], plan['required_cohorts'])
        self.assertEqual(11, len({c['id'] for c in plan['required_cohorts']}))
        for cohort in plan['required_cohorts']:
            self.assertEqual({'id', 'reference_result', 'acceptance'}, set(cohort))
            experiment_record.acceptance_rules(cohort['acceptance'])
        self.assertEqual([dict(path='artifacts/surface-normal-coexclusion-20261025/worker.py', baseline=None)], plan['code_changes'])
        self.assertEqual(str(SOURCE.relative_to(REPO)), plan['tracked_source'])
        self.assertEqual(worker.TYPED, plan['cache_source'])
        self.assertTrue({worker.TYPED, worker.LEGACY, worker.CURRENT, worker.BASE + '/fold-heads.pt'} <= set(plan['input_sha256']))
        self.assertEqual(6, len(plan['training_only_ids']))
        runner = inspect.getsource(experiment_record.complete)
        for text in ("'diagnostic'", '4000', 'primary_acceptance_passed'):
            self.assertIn(text, runner)
        self.assertIn("independent', False) is not False", inspect.getsource(experiment_record.prepare))


if __name__ == '__main__':
    unittest.main()

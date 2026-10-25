import importlib.util
from pathlib import Path
import unittest

import torch

PATH = Path(__file__).resolve().parents[1]/'tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py'
spec = importlib.util.spec_from_file_location('front_joint_worker', PATH)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)


def synthetic():
    """Four front groups (two clicked, two normal) plus one back row; images are unique per group."""
    rows = [dict(id=f'{g}/front/{k}', group=g, side='front', target=t, image=f'{g}.png')
            for g, t in (('p1', 1), ('p2', 1), ('n1', 0), ('n2', 0)) for k in range(2)]
    rows.append(dict(id='p1/back/0', group='p1', side='back', target=1, image='p1b.png'))
    all_rows = rows + [dict(id='extra/front/0', group='extra', side='front', target=0, image='extra.png')]
    identity = {r['image']: {r['image']} for r in all_rows}
    def fold(fid, held):
        return dict(id=fid, held_groups=held,
                    train_ids=[r['id'] for r in all_rows if r['side'] == 'front' and r['group'] not in held],
                    held_ids=[r['id'] for r in rows if r['side'] == 'front' and r['group'] in held])
    proposal = dict(folds=[fold('f1', ['p1', 'n1']), fold('f2', ['p2', 'n2'])])
    return rows, all_rows, identity, proposal


class FrontJointHoldoutWorkerTest(unittest.TestCase):
    def test_folds_cover_front_once_and_reject_leakage(self):
        rows, all_rows, identity, proposal = synthetic()
        folds = worker.check_folds(proposal, all_rows, rows, identity)
        self.assertEqual(sorted(i for _, _, held in folds for i in held), list(range(8)))
        shared = dict(identity, **{'p1.png': {'p1.png', 'same-decoded'}, 'p2.png': {'p2.png', 'same-decoded'}})
        with self.assertRaises(AssertionError):
            worker.check_folds(proposal, all_rows, rows, shared)
        broken = dict(folds=proposal['folds'][:1])
        with self.assertRaises(AssertionError):
            worker.check_folds(broken, all_rows, rows, identity)

    def test_front_uses_only_its_fold_head_and_back_is_unchanged(self):
        rows, all_rows, identity, proposal = synthetic()
        folds = worker.check_folds(proposal, all_rows, rows, identity)
        x = torch.zeros(len(all_rows), 3, 2)
        mask = torch.ones(len(all_rows), 3, dtype=torch.bool)
        tokens = torch.full((len(all_rows),), -1, dtype=torch.long)
        base = torch.full((len(rows), 3), .25)
        seen = []
        def fake_fit(features, masks, y, points, weights, penalty, normal_reduction):
            seen.append((len(features), float(weights[y == 1].sum()), float(weights[y == 0].sum()), normal_reduction))
            return torch.zeros(2), torch.tensor(float(len(seen))), dict(converged=True)
        maps, fits, heads = worker.joint_holdout_maps(x, mask, tokens, all_rows, rows, folds, base, fake_fit)
        self.assertEqual([5, 5], [n for n, *_ in seen])
        self.assertTrue(all(abs(pos - neg) < 1e-6 and objective == 'max_bound' for _, pos, neg, objective in seen))
        self.assertTrue(torch.equal(maps[8], base[8]))
        self.assertAlmostEqual(float(maps[0][0]), float(torch.tensor(1.).sigmoid()), places=6)
        self.assertAlmostEqual(float(maps[2][0]), float(torch.tensor(2.).sigmoid()), places=6)
        self.assertEqual(['f1', 'f2'], [f['fold'] for f in fits])

    def test_front_metrics_keep_denominators_and_changes(self):
        rows, *_ = synthetic()
        before = [.9, .9, .9, .1, .1, .1, .1, .6, .9]
        after = [.9, .2, .9, .9, .1, .1, .7, .1, .1]
        metrics = worker.front_metrics(rows, after, before)
        self.assertEqual(dict(fn=1, fp=1, positives=4, negatives=4, positive_groups=2, negative_groups=2),
                         metrics['before_single_group_heads'])
        self.assertEqual((1, 1), (metrics['joint_holdout']['fn'], metrics['joint_holdout']['fp']))
        self.assertEqual(['p1/front/1'], metrics['new_fn'])
        self.assertEqual(['n2/front/0'], metrics['new_fp'])
        self.assertEqual(['p2/front/1', 'n2/front/1'], metrics['recovered'])


if __name__ == '__main__':
    unittest.main()

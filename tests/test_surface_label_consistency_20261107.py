"""Synthetic checks for the isolated surface-label comparison; no photos or model inference."""
import importlib.util
from pathlib import Path
import unittest

import numpy as np

SPEC = importlib.util.spec_from_file_location('surface_label_metrics',Path(__file__).resolve().parents[1]/'tools/experiments/surface-label-consistency-20261107/metrics.py')
MET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MET)


class SurfaceLabelConsistencyTests(unittest.TestCase):
    def test_labels_preserve_original_and_exclude_impossible_from_both(self):
        rows = [dict(id='a',group='a',target=0),dict(id='b',group='b',target=0),dict(id='c',group='c',target=1)]
        keep,old,new = MET.label_rows(rows,{'a':'결함','b':'불가'})
        self.assertEqual(keep,[0,2]); self.assertEqual([r['target'] for r in old],[0,1]); self.assertEqual([r['target'] for r in new],[1,1])
        self.assertEqual([r['target'] for r in rows],[0,0,1])
        with self.assertRaises(ValueError): MET.label_rows(rows,{'a':'미확인'})
        with self.assertRaises(ValueError): MET.label_rows(rows,{'unknown':'정상'})

    def test_auc_matches_pair_count_with_ties_and_group_multiplicity(self):
        y,s,w = [0,1,0,1],[.1,.5,.5,.9],[2,3,1,2]
        expanded = [(label,score) for label,score,n in zip(y,s,w) for _ in range(n)]
        pos = [s for y,s in expanded if y]; neg = [s for y,s in expanded if not y]
        brute = sum((p>n)+.5*(p==n) for p in pos for n in neg)/(len(pos)*len(neg))
        self.assertAlmostEqual(MET.auc(y,s,w),brute)
        self.assertEqual(MET.auc([0,1],[.5,.5]),.5)

    def test_metrics_and_paired_bootstrap(self):
        rows = [dict(group=g,target=y) for g in ('a','b','c') for y in (0,1)]
        scores = [.6,.4,.2,.8,.1,.9]
        m = MET.metrics(rows,scores)
        self.assertEqual((m['fn'],m['fp'],m['positive'],m['negative']),(1,1,3,3))
        b = MET.paired_bootstrap(rows,scores,scores,50,20261107)
        self.assertEqual((b['lo'],b['hi'],b['draws']),(0.,0.,50))
        labels = [r['target'] for r in rows]
        rng = np.random.RandomState(20261107)
        expected = []
        other = list(reversed(scores))
        for _ in range(50):
            idx = [i for group in rng.randint(3,size=3) for i in (2*group,2*group+1)]
            expected.append(MET.auc([labels[i] for i in idx],[scores[i] for i in idx])-MET.auc([labels[i] for i in idx],[other[i] for i in idx]))
        expected.sort()
        actual = MET.paired_bootstrap(rows,scores,other,50,20261107)
        self.assertAlmostEqual(actual['lo'],expected[int(.025*49)])
        self.assertAlmostEqual(actual['hi'],expected[int(.975*49)])

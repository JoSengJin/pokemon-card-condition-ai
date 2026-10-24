import copy
import unittest
import torch
from card_condition.observation_nested import nested_back_glare, nested_glare
from card_condition.visibility_model import TARGET


class NestedObservationTest(unittest.TestCase):
    def test_group_exclusion_and_held_truth_does_not_set_threshold(self):
        rows=[dict(card_id=str(i),group=str(i),split='train',side='back',
            labels={TARGET:int(i>=4)},visibility_issues=['glare'] if i>=4 else []) for i in range(8)]
        features=torch.tensor([[.0],[.1],[.2],[.3],[.7],[.8],[.9],[1.]])
        result=nested_back_glare(features,rows)
        self.assertEqual(8,result['faces'])
        self.assertEqual((4,4),tuple(result['rate_comparison']['reference'][k] for k in ('positive','negative')))
        for fold in result['folds']:
            self.assertNotIn(fold['held_group'],fold['fit_groups'])
            self.assertEqual(0,fold['inner_fp'])
            for inner in fold['inner_folds']:
                self.assertNotIn(inner['held_group'],inner['fit_groups'])
                self.assertNotIn(fold['held_group'],inner['fit_groups'])
        changed=copy.deepcopy(rows);changed[-1]['labels'][TARGET]=0
        other=nested_back_glare(features,changed)
        self.assertEqual(result['predictions'][-1]['score'],other['predictions'][-1]['score'])
        self.assertEqual(result['predictions'][-1]['threshold'],other['predictions'][-1]['threshold'])
        self.assertFalse(result['production_ready'])
        rows[0]['split']='val'
        with self.assertRaisesRegex(ValueError,'training-only'):nested_back_glare(features,rows)
        with self.assertRaises(ValueError):nested_back_glare(torch.full((8,1),float('nan')),changed)
        with self.assertRaises(ValueError):nested_back_glare(features[:3],changed[:3])

    def test_front_reuses_group_exclusion_without_reading_back_or_test(self):
        rows=[dict(card_id=str(i),group=str(i),split='train',side='front',
            labels={TARGET:int(i>=4)},visibility_issues=['glare'] if i>=4 else []) for i in range(8)]
        features=torch.tensor([[.0],[.1],[.2],[.3],[.7],[.8],[.9],[1.]])
        front=nested_glare(features,rows,side='front')
        back=nested_back_glare(features,[{**r,'side':'back'} for r in rows])
        self.assertEqual(front['fixed_counts'],back['fixed_counts'])
        self.assertEqual(front['nested_counts'],back['nested_counts'])
        self.assertTrue(all(r['side']=='front' for r in front['predictions']))
        for fold in front['folds']:
            for inner in fold['inner_folds']:
                self.assertNotIn(fold['held_group'],inner['fit_groups'])
                self.assertNotIn(inner['held_group'],inner['fit_groups'])
        augmented=rows+[dict(card_id='b',group='b',split='train',side='back',labels={TARGET:1},visibility_issues=['glare'])]
        mixed=nested_glare(torch.cat((features,torch.tensor([[100.]]))),augmented,side='front')
        self.assertEqual(front['predictions'],mixed['predictions'])
        with self.assertRaisesRegex(ValueError,'side required'):nested_glare(features,rows,side='other')
        with self.assertRaisesRegex(ValueError,'training-only'):nested_glare(features,[{**r,'split':'test'} for r in rows],side='front')

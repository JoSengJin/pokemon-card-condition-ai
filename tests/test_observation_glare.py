import copy
import unittest
import torch
from card_condition.observation_glare import compare_glare,glare_cohort
from card_condition.visibility_model import TARGET


class GlareTest(unittest.TestCase):
    def test_other_restrictions_unknown_and_fit_and_baseline_use_same_cohort(self):
        torch.set_num_threads(1)
        rows=[]
        for group,issues in (('a',[]),('b',[]),('c',['glare']),('d',['glare']),('e',['shadow'])):
            for side in ('front','back'):
                rows.append(dict(card_id=group,group=group,side=side,split='train',
                    labels={TARGET:int(bool(issues))},visibility_issues=issues,box=[0,0,1,1],image_hashes=[group]))
        baseline=[dict(**r,excluded_fit_group=r['group'],probabilities={TARGET:.8 if r['labels'][TARGET] else .2}) for r in rows]
        folds=[dict(group=g,train_indices=[i for i,r in enumerate(rows) if r['group']!=g],
                    held_indices=[i for i,r in enumerate(rows) if r['group']==g]) for g in ('a','b','c','d','e')]
        original=copy.deepcopy(rows)
        result=compare_glare(torch.tensor([[float(r['labels'][TARGET])] for r in rows]),rows,folds,baseline)
        self.assertEqual(original,rows)
        self.assertEqual(8,result['eligible_faces'])
        self.assertEqual(8,result['scored_faces'])
        self.assertEqual(8,result['baseline']['faces'])
        self.assertEqual(2,len(result['other_restriction_faces']))
        self.assertFalse(glare_cohort(rows[-1]))
        self.assertTrue(glare_cohort(dict(labels={TARGET:1},visibility_issues=['shadow','glare'])))
        for fold in result['fit_folds']:
            self.assertNotIn(fold['excluded_group'],fold['fit_groups'])
            self.assertNotIn('e',fold['fit_groups'])
            self.assertTrue(all(glare_cohort(rows[i]) for i in fold['train_indices']))
        # Keeping just one glare group makes its held fold ineligible, never silently correct.
        fewer=[f for f in folds if f['group']!='d']
        changed=[dict(r,visibility_issues=['shadow']) if r['group']=='d' else r for r in rows]
        refused=compare_glare(torch.tensor([[float(r['labels'][TARGET])] for r in rows]),changed,fewer,baseline)
        self.assertEqual(1,len(refused['refused_folds']))
        self.assertFalse(refused['research_direction_supported'])
        self.assertEqual('insufficient_scored_support',refused['status'])
        self.assertIsNone(refused['candidate'])
        self.assertIsNone(refused['paired_group_sensitivity'])
        self.assertEqual(2,refused['refused_folds'][0]['unscored_faces'])

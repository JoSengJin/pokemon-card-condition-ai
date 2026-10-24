import copy
import unittest
from card_condition.observation_bootstrap import paired_group_bootstrap


def row(group,side,truth,score):
    return dict(card_id=group,group=group,side=side,split='train',excluded_fit_group=group,
        labels={'observation_limited':truth},probabilities={'observation_limited':score},
        image_hashes=[group],box=[0,0,1,1],visibility_issues=['glare'] if truth else [])


class GroupBootstrapTest(unittest.TestCase):
    def test_paired_identical_candidates_have_zero_delta_and_are_unchanged(self):
        rows=[row('a','front',0,.2),row('a','back',1,.8),
              row('b','front',0,.8),row('b','back',1,.2)]
        original=copy.deepcopy(rows)
        result=paired_group_bootstrap(rows,copy.deepcopy(rows))
        self.assertEqual(result,paired_group_bootstrap(rows,rows))
        self.assertEqual(result,paired_group_bootstrap(list(reversed(rows)),list(reversed(rows))))
        self.assertEqual(original,rows)
        self.assertEqual(2000,result['usable_replicates'])
        for metric in ('fpr_delta','fnr_delta'):
            self.assertEqual(dict(observed=0.,spread=dict(empirical_p025=0.,empirical_p975=0.)),result[metric])

    def test_whole_group_draws_keep_photos_together(self):
        before=[row('a','front',0,.8),row('a','back',1,.2),
                row('b','front',0,.2),row('b','back',1,.8)]
        after=copy.deepcopy(before)
        after[0]['probabilities']['observation_limited']=.2
        after[1]['probabilities']['observation_limited']=.8
        result=paired_group_bootstrap(before,after)
        self.assertEqual(-.5,result['fpr_delta']['observed'])
        self.assertEqual(result['fpr_delta'],result['fnr_delta'])
        self.assertEqual(dict(empirical_p025=-1.,empirical_p975=0.),result['fpr_delta']['spread'])

    def test_missing_class_draws_are_counted_and_bad_pairings_rejected(self):
        rows=[row('a','front',0,.2),row('b','front',1,.8)]
        result=paired_group_bootstrap(rows,rows)
        self.assertGreater(result['skipped_single_class_replicates'],0)
        self.assertEqual(2000,result['usable_replicates']+result['skipped_single_class_replicates'])
        for field,value in (('group','different'),('box',[.1,0,1,1]),('labels',{'observation_limited':0})):
            other=copy.deepcopy(rows);other[1][field]=value
            if field=='group':other[1]['excluded_fit_group']=value
            with self.assertRaisesRegex(ValueError,'differ'):
                paired_group_bootstrap(rows,other)
        with self.assertRaisesRegex(ValueError,'nonempty'):
            paired_group_bootstrap(rows,rows[:1])
        with self.assertRaisesRegex(ValueError,'both observation'):
            paired_group_bootstrap([row('a','front',0,.2),row('b','front',0,.2)],
                                   [row('a','front',0,.2),row('b','front',0,.2)])
        for score in (float('nan'),float('inf'),1.1):
            other=copy.deepcopy(rows);other[0]['probabilities']['observation_limited']=score
            with self.assertRaisesRegex(ValueError,'Invalid'):
                paired_group_bootstrap(rows,other)

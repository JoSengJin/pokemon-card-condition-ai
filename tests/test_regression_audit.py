import unittest
from card_condition.regression_audit import compare_predictions

class RegressionAuditTest(unittest.TestCase):
    def test_aggregate_improvement_cannot_hide_new_miss(self):
        r=compare_predictions([1,1,1,0],[.9,.1,.2,.1],[.1,.9,.9,.1])
        self.assertTrue(r['aggregate_improved'])
        self.assertFalse(r['no_new_errors'])
        self.assertEqual(r['new_misses'],[0])
        self.assertEqual(r['recovered'],[1,2])

    def test_equal_totals_can_swap_wrong_normal_regions(self):
        r=compare_predictions([0,0],[.8,.1],[.1,.8])
        self.assertEqual(r['before'],r['after'])
        self.assertFalse(r['no_new_errors'])
        self.assertEqual(r['new_false_positives'],[1])

    def test_threshold_and_unchanged_predictions(self):
        r=compare_predictions([1,0],[.5,.49],[.5,.49])
        self.assertTrue(r['no_new_errors'])
        self.assertFalse(r['aggregate_improved'])
        self.assertEqual(r['after'],dict(tp=1,tn=1,fp=0,fn=0))

    def test_constant_predictor_is_not_informative_improvement(self):
        r=compare_predictions([1,0],[.1,.9],[.9,.9])
        self.assertTrue(r['aggregate_improved'])
        self.assertEqual(r['constant_prediction'],1)
        self.assertFalse(r['informative_improvement'])
        self.assertTrue(r['both_classes_evaluated'])

    def test_positive_only_recall_does_not_prove_classifier_quality(self):
        r=compare_predictions([1,1],[.1,.1],[.9,.9])
        self.assertTrue(r['aggregate_improved'])
        self.assertFalse(r['both_classes_evaluated'])
        self.assertFalse(r['informative_improvement'])

    def test_unknown_or_unpaired_or_invalid_scores_rejected(self):
        for t,a,b in [([],[],[]),([1],[.5],[]),([None],[.1],[.2]),
                      ([True],[.1],[.2]),([0],[float('nan')],[.2]),([0],[.1],[1.1])]:
            with self.assertRaises(ValueError):compare_predictions(t,a,b)


class PairedRunTest(unittest.TestCase):
    def rows(self):
        return [dict(id=k, group=k, side='front', split='train',
                     image_sha256=k, card_box=[0,0,1,1], box=[0,0,.3,.3],
                     labels={'surface_defect':v}) for k,v in [('a',1),('b',0)]]

    def test_reordering_cannot_create_false_improvement(self):
        from card_condition.regression_audit import compare_runs
        r=self.rows()
        result=compare_runs(r,[.8,.2],r[::-1],[.2,.8],'surface_defect')
        self.assertEqual(result['before'],result['after'])
        self.assertTrue(result['no_new_errors'])

    def test_changed_evidence_population_truth_and_duplicates_rejected(self):
        import copy
        from card_condition.regression_audit import compare_runs
        rows=self.rows()
        for field,value in [('box',[0,0,.4,.4]),('image_sha256','changed'),
                            ('group','changed'),('labels',{'surface_defect':0})]:
            changed=copy.deepcopy(rows);changed[0][field]=value
            with self.assertRaises(ValueError):
                compare_runs(rows,[.8,.2],changed,[.8,.2],'surface_defect')
        for changed,scores in [(rows[:1],[.8]),([rows[0],rows[0]],[.8,.8]),(rows,[.8])]:
            with self.assertRaises(ValueError):
                compare_runs(rows,[.8,.2],changed,scores,'surface_defect')

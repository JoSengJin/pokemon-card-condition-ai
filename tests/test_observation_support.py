import copy
import unittest
from card_condition.observation_support import fold_reason_support
from card_condition.visibility_model import TARGET


def face(card,group,side,reasons,score):
    return dict(card_id=card,group=group,side=side,visibility_issues=reasons,
                labels={TARGET:int(bool(reasons))},probabilities={TARGET:score})


class ObservationSupportTest(unittest.TestCase):
    def test_group_and_side_exclusion_multi_reason_and_false_positives(self):
        rows=[face('a','same','front',['shadow','glare'],.2),
              face('a-photo2','same','front',['shadow'],.9),
              face('b','other','back',['shadow'],.9),
              face('c','third','front',['glare'],.8),
              face('d','clear','front',[],.8)]
        original=copy.deepcopy(rows)
        report=fold_reason_support(rows,{'model':rows})
        self.assertEqual(original,rows)
        candidate=report['candidates']['model']
        shadow=next(r for r in candidate['reasons'] if r['side']=='front' and r['reason']=='shadow')
        self.assertEqual(dict(faces=2,groups=1,detected=1,missed=1,recall=.5),shadow['support_strata']['no_other_group'])
        self.assertIsNone(shadow['support_strata']['has_other_group']['recall'])
        glare=next(r for r in candidate['positive_face_reasons'] if r['card_id']=='a' and r['reason']=='glare')
        self.assertEqual(['third'],glare['other_fit_groups'])
        self.assertEqual(dict(tp=2,tn=0,fp=1,fn=1),candidate['metrics_by_side']['front'])
        self.assertFalse(report['affects_predictions'])

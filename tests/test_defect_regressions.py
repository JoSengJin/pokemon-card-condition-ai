import unittest
from card_condition.defect_regressions import defect_regressions


def error(name, kind='fn', label='edge_defect'):
    return dict(id=name,label=label,kind=kind,area='upper_left',group=name)


class DefectRegressionsTest(unittest.TestCase):
    def compare(self, old, new):
        return defect_regressions(old,new,['edge_defect'])['edge_defect']

    def test_fewer_misses_cannot_hide_newly_lost_defect(self):
        r=self.compare([error('a'),error('b'),error('c')],[error('d')])
        self.assertEqual((1,3,0),(r['new_miss_count'],r['recovered_count'],r['persistent_miss_count']))
        self.assertFalse(r['recall_improvement_without_regression'])
        self.assertEqual('d',r['newly_missed'][0]['id'])

    def test_recovery_requires_no_extra_false_positive(self):
        old=[error('a'),error('b')]
        self.assertTrue(self.compare(old,[error('b')])['recall_improvement_without_regression'])
        self.assertFalse(self.compare(old,[error('b'),error('c','fp')])['recall_improvement_without_regression'])
        self.assertFalse(self.compare(old,old)['recall_improvement_without_regression'])
        self.assertFalse(self.compare([],[])['recall_improvement_without_regression'])

    def test_types_stay_separate_and_evidence_preserved(self):
        old=[error('a'),error('a',label='surface_defect')]
        new=[error('a',label='surface_defect')]
        r=defect_regressions(old,new,['edge_defect','surface_defect'])
        self.assertEqual(old[0],r['edge_defect']['recovered'][0])
        self.assertEqual(1,r['surface_defect']['persistent_miss_count'])
        self.assertFalse(r['edge_defect']['severity_known'])
        self.assertFalse(r['edge_defect']['production_ready'])

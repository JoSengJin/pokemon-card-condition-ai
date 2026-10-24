import unittest
from card_condition.observation_clearance import clearance_cutoff, clearance_summary


class ObservationClearanceTest(unittest.TestCase):
    def test_inner_boundary_ties_and_positive_side_never_clear(self):
        inner=[dict(truth=1,score=.42),dict(truth=1,score=.6),dict(truth=0,score=.1)]
        cutoff=clearance_cutoff(inner)
        self.assertEqual(.42,cutoff)
        self.assertEqual(.5,clearance_cutoff([dict(truth=1,score=.8),dict(truth=0,score=.1)]))
        result=clearance_summary([dict(truth=1,score=.42,clearance_cutoff=cutoff),dict(truth=0,score=.4,clearance_cutoff=cutoff)])
        self.assertEqual(dict(limited_cleared=0,clear_cleared=1,limited_deferred=1,clear_deferred=0),result['counts'])
        self.assertEqual(.5,result['clearance_coverage'])
        self.assertTrue(result['nontrivial_research_support'])
        self.assertFalse(result['production_ready'])
        self.assertEqual(0,result['actual_calls_saved'])

    def test_deferral_does_not_hide_unsafe_clearance_or_count_as_detection(self):
        result=clearance_summary([dict(truth=1,score=.2,clearance_cutoff=.3),dict(truth=1,score=.4,clearance_cutoff=.3),dict(truth=0,score=.4,clearance_cutoff=.3)])
        self.assertEqual(.5,result['unsafe_clearance_rate'])
        self.assertEqual(2,result['deferred'])
        self.assertEqual(0,result['normal_clearance_rate'])
        self.assertFalse(result['nontrivial_research_support'])
        for inner in ([],[dict(truth=1,score=.4)],[dict(truth=0,score=.4)]):
            self.assertIsNone(clearance_cutoff(inner))
        result=clearance_summary([dict(truth=1,score=.2,clearance_cutoff=None),dict(truth=0,score=.1,clearance_cutoff=None)])
        self.assertEqual(0,result['clearance_coverage'])
        self.assertFalse(result['nontrivial_research_support'])
        self.assertIsNone(clearance_summary([])['unsafe_clearance_rate'])

    def test_invalid_evidence_fails_instead_of_clearing(self):
        for row in [dict(truth=None,score=.2),dict(truth=True,score=.2),dict(truth=0,score=float('nan')),dict(truth=1,score=1.2),dict(truth=0,score='0.2')]:
            with self.assertRaises(ValueError):clearance_cutoff([row])
        for cutoff in [float('nan'),float('inf'),-.1,.6,True,'0.4']:
            with self.assertRaises(ValueError):clearance_summary([dict(truth=0,score=.1,clearance_cutoff=cutoff)])

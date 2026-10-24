import unittest
from card_condition.recall_review import review_labels

class RecallReviewTest(unittest.TestCase):
    def test_union_keeps_old_detections_and_adds_candidate(self):
        rows=review_labels({'edge':.7,'surface':.2},{'edge':.1,'surface':.6})
        self.assertEqual(['edge','surface'],[r['label'] for r in rows])
        self.assertTrue(all(r['action']=='review_required' for r in rows))
    def test_unknown_not_clean_and_boundary(self):
        self.assertEqual([],review_labels({'edge':None},{'edge':.9}))
        self.assertEqual([],review_labels({'edge':.2},{'edge':None}))
        self.assertEqual(1,len(review_labels({'edge':.5},{'edge':.1})))

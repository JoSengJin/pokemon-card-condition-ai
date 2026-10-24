import unittest
from card_condition.edge_hybrid_review import review_route
class HybridReviewTests(unittest.TestCase):
 def test_original_positive_is_never_cleared(self):
  self.assertTrue(review_route(.8,.1)['flagged_for_review'])
  self.assertFalse(review_route(.8,.1)['additional_review'])
 def test_new_signal_is_review_not_truth(self):
  result=review_route(.2,.7)
  self.assertTrue(result['additional_review']);self.assertTrue(result['human_review_required']);self.assertFalse(result['production_ready'])
 def test_boundaries_and_invalid_scores(self):
  self.assertTrue(review_route(.49,.5)['additional_review']);self.assertFalse(review_route(.5,.5)['additional_review'])
  for x in (float('nan'),float('inf'),-1,2):
   with self.assertRaises(ValueError):review_route(x,.5)

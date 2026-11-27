"""선별·감사 표본의 경계: 무작위 몫 반올림, 선별 중복 없음, 감사 표본 올림, Pending 제외. 합성 후보이며 모델 성능 근거가 아니다."""
import unittest
from fractions import Fraction

from harness import active_learning, audit, audit_rate
from tests.test_harness_champion_support import make_root
from tests.test_harness_silver_support import PROTECTED, al_pool, approve, cands, judge

LOOSE = {"error_priority": {"FN": 2.0, "FP": 1.0}, "stratum_scarcity": {"front": 1.0, "back": 0.5}, "threshold_width": 0.4,
         "per_group_cap": 100, "per_seller_cap": 100, "cluster_quota": 100}


class BoundaryGapTest(unittest.TestCase):
    def test_the_random_share_is_rounded_to_the_nearest_whole(self):
        for budget, share in ((3, 1), (7, 1)):  # 0.6 → 1(내림이면 0), 1.4 → 1(올림이면 2)
            res = active_learning.select(al_pool(30), PROTECTED, LOOSE, budget, 1, [])
            self.assertEqual((share, budget), (len(res["random_part_ids"]), len(res["selected"])), budget)

    def test_no_region_is_selected_twice_even_when_the_caps_would_allow_it(self):
        for seed in range(5):
            for budget in (5, 12, 40):
                ids = [s["region_id"] for s in active_learning.select(al_pool(12), PROTECTED, LOOSE, budget, seed, [])["selected"]]
                self.assertEqual((min(budget, len(ids)), len(set(ids))), (len(ids), len(ids)), (seed, budget))
        full = active_learning.select(al_pool(12), PROTECTED, LOOSE, 40, 1, [])
        self.assertEqual((12, 28), (len(full["selected"]), full["shortfall"]))

    def test_the_audit_sample_size_is_rounded_up(self):
        ids = ["id%02d" % i for i in range(11)]
        self.assertEqual(2, len(audit_rate.sample_ids(ids, Fraction(1, 10), 1)))  # 1.1 → 2(내림·반올림이면 1)
        self.assertEqual(3, len(audit_rate.sample_ids(ids, Fraction(1, 5), 1)))  # 2.2 → 3

    def test_the_audit_sample_is_drawn_from_silver_labels_only(self):
        root = make_root(self)
        policy = approve(root)
        silver = judge(root, "b1", policy, cands(3, prefix="s"))["silver"]
        pending = judge(root, "b1", policy, cands(9, prefix="p", uncertain=True))["pending"]
        self.assertEqual((3, 9), (len(silver), len(pending)))
        plan = audit.plan_audit(root, 3.0, "b1", seed=1, schedule={"initial": 1, "floor": 1, "initial_rounds": 1})["plan"]
        self.assertEqual((3, sorted(silver)), (plan["n_silver"], plan["sample_ids"]))


if __name__ == "__main__":
    unittest.main()

"""능동 학습 선별: 봉인·보정 제외, 상한, seed 재현, 무작위 20% 표시, 정책 범위 라우팅, 점수 순서. 합성 후보이며 모델 성능 근거가 아니다."""
import unittest

from harness import active_learning, silver_policy
from tests.test_harness_silver_support import al_pool

CONFIG = {"error_priority": {"FN": 2.0, "FP": 1.0}, "stratum_scarcity": {"front": 1.0, "back": 0.5}, "threshold_width": 0.4,
          "per_group_cap": 1, "per_seller_cap": 4, "cluster_quota": 6}
OPEN = {"sealed": {"image_shas": [], "group_ids": []}, "calibration": {"image_shas": [], "group_ids": []}}


class ActiveLearningTest(unittest.TestCase):
    def setUp(self):
        self.pool = al_pool(60)

    def test_sealed_and_calibration_groups_are_never_selected(self):
        protected = {"sealed": {"image_shas": ["sha000", "sha001", "sha010"], "group_ids": ["g020", "g021"]},
                     "calibration": {"image_shas": ["sha030"], "group_ids": ["g015", "g016"]}}
        banned_sha, banned_group = {"sha000", "sha001", "sha010", "sha030"}, {"g020", "g021", "g015", "g016"}
        for seed in range(6):
            for budget in (5, 20, 60):
                res = active_learning.select(self.pool, protected, CONFIG, budget, seed, [])
                for item in res["selected"]:
                    self.assertNotIn(item["image_sha"], banned_sha)
                    self.assertNotIn(item["group_id"], banned_group)
        # g020·g021·g015·g016에 속한 모든 사진(SHA가 목록에 없는 것 포함)과 목록의 SHA가 빠졌고 개수가 맞다
        expected = sum(1 for i in self.pool if i["image_sha"] in banned_sha or i["group_id"] in banned_group)
        self.assertEqual(expected, res["excluded"]["sealed"] + res["excluded"]["calibration"])
        self.assertEqual(len(self.pool) - expected, res["n_eligible"])
        with self.assertRaises(active_learning.ActiveLearningError):  # 제외 목록이 없으면 선별하지 않는다
            active_learning.select(self.pool, {"sealed": {"image_shas": [], "group_ids": []}}, CONFIG, 5, 1, [])

    def test_group_seller_and_cluster_caps_each_bind_on_their_own_and_the_shortfall_is_reported(self):
        huge = 10 ** 6
        by_id = {p["region_id"]: p for p in self.pool}
        # 다른 두 상한을 풀어 한 상한만 묶이게 한다: 그룹 30개×1, 판매자 7명×2, 군집 5개×3이 각각 선별 수의 한계다
        for field, cap, caps, most in (("group_id", 1, dict(per_group_cap=1, per_seller_cap=huge, cluster_quota=huge), 30),
                                       ("seller_id", 2, dict(per_group_cap=huge, per_seller_cap=2, cluster_quota=huge), 14),
                                       ("cluster_id", 3, dict(per_group_cap=huge, per_seller_cap=huge, cluster_quota=3), 15)):
            res = active_learning.select(self.pool, OPEN, dict(CONFIG, **caps), 40, 3, [])
            counts = {}
            for item in res["selected"]:
                value = by_id[item["region_id"]][field]
                counts[value] = counts.get(value, 0) + 1
            self.assertEqual((cap, most), (max(counts.values()), len(res["selected"])), field)
            self.assertEqual(40 - most, res["shortfall"], field)

    def test_same_seed_same_selection_and_other_seed_changes_only_the_random_part(self):
        first = active_learning.select(self.pool, OPEN, CONFIG, 10, 11, [])
        again = active_learning.select(list(reversed(self.pool)), OPEN, CONFIG, 10, 11, [])
        self.assertEqual(first, again)  # 같은 seed는 후보 입력 순서와 무관하게 같은 선별
        other = active_learning.select(self.pool, OPEN, CONFIG, 10, 12, [])
        self.assertEqual([s["region_id"] for s in first["selected"] if not s["random_part"]],
                         [s["region_id"] for s in other["selected"] if not s["random_part"]])
        self.assertNotEqual(first["random_part_ids"], other["random_part_ids"])

    def test_random_twenty_percent_is_flagged_and_sample_is_not_representative(self):
        res = active_learning.select(self.pool, OPEN, CONFIG, 10, 5, [])
        self.assertIs(False, res["representative"])
        self.assertEqual(2, len(res["random_part_ids"]))  # 10의 20%
        self.assertEqual(8, sum(1 for s in res["selected"] if not s["random_part"]))
        for item in res["selected"]:
            self.assertEqual("random" if item["random_part"] else "ranked", item["part"])
            self.assertEqual(item["part"], res["trace"][item["region_id"]]["part"])
        self.assertIn("대표 표본이 아니다", res["dev_eval_note"])

    def test_routing_by_policy_scope_and_queues_carry_no_model_fields(self):
        scopes = [{"defect_type": "corner", "stratum": "front", "label_value": "normal"}]
        res = active_learning.select(self.pool, OPEN, CONFIG, 20, 2, scopes)
        info = {p["region_id"]: p for p in self.pool}
        self.assertTrue(res["silver_queue"] and res["human_queue"])
        for item in res["silver_queue"]:
            self.assertEqual(("corner", "front"), (info[item["region_id"]]["defect_type"], info[item["region_id"]]["stratum"]))
        for item in res["human_queue"]:
            self.assertNotEqual(("corner", "front"), (info[item["region_id"]]["defect_type"], info[item["region_id"]]["stratum"]))
        self.assertEqual(len(res["selected"]), len(res["silver_queue"]) + len(res["human_queue"]))
        for item in res["selected"]:  # 앵커링 방지: 모델 점수·기대 라벨이 항목에 없고 미리 채운 입력 검사도 통과한다
            self.assertTrue({"score", "expected_label", "error_type"}.isdisjoint(item))
            silver_policy.reject_prefilled(item)
        none = active_learning.select(self.pool, OPEN, CONFIG, 20, 2, [])  # 승인된 범위가 없으면 전부 사람 큐
        self.assertEqual(([], len(none["selected"])), (none["silver_queue"], len(none["human_queue"])))

    def test_score_is_priority_times_scarcity_times_uncertainty_and_bad_input_is_refused(self):
        base = {"region_id": "x", "image_sha": "sx", "zone": "z", "group_id": "gx", "seller_id": "sx", "cluster_id": "cx",
                "defect_type": "corner", "stratum": "front", "error_type": "FN", "expected_label": "normal", "score": 0.5, "threshold": 0.5}
        self.assertAlmostEqual(2.0 * 1.0 * 1.0, active_learning.score(base, CONFIG))
        self.assertAlmostEqual(1.0 * 1.0 * 1.0, active_learning.score(dict(base, error_type="FP"), CONFIG))
        self.assertAlmostEqual(2.0 * 0.5, active_learning.score(dict(base, stratum="back"), CONFIG))
        self.assertAlmostEqual(2.0 * 0.5, active_learning.score(dict(base, score=0.7), CONFIG))  # 문턱에서 0.2 → 근접도 0.5
        far = dict(base, score=0.99)
        self.assertAlmostEqual(0.0, active_learning.score(far, CONFIG))
        self.assertAlmostEqual(2.0 * 0.8, active_learning.score(dict(far, champion_score=0.9, challenger_score=0.1), CONFIG))
        for bad in (dict(base, score=float("nan")), dict(base, error_type="??"), dict(base, group_id="")):
            with self.assertRaises(active_learning.ActiveLearningError):
                active_learning.select([bad], OPEN, CONFIG, 1, 1, [])


if __name__ == "__main__":
    unittest.main()

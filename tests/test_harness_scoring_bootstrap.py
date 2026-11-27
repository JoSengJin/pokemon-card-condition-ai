"""부트스트랩·민감도 시험. 카드 단위 재표집, 재현성, 분모 0, 라벨 잡음 뒤집기. 합성 시험이며 모델 성능 근거가 아니다."""
import random
import unittest

from harness import bootstrap
from harness.scoring import UNMEASURED
from tests.test_harness_scoring_support import clustered, make_rows, row, uneven


class Bootstrap(unittest.TestCase):
    def test_percentile_linear_interpolation(self):
        self.assertAlmostEqual(bootstrap.percentile([5, 1, 4, 2, 3], 0.10), 1.4)
        self.assertEqual((bootstrap.percentile([5, 1, 3], 0.0), bootstrap.percentile([5, 1, 3], 1.0)), (1, 5))
        self.assertEqual(bootstrap.percentile([7], 0.10), 7)
        with self.assertRaises(ValueError):
            bootstrap.percentile([], 0.10)

    def test_same_seed_same_result_row_order_irrelevant_other_seeds_close_but_not_identical(self):
        rows = uneven()
        first = bootstrap.paired_bootstrap(rows, 2000, 7)
        shuffled = list(rows)
        random.Random(3).shuffle(shuffled)
        self.assertEqual(first, bootstrap.paired_bootstrap(rows, 2000, 7))
        self.assertEqual(first, bootstrap.paired_bootstrap(shuffled, 2000, 7))
        lowers = [bootstrap.paired_bootstrap(rows, 2000, seed)["lower"] for seed in (1, 2, 3, 4, 5)]
        self.assertGreater(len(set(lowers)), 1)  # 시드가 실제로 난수를 바꾼다(시험이 공허하지 않다)
        self.assertLess(max(lowers) - min(lowers), 0.02)  # 그래도 구간 하한은 크게 흔들리지 않는다
        self.assertGreater(min(lowers), 0.5)
        flips = [bootstrap.sensitivity(rows, 0.3, 200, seed)["min_improvement"] for seed in (7, 7, 8)]
        self.assertEqual(flips[0], flips[1])
        self.assertNotEqual(flips[0], flips[2])

    def test_resampling_unit_is_the_card_not_the_zone(self):
        rows = clustered(cards=3, zones=10, improved=1)  # 개선은 카드 1장에 몰려 있다
        by_card = bootstrap.paired_bootstrap(rows, 2000, 0)
        by_zone = bootstrap.paired_bootstrap([dict(r, card_group=r["id"]) for r in rows], 2000, 0)  # 구역을 독립으로 취급
        self.assertEqual((by_card["n_cards"], by_zone["n_cards"]), (3, 30))
        self.assertAlmostEqual(by_card["point"], by_zone["point"])  # 점추정은 같다
        self.assertLessEqual(by_card["lower"], 0)  # 카드 3장이면 개선을 증명 못 한다
        self.assertGreater(by_zone["lower"], 0.15)  # 구역 독립으로 잘못 세면 증명된 것처럼 보인다

    def test_fewer_cards_widen_the_interval_for_the_same_pooled_rates(self):
        lowers = [bootstrap.paired_bootstrap(clustered(cards, 30 // cards, cards // 3), 2000, 0)["lower"] for cards in (3, 6, 30)]
        self.assertLessEqual(lowers[0], 0)
        self.assertLess(lowers[0], lowers[1])
        self.assertLess(lowers[1], lowers[2])

    def test_no_defect_rows_is_unmeasured_not_zero(self):
        normal_only = [row("n1", "normal"), row("p1", "pending", "defect", "normal")]
        result = bootstrap.paired_bootstrap(normal_only, 100, 0)
        self.assertEqual((result["point"], result["lower"], result["valid_replicates"]), (UNMEASURED, UNMEASURED, 0))
        self.assertEqual(bootstrap.sensitivity(normal_only, 0.3, 20, 0)["min_improvement"], UNMEASURED)


class Sensitivity(unittest.TestCase):
    ROWS = [row("r1", "defect", "normal", "defect", uncertain=True), row("r2", "defect", "normal", "defect", uncertain=True),
            row("r3", "defect", "defect", "normal"), row("r4", "defect", "defect", "defect"), row("r5", "pending", uncertain=True)]

    def test_flip_noise_extremes_decide_whether_direction_survives(self):
        none = bootstrap.sensitivity(self.ROWS, 0.0, 50, 0)  # 잡음 0: 개선 (2-1)/4가 매번 유지
        self.assertEqual((none["fraction"], none["min_improvement"], none["n_uncertain"]), (1.0, 0.25, 3))
        every = bootstrap.sensitivity(self.ROWS, 1.0, 50, 0)  # 잡음 1: r1·r2가 정상으로 뒤집혀 B가 오히려 나쁘다(0-1)/2
        self.assertEqual((every["fraction"], every["min_improvement"]), (0.0, -0.5))
        tie = bootstrap.sensitivity([row("e1", "defect", "normal", "normal"), row("e2", "defect")], 0.0, 10, 0)
        self.assertEqual((tie["fraction"], tie["min_improvement"]), (0.0, 0.0))  # 개선량 0은 방향 유지가 아니다

    def test_flip_swaps_both_ways_only_uncertain_and_never_pending(self):
        rows = [row("a", "defect", uncertain=True), row("b", "normal", uncertain=True), row("c", "defect"),
                row("d", "pending", uncertain=True)]
        self.assertEqual(bootstrap.flip_truths(rows, 1.0, random.Random(0)), ["normal", "defect", "defect", "pending"])
        self.assertEqual(bootstrap.flip_truths(rows, 0.0, random.Random(0)), ["defect", "normal", "defect", "pending"])


if __name__ == "__main__":
    unittest.main()

"""승격 판정의 사전 등록 관문 시험: 결함 카드 수, 버린 재표집 비율, 공허한 민감도, eval_tier·stratum.
합성 시험이며 모델 성능 근거가 아니다. 기준값은 시험용 값이다."""
import unittest

from harness import promotion
from tests.test_harness_scoring_support import codes, make_rows, row

FA = {"fa": range(90, 100)}
BASE = dict(miss=range(0, 40), **FA)
GOOD = dict(miss=range(0, 10), **FA)
SETTING = dict(noise_rate=0.1, direction_min_fraction=0.9, min_defect_cards=10, min_valid_fraction=0.9)


class Gates(unittest.TestCase):
    def test_one_or_two_defect_cards_cannot_pass_even_though_resampling_has_zero_variance(self):
        for defect_cards in (1, 2):  # 모두 같은 방향이라 재표집 값이 전부 같다 → 하한 = 점추정 > 0
            rows = [row("d%d_%d" % (c, z), "defect", "normal", "defect", card="hot%d" % c, uncertain=True)
                    for c in range(defect_cards) for z in range(3)]
            rows += [row("n%d_%d" % (c, z), "normal", card="cool%d" % c) for c in range(50) for z in range(2)]
            result = promotion.evaluate(rows, **SETTING)
            self.assertGreater(result["bootstrap"]["lower"], 0)
            self.assertEqual(result["bootstrap"]["defect_cards"], defect_cards)
            self.assertEqual(result["verdict"], "미달")
            self.assertIn("bootstrap_too_few_cards", codes(result))
        rows = make_rows(BASE, GOOD, uncertain=range(0, 5))  # 결함 카드 100장
        self.assertEqual(promotion.evaluate(rows, **dict(SETTING, min_defect_cards=100))["verdict"], "통과")  # 경계: 같으면 통과
        self.assertIn("bootstrap_too_few_cards", codes(promotion.evaluate(rows, **dict(SETTING, min_defect_cards=101))))

    def test_discarded_replicate_fraction_boundary_is_inclusive(self):
        rows = [row("d%d" % c, "defect", "normal", "defect", card="g%d" % c, uncertain=True) for c in range(2)]
        rows += [row("n%d" % c, "normal", card="g%d" % c) for c in range(10)]  # 결함 카드 2/10장 → 재표집의 약 11%가 결함 없음
        setting = dict(SETTING, min_defect_cards=2)
        boot = promotion.evaluate(rows, **dict(setting, min_valid_fraction=0.5))["bootstrap"]
        kept = boot["valid_replicates"] / boot["replicates"]
        self.assertTrue(0.85 < kept < 0.95)
        self.assertNotIn("bootstrap_too_many_discarded", codes(promotion.evaluate(rows, **dict(setting, min_valid_fraction=kept))))
        over = promotion.evaluate(rows, **dict(setting, min_valid_fraction=kept + 0.001))
        self.assertIn("bootstrap_too_many_discarded", codes(over))
        self.assertEqual(over["verdict"], "미달")

    def test_no_uncertain_rows_means_sensitivity_was_not_evaluated_and_cannot_pass(self):
        rows = make_rows(BASE, GOOD)  # 불확실 표시 없음: 민감도는 아무 일도 하지 않고 fraction=1.0
        result = promotion.evaluate(rows, **SETTING)
        self.assertEqual((result["sensitivity"]["n_uncertain"], result["sensitivity"]["fraction"]), (0, 1.0))
        self.assertEqual((result["verdict"], codes(result)), ("미달", ["sensitivity_vacuous"]))
        flagged_pending = [dict(r, truth="pending", uncertain=True) if r["id"] == "c000z0" else r for r in make_rows(BASE, GOOD)]
        self.assertEqual(promotion.evaluate(flagged_pending, **SETTING)["sensitivity"]["n_uncertain"], 0)  # pending 표시는 뒤집을 수 없다
        self.assertEqual(promotion.evaluate(make_rows(BASE, GOOD, uncertain=range(0, 5)), **SETTING)["verdict"], "통과")

    def test_eval_tier_rejects_sealed_and_overlap_while_stratum_drives_the_abstain_cap(self):
        rows = make_rows(BASE, GOOD, uncertain=range(0, 5))
        sealed = [dict(r, eval_tier="sealed") if r["card_group"] == "card099" else r for r in rows]
        with self.assertRaisesRegex(ValueError, "sealed"):
            promotion.evaluate(sealed, **SETTING)  # 봉인 행은 확증 단계 몫
        calib = [dict(r, eval_tier="calib") if r["card_group"] == "card099" else r for r in rows]
        self.assertEqual(promotion.evaluate(calib, **SETTING)["inputs"]["eval_tiers"], ["calib", "dev"])
        with self.assertRaisesRegex(ValueError, "card099"):  # 같은 카드가 dev와 calib에 걸치면 거절
            promotion.evaluate([dict(r, eval_tier="calib") if r["id"] == "c099z0" else r for r in rows], **SETTING)
        for bad in (dict(eval_tier="test"), dict(eval_tier=None), dict(stratum=""), dict(stratum=3)):
            with self.assertRaises(ValueError, msg=str(bad)):
                promotion.evaluate([dict(rows[0], **bad)] + rows[1:], **SETTING)
        one_tier = promotion.evaluate(make_rows(BASE, dict(abs_defect=range(0, 40), **FA), uncertain=range(0, 5)), **SETTING)
        self.assertEqual(one_tier["inputs"]["eval_tiers"], ["dev"])  # 층은 하나인데 stratum 둘(front/back)이 각각 상한을 넘는다
        self.assertEqual(sorted(v["stratum"] for v in one_tier["abstain_cap"]["violations"]), ["back", "front"])


if __name__ == "__main__":
    unittest.main()

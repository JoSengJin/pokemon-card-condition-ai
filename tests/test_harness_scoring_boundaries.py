"""승격 판정의 경계·보고 시험: 하한 백분위 0.10, 오탐 Δ 경계, 최악값 비사용, 분모 소멸 시행, 보류 몫 분리 보고.
합성 시험이며 모델 성능 근거가 아니다. 기준값은 시험용 값이다."""
import unittest

from harness import bootstrap, promotion
from tests.test_harness_scoring_support import clustered, codes, make_rows, row

FA = {"fa": range(90, 100)}
BASE = dict(miss=range(0, 40), **FA)
SETTING = dict(noise_rate=0.1, direction_min_fraction=0.9, min_defect_cards=5, min_valid_fraction=0.9)


class Boundaries(unittest.TestCase):
    def test_lower_bound_is_exactly_the_tenth_percentile(self):
        # 카드 12장 중 4장만 개선: 개선 카드 수 k ~ Bin(12, 1/3). 5번째 백분위는 k=1, 10번째는 k=2, 20번째는 k=3에 놓인다.
        rows = [dict(r, uncertain=r["card_group"] not in ("card0", "card1", "card2", "card3")) for r in clustered(12, 1, 4)]
        rows += [row("n%d" % c, "normal", card="card%d" % c) for c in range(12)]
        result = promotion.evaluate(rows, **SETTING)
        self.assertEqual((result["bootstrap"]["quantile"], result["config"]["quantile"]), (0.10, 0.10))
        self.assertAlmostEqual(result["bootstrap"]["lower"], 2 / 12)
        self.assertEqual(result["verdict"], "통과")
        self.assertEqual([bootstrap.paired_bootstrap(rows, 2000, 0, q)["lower"] for q in (0.05, 0.20)], [1 / 12, 3 / 12])

    def test_false_alarm_difference_exactly_delta_passes_and_just_above_fails(self):
        cand = dict(miss=range(0, 10), fa=range(85, 100))  # 정상 구역 오탐 10% → 15%: 차이 정확히 Δ=0.05
        result = promotion.evaluate(make_rows(BASE, cand, uncertain=range(0, 5)), min_defect_cards=10, **{
            k: v for k, v in SETTING.items() if k != "min_defect_cards"})
        self.assertAlmostEqual(result["candidate"]["false_alarm"]["rate"] - result["baseline"]["false_alarm"]["rate"], 0.05)
        self.assertEqual((result["verdict"], result["reasons"]), ("통과", []))
        over = promotion.evaluate(make_rows(BASE, dict(miss=range(0, 10), fa=range(84, 100)), uncertain=range(0, 5)),
                                  **dict(SETTING, min_defect_cards=10))
        self.assertEqual(codes(over), ["false_alarm_not_noninferior"])

    def test_worst_trial_below_zero_is_reported_but_does_not_decide_when_the_fraction_is_met(self):
        a, b = dict(miss=range(0, 20), **FA), dict(miss=range(20, 30), **FA)  # 순개선 +10%p, 개선이 전부 불확실 구역
        rows = make_rows(a, b, uncertain=range(0, 20))
        kept = promotion.evaluate(rows, **dict(SETTING, noise_rate=0.4, direction_min_fraction=0.5, min_defect_cards=10))
        self.assertLess(kept["sensitivity"]["min_improvement"], 0)  # 어떤 시행에서는 방향이 뒤집힌다
        self.assertGreaterEqual(kept["sensitivity"]["fraction"], 0.5)
        self.assertEqual((kept["verdict"], kept["reasons"]), ("통과", []))  # 최악값은 보고만 한다
        vanished = bootstrap.sensitivity([row("u", "defect", "normal", "defect", uncertain=True)], 0.5, 400, 0)
        self.assertGreater(vanished["unmeasured_trials"], 100)  # 결함 구역이 사라진 시행
        self.assertEqual(vanished["fraction"], vanished["maintained"] / 400)  # 분모는 전체 시행 수(빠진 시행은 유지 못 한 것)
        self.assertLess(vanished["fraction"], 0.6)

    def test_abstain_share_of_the_gain_is_reported_separately_and_does_not_decide(self):
        cand = dict(abs_defect=range(0, 4), abs_normal=range(0, 4), miss=range(4, 10), **FA)  # 카드 0~3은 보류, 10~39는 정답으로 전환
        mixed = promotion.evaluate(make_rows(BASE, cand, uncertain=range(0, 5)), **dict(SETTING, min_defect_cards=10))
        split = mixed["improvement_split"]
        self.assertEqual([split[k]["num"] for k in ("improvement_from_abstain_zones", "improvement_from_correct_zones", "worsened_zones")], [8, 60, 0])
        self.assertEqual(split["defect_n"], 200)
        self.assertAlmostEqual(split["improvement_from_abstain_zones"]["rate"], 0.04)
        self.assertAlmostEqual(split["improvement_from_correct_zones"]["rate"], 0.30)
        self.assertEqual(mixed["verdict"], "통과")  # 보고만 하고 탈락 사유로 쓰지 않는다
        worse = dict(cand, miss=list(range(4, 10)) + [90, 91, 92])  # B만 새로 놓치는 카드 3장(구역 6개)
        net = promotion.evaluate(make_rows(BASE, worse, uncertain=range(0, 5)), **dict(SETTING, min_defect_cards=10))
        self.assertEqual(net["improvement_split"]["worsened_zones"]["num"], 6)
        gain = sum(net["improvement_split"][k]["rate"] for k in ("improvement_from_abstain_zones", "improvement_from_correct_zones"))
        self.assertAlmostEqual(gain - net["improvement_split"]["worsened_zones"]["rate"], net["bootstrap"]["point"])
        only_abstain = promotion.evaluate(make_rows(BASE, dict(abs_defect=range(0, 10), miss=range(10, 40), **FA), uncertain=range(0, 5)),
                                          **dict(SETTING, min_defect_cards=10))  # 개선이 전부 보류에서 나온다
        split = only_abstain["improvement_split"]
        self.assertEqual((split["improvement_from_correct_zones"]["num"], split["abstain_share_of_gross_gain"]["rate"]), (0, 1.0))
        self.assertAlmostEqual(only_abstain["bootstrap"]["point"], 0.10)


if __name__ == "__main__":
    unittest.main()

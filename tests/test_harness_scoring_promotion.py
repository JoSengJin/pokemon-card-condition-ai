"""승격 판정 시험(합성 후보). 합성 시험이며 모델 성능 근거가 아니다. 기준값(noise_rate·direction_min_fraction)은 시험용 값이다."""
import json
import random
import unittest

from harness import promotion
from tests.test_harness_scoring_support import clustered, codes, make_rows, row

FA = {"fa": range(90, 100)}  # 두 모델 모두 정상 구역 10%를 오탐
BASE = dict(miss=range(0, 40), **FA)  # 기준 A: 결함 구역 40% 누락
SETTING = dict(noise_rate=0.1, direction_min_fraction=0.9)


class Promotion(unittest.TestCase):
    def test_large_genuine_improvement_with_enough_cards_passes_but_not_on_three_cards(self):
        result = promotion.evaluate(make_rows(BASE, dict(miss=range(0, 10), **FA), uncertain=range(0, 5)), **SETTING)
        self.assertEqual((result["verdict"], result["reasons"]), ("통과", []))
        self.assertEqual((result["baseline"]["miss"]["rate"], result["candidate"]["miss"]["rate"]), (0.4, 0.1))
        self.assertGreater(result["bootstrap"]["lower"], 0.2)
        self.assertEqual((result["candidate"]["coverage"]["rate"], result["inputs"]["n_cards"]), (1.0, 100))
        few = clustered(3, 10, 1) + [row("n%d" % c, "normal", card="card%d" % c) for c in range(3)]  # 점추정 +33%p, 카드 3장
        small = promotion.evaluate(few, **SETTING)
        self.assertAlmostEqual(small["bootstrap"]["point"], 1 / 3)
        self.assertEqual((small["verdict"], codes(small)), ("미달", ["bootstrap_lower_not_positive"]))

    def test_abstaining_on_every_normal_zone_is_rejected_by_false_alarm_and_cap(self):
        cand = dict(miss=range(0, 10), abs_normal=range(100), **FA)  # 누락은 줄었지만 정상을 전부 보류
        result = promotion.evaluate(make_rows(BASE, cand), **SETTING)
        self.assertEqual(result["verdict"], "미달")
        self.assertEqual(result["candidate"]["false_alarm"]["rate"], 1.0)  # 보류는 오탐으로 센다
        self.assertEqual(sorted(codes(result)), ["abstain_cap", "abstain_cap", "false_alarm_not_noninferior"])

    def test_abstaining_only_on_defect_zones_to_cut_misses_is_rejected_by_abstain_cap_alone(self):
        result = promotion.evaluate(make_rows(BASE, dict(abs_defect=range(0, 40), **FA)), **SETTING)  # 누락 40% → 0%
        self.assertEqual(result["candidate"]["miss"]["rate"], 0.0)
        self.assertGreater(result["bootstrap"]["lower"], 0.3)  # 개선·민감도·오탐은 모두 좋아 보인다
        self.assertEqual(result["sensitivity"]["fraction"], 1.0)
        self.assertEqual(codes(result), ["abstain_cap", "abstain_cap"])  # 층(front·back)마다 20% > 0%+5%p
        self.assertEqual(sorted(v["layer"] for v in result["abstain_cap"]["violations"]), ["back", "front"])

    def test_small_gain_that_label_noise_erases_is_not_promoted(self):
        a, b = dict(miss=range(0, 20), **FA), dict(miss=range(20, 30), **FA)  # 순개선 +10%p
        fragile = make_rows(a, b, uncertain=range(0, 20))  # 개선이 전부 불확실한 구역에서 나온다
        settings = dict(noise_rate=0.4, direction_min_fraction=0.95)
        result = promotion.evaluate(fragile, **settings)
        self.assertGreater(result["bootstrap"]["lower"], 0)  # 부트스트랩만으로는 통과할 개선이다
        self.assertLess(result["sensitivity"]["fraction"], 0.95)
        self.assertLess(result["sensitivity"]["min_improvement"], 0)  # 보고만 한다
        self.assertEqual((result["verdict"], codes(result)), ("미달", ["direction_unstable"]))
        control = promotion.evaluate(make_rows(a, b), **settings)  # 같은 개선, 불확실 구역 없음
        self.assertEqual((control["verdict"], control["sensitivity"]["fraction"]), ("통과", 1.0))

    def test_zero_denominators_are_unmeasured_and_never_pass(self):
        only_normal = [row("n%d" % i, "normal", card="g%d" % i) for i in range(10)]
        result = promotion.evaluate(only_normal, **SETTING)
        self.assertEqual((result["verdict"], result["baseline"]["miss"]["rate"]), ("미달", "미측정"))
        self.assertIn("bootstrap_unmeasured", codes(result))
        only_defect = [row("d%d" % i, "defect", "normal", "defect", card="g%d" % i) for i in range(30)]
        result = promotion.evaluate(only_defect, **SETTING)  # 큰 개선이 있어도 오탐을 못 재면 통과하지 않는다
        self.assertGreater(result["bootstrap"]["lower"], 0)
        self.assertEqual((result["verdict"], codes(result)), ("미달", ["false_alarm_unmeasured"]))
        all_pending = promotion.evaluate([row("p1", "pending")], **SETTING)
        self.assertEqual(all_pending["verdict"], "미달")
        self.assertIn("abstain_unmeasured", codes(all_pending))

    def test_inputs_are_validated_and_preregistered_values_are_required(self):
        rows = make_rows(BASE, BASE, cards=10)
        with self.assertRaises(TypeError):  # 기본값 없음: 코드가 정하지 않는다
            promotion.evaluate(rows, noise_rate=0.1)
        with self.assertRaises(TypeError):
            promotion.evaluate(rows, direction_min_fraction=0.9)
        for bad in (dict(noise_rate=-0.1), dict(noise_rate=1.5), dict(direction_min_fraction=2), dict(delta=-1),
                    dict(replicates=0), dict(trials=0), dict(noise_rate=float("nan"))):
            with self.assertRaises(ValueError):
                promotion.evaluate(rows, **dict(SETTING, **bad))
        clash = [dict(r, layer="sealed" if r["id"].endswith("z0") else r["layer"]) for r in rows]
        with self.assertRaisesRegex(ValueError, "여러 층"):
            promotion.evaluate(clash, **SETTING)  # 같은 카드가 층 사이에 걸치면 판정하지 않는다

    def test_result_records_inputs_config_and_seed_and_is_reproducible(self):
        rows = make_rows(BASE, dict(miss=range(0, 10), **FA), uncertain=range(0, 5))
        shuffled = list(rows)
        random.Random(9).shuffle(shuffled)
        first = promotion.evaluate(rows, seed=11, **SETTING)
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(promotion.evaluate(shuffled, seed=11, **SETTING), sort_keys=True))
        self.assertEqual((first["config"]["seed"], first["config"]["replicates"], first["config"]["trials"]), (11, 2000, 1000))
        self.assertEqual((first["config"]["noise_rate"], first["config"]["direction_min_fraction"], first["config"]["delta"]),
                         (0.1, 0.9, 0.05))
        self.assertEqual((first["inputs"]["n_rows"], len(first["inputs"]["rows_sha256"])), (400, 64))
        changed = [dict(r) for r in rows]
        changed[0]["pred_b"] = "abstain"
        self.assertNotEqual(first["inputs"]["rows_sha256"], promotion.evaluate(changed, seed=11, **SETTING)["inputs"]["rows_sha256"])
        others = [promotion.evaluate(rows, seed=s, **SETTING) for s in (1, 2, 3)]
        self.assertEqual({o["verdict"] for o in others}, {"통과"})
        lowers = [o["bootstrap"]["lower"] for o in others]
        self.assertLess(max(lowers) - min(lowers), 0.05)


if __name__ == "__main__":
    unittest.main()

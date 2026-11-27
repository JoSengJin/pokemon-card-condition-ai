"""채점 집계 시험: 보류=경보, pending 제외, 분모 0 미측정, 층별 보류율, 위험-Coverage, 상한, 층 사이 카드 중복.
합성 시험이며 모델 성능 근거가 아니다."""
import unittest

from harness import scoring
from harness.scoring import UNMEASURED
from harness.scoring_rows import check_group_overlap, validate_rows
from tests.test_harness_scoring_support import row


class AbstainCounting(unittest.TestCase):
    def test_abstain_on_defect_is_alert_not_miss(self):
        rows = [row("d1", "defect", "abstain"), row("d2", "defect", "normal"), row("d3", "defect", "defect")]
        rep = scoring.report(rows, "pred_a")
        self.assertEqual((rep["miss"]["num"], rep["miss"]["den"]), (1, 3))  # 보류한 d1은 누락이 아니다
        self.assertAlmostEqual(rep["miss"]["rate"], 1 / 3)
        self.assertEqual(scoring.error_kind("defect", "abstain"), "hit")

    def test_abstain_on_normal_is_false_alarm(self):
        rows = [row("n1", "normal", "abstain"), row("n2", "normal", "defect"), row("n3", "normal", "normal")]
        rep = scoring.report(rows, "pred_a")
        self.assertEqual((rep["false_alarm"]["num"], rep["false_alarm"]["den"]), (2, 3))
        self.assertEqual(scoring.error_kind("normal", "abstain"), "false_alarm")
        self.assertEqual(scoring.error_kind("normal", "normal"), "correct")

    def test_pending_is_outside_every_denominator_and_zero_denominator_is_unmeasured(self):
        rows = [row("p1", "pending", "abstain"), row("p2", "pending", "defect"), row("n1", "normal", "normal")]
        rep = scoring.report(rows, "pred_a")
        self.assertEqual((rep["gold_n"], rep["pending_n"], rep["defect_n"]), (1, 2, 0))
        self.assertEqual(rep["miss"], {"num": 0, "den": 0, "rate": UNMEASURED})  # 결함 구역 0 → 숫자 없음
        self.assertEqual(rep["false_alarm"]["rate"], 0.0)
        empty = scoring.report([row("p1", "pending")], "pred_a")
        self.assertEqual([empty[k]["rate"] for k in ("miss", "false_alarm", "coverage")], [UNMEASURED] * 3)
        self.assertEqual(empty["abstain_by_stratum"]["S1"]["rate"], UNMEASURED)

    def test_coverage_and_stratum_abstain_rates_use_gold_denominator(self):
        rows = [row("a1", "defect", "abstain", stratum="L1"), row("a2", "normal", "normal", stratum="L1"),
                row("a3", "normal", "defect", stratum="L1"), row("a4", "defect", "defect", stratum="L1"),
                row("b1", "defect", "defect", stratum="L2"), row("b2", "normal", "normal", stratum="L2"),
                row("p1", "pending", "abstain", stratum="L2")]
        rep = scoring.report(rows, "pred_a")
        self.assertEqual((rep["coverage"]["num"], rep["coverage"]["den"]), (5, 6))  # pending 보류는 제외
        self.assertEqual(rep["abstain_by_stratum"]["L1"]["rate"], 0.25)
        self.assertEqual(rep["abstain_by_stratum"]["L2"], {"num": 0, "den": 2, "rate": 0.0})


class CurveAndCap(unittest.TestCase):
    def test_risk_coverage_curve_groups_ties_and_needs_scores(self):
        rows = [row("r1", "defect", "defect", score=0.9), row("r2", "normal", "normal", score=0.8),
                row("r3", "defect", "normal", score=0.8), row("r4", "normal", "defect", score=0.3),
                row("r5", "defect", "abstain"), row("r6", "pending", "defect", score=0.99)]
        curve = scoring.report(rows, "pred_a")["risk_coverage"]
        self.assertEqual([p["kept"] for p in curve], [1, 3, 4])  # 같은 점수 0.8은 한 점
        for point, (cov, risk) in zip(curve, [(0.2, 0.0), (0.6, 1 / 3), (0.8, 0.5)]):
            self.assertAlmostEqual(point["coverage"], cov)
            self.assertAlmostEqual(point["risk"], risk)
        no_score = [dict(r) for r in rows]
        del no_score[1]["score"]  # 판정한 구역에 점수가 빠지면 곡선을 만들지 않는다
        self.assertEqual(scoring.report(no_score, "pred_a")["risk_coverage"], UNMEASURED)
        self.assertEqual(scoring.report([row("x", "defect")], "pred_a")["risk_coverage"], UNMEASURED)

    def test_abstain_cap_is_relative_plus_5pp_and_absolute_20pp_per_stratum(self):
        base = {"abstain_by_stratum": {k: {"rate": v} for k, v in dict(a=0.00, b=0.10, c=0.18, d=UNMEASURED, e=0.25).items()}}
        cand = {"abstain_by_stratum": {k: {"rate": v} for k, v in dict(a=0.04, b=0.16, c=0.22, d=0.0, e=0.25, z=0.01).items()}}  # z는 기준에 없는 층
        cap = scoring.abstain_cap(base, cand)
        self.assertEqual([v["stratum"] for v in cap["violations"]], ["b", "c", "e"])  # b: 0.16>0.15, c: 0.22>0.20(절대), e: 기준이 이미 20% 넘으면 같아도 위반(D-6 문구대로)
        self.assertEqual((cap["checked"], cap["unmeasured"]), (["a", "b", "c", "e"], ["d", "z"]))
        ok = scoring.abstain_cap({"abstain_by_stratum": {"a": {"rate": 0.10}}}, {"abstain_by_stratum": {"a": {"rate": 0.15}}})  # 경계(+5%p 정확히)는 통과
        self.assertEqual((ok["violations"], ok["checked"]), ([], ["a"]))

    def test_group_overlap_across_eval_tiers_is_an_error_and_bad_rows_are_rejected(self):
        check_group_overlap([row("a", "defect", card="g1", tier="dev"), row("b", "normal", card="g1", tier="dev"),
                             row("c", "defect", card="g2", tier="sealed")])
        with self.assertRaisesRegex(ValueError, "g1"):
            check_group_overlap([row("a", "defect", card="g1", tier="dev"), row("b", "defect", card="g1", tier="sealed")])
        for bad in ([], [row("a", "good")], [row("a", "defect"), row("a", "normal")],
                    [row("a", "defect", score=True)], [row("a", "defect", pred_b="maybe")],
                    [row("a", "defect", uncertain="yes")], [row("a", "defect", score=float("nan"))]):
            with self.assertRaises(ValueError):
                validate_rows(bad)


if __name__ == "__main__":
    unittest.main()

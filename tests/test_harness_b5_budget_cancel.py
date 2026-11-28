"""B5-4: 실험 예산 차감 취소(사용자 결정 3, 2026-11-28). 실행되지 않았음이 객관적으로 확인된 경우(어댑터 not_started)에만 그 시도가 새로 한 차감을
취소한다. 장부 이벤트는 cancel 하나만 더했다. 여기서는 취소 규칙·다른 주 비우기·같은 키 취소·재차감 반복을 본다(위조·kill·병렬·반쯤 쓴 줄은
test_harness_b5_budget_cancel_abuse).
합성 root만 쓴다(실제 실험·모델 호출 없음).
"""
import calendar
import tempfile
import unittest

from harness import budget
from tests import harness_depth_kit as kit
from tests.test_harness_supervisor_kit import events

WED = calendar.timegm((2030, 1, 9, 1, 0, 0))  # 2030-W02
NEXT = WED + 7 * 86400  # 2030-W03


def _week(root, now=WED):
    return budget.usage(root, "experiment", budget.period_of("experiment", now))


class BudgetCancelTest(unittest.TestCase):
    def test_cancel_refunds_only_its_own_charge_once_and_a_recharge_is_a_new_charge(self):
        root = tempfile.mkdtemp()
        first = budget.charge(root, "experiment", 1, WED, key="K")
        self.assertEqual((first["ok"], first["seq"]), (True, 0))
        again = budget.charge(root, "experiment", 1, WED + 1, key="K")  # 같은 논리 실험의 재개: 차감 번호 없음 = 취소할 차감이 아니다
        self.assertEqual((again.get("already"), "seq" in again), (True, False))
        for bad in [("vision_zone", "K", 0), ("experiment", "other", 0), ("experiment", "K", 7), ("experiment", "K", None),
                    ("experiment", "", 0), ("experiment", "K", True), ("experiment", None, 0)]:
            with self.subTest(bad=bad):
                self.assertFalse(budget.cancel(root, bad[0], bad[1], bad[2], WED + 2)["ok"])
        self.assertEqual(_week(root), 1)
        done = budget.cancel(root, "experiment", "K", 0, WED + 3)
        self.assertEqual((done["ok"], done["used"], _week(root)), (True, 0, 0))
        twice = budget.cancel(root, "experiment", "K", 0, WED + 4)  # kill 뒤 다시 부른 취소: 두 번 빼지 않는다
        self.assertEqual((twice["ok"], twice.get("already"), _week(root)), (True, True, 0))
        recharge = budget.charge(root, "experiment", 1, WED + 5, key="K")  # 취소된 차감은 재개 근거가 아니다: 새로 차감
        self.assertEqual((recharge["ok"], recharge.get("already"), recharge["seq"], _week(root)), (True, None, 2, 1))
        self.assertEqual([e["event"] for e in events(root, path=budget.BUDGET)], ["charge", "cancel", "charge"])
        self.assertEqual(events(root, "cancel", budget.BUDGET)[0]["data"], {"kind": "experiment", "key": "K", "charge_seq": 0,
                                                                             "period": "week:2030-W02", "amount": 1, "actor": "harness",
                                                                             "reason": "not_started"})

    def test_cancel_refunds_the_charge_week_not_the_current_week(self):
        root = tempfile.mkdtemp()
        old = [budget.charge(root, "experiment", 1, WED + i, key="old-%d" % i) for i in range(20)]
        for i in range(20):
            self.assertTrue(budget.charge(root, "experiment", 1, NEXT + i, key="new-%d" % i)["ok"])
        moved = budget.cancel(root, "experiment", "old-3", old[3]["seq"], NEXT + 30)  # 다음 주에 지난주 차감을 취소
        self.assertEqual((moved["ok"], moved["period"], moved["used"]), (True, "week:2030-W02", 19))
        self.assertEqual((_week(root), _week(root, NEXT)), (19, 20))
        over = budget.charge(root, "experiment", 1, NEXT + 31, key="new-20")  # 이번 주 한도는 그대로
        self.assertEqual((over["ok"], over["reason"]), (False, "limit"))

    def test_repeated_cancel_and_recharge_of_one_key_never_exceeds_the_limit(self):
        root = tempfile.mkdtemp()
        for i in range(19):
            budget.charge(root, "experiment", 1, WED + i, key="exp-%d" % i)
        for n in range(30):
            got = budget.charge(root, "experiment", 1, WED + 100 + 2 * n, key="K")
            self.assertEqual((got["ok"], got["used"]), (True, 20))
            self.assertTrue(budget.cancel(root, "experiment", "K", got["seq"], WED + 101 + 2 * n)["ok"])
            self.assertEqual(_week(root), 19)
        last = budget.charge(root, "experiment", 1, WED + 300, key="K")
        self.assertEqual((last["ok"], last["used"]), (True, 20))
        self.assertTrue(budget.charge(root, "experiment", 1, WED + 301, key="K").get("already"))
        self.assertEqual(budget.charge(root, "experiment", 1, WED + 302, key="exp-new")["reason"], "limit")

    def test_cancel_depth_fits_the_drain_call_site(self):
        graph = kit.call_graph()
        depth, path = kit.longest("budget.cancel", graph)
        self.assertLessEqual(depth + 2, 4, path)  # runner.main -> drain -> cancel
        self.assertLessEqual(kit.longest("budget.charge", graph)[0] + 2, 4)


if __name__ == "__main__":
    unittest.main()

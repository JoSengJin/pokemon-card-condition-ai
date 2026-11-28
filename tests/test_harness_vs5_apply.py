"""VS5 적용 단계(학습 등록 B5-7, 채점·승격 판정 B5-10) 시험. 합성 학습·평가 작업(가짜 executor)만 쓰며 모델 성능 근거가 아니다.
승격은 하지 않는다(판정 기록까지). 진입점(Supervisor) 연결은 test_harness_vs5_entry가 본다.
"""
import os
import unittest
from unittest import mock

from harness import apply_main, apply_promote, apply_train, champion, ledger, opstate, registry
from harness.jsonio import read_json
from tests import harness_vs5_kit as kit
from tests import harness_vs5_run as run


def verdicts(root):
    return ledger.events(os.path.join(root, "ledger.jsonl"), "promotion_verdict")


class ApplyPromoteTest(unittest.TestCase):
    def setUp(self):
        self.root, self.src, self.head, self.tkey, self.ekey = run.verified_pair(self)

    def test_verdict_is_recorded_once_after_the_candidate_is_applied_and_nothing_is_promoted(self):
        early = apply_promote.apply(self.root, self.ekey, 5.0)  # 학습 결과가 아직 등록되지 않았다 = 대기(판정하지 않는다)
        self.assertEqual((early["ok"], early["reason"]), (False, "candidate_not_applied"))
        self.assertEqual((verdicts(self.root), os.path.exists(os.path.join(self.root, apply_promote.VERDICTS))), ([], False))
        model = apply_train.apply(self.root, self.tkey, 6.0)["model_id"]
        first, again = apply_promote.apply(self.root, self.ekey, 7.0), apply_promote.apply(self.root, self.ekey, 8.0)
        self.assertEqual((first["ok"], first["verdict"], again["ok"], again.get("already")), (True, "통과", True, True))
        [line] = verdicts(self.root)  # 두 번 적용해도 장부 한 줄
        self.assertEqual((line["task_key"], line["model_id"], line["verdict"], line["promoted"]), (self.ekey, model, "통과", False))
        rec = read_json(os.path.join(self.root, apply_promote.VERDICTS, self.ekey + ".json"))
        self.assertEqual((rec["model_id"], rec["promoted"], rec["candidate_of"]), (model, False, self.tkey))
        self.assertEqual((rec["result"]["baseline"]["miss"]["rate"], rec["result"]["candidate"]["miss"]["rate"]), (0.4, 0.1))  # 채점 분모가 기록에 있다
        self.assertEqual((rec["result"]["baseline"]["miss"]["den"], rec["result"]["inputs"]["n_cards"]), (200, 100))
        self.assertIsNone(champion.read_current(self.root))  # 승격 실행은 하지 않는다
        self.assertEqual(registry.load(self.root)["models"][model]["grade"], "Challenger")

    def test_verdict_can_be_a_rejection_and_a_repeated_abstain_hack_is_still_rejected(self):
        root, _, _, tkey, ekey = run.verified_pair(self, variant="abstain_all")
        apply_train.apply(root, tkey, 6.0)
        done = apply_promote.apply(root, ekey, 7.0)
        self.assertEqual((done["ok"], done["verdict"]), (True, "미달"))
        self.assertIn("abstain_cap", [r["code"] for r in read_json(os.path.join(root, apply_promote.VERDICTS, ekey + ".json"))["result"]["reasons"]])

    def test_bad_contract_bad_rows_or_halted_state_record_nothing(self):
        for over in ({"candidate_of": False}, {"depends": False}, {"promotion": {"noise_rate": 0.1}},
                     {"promotion": dict(kit.SETTING, extra=1)}, {"variant": "sealed"}):
            root, _, _, tkey, ekey = run.verified_pair(self, **over)
            apply_train.apply(root, tkey, 6.0)
            done = apply_promote.apply(root, ekey, 7.0)
            self.assertFalse(done["ok"], (over, done))
            self.assertEqual((verdicts(root), os.path.exists(os.path.join(root, apply_promote.VERDICTS, ekey + ".json"))), ([], False), over)
        opstate.set_condition(self.root, opstate.USER_STOPPED, 9.0, "user", "정지")  # 결정 9(나): 정지 중에는 모든 반영 정지
        self.assertEqual([r["reason"] for r in run.apply_all(self.root)], ["halted:USER_STOPPED"] * 2)
        self.assertEqual((registry.load(self.root)["models"], verdicts(self.root)), ({}, []))

    def test_a_crash_between_the_record_and_the_ledger_line_is_repaired_without_a_second_line(self):
        apply_train.apply(self.root, self.tkey, 6.0)
        real = ledger.append
        with mock.patch.object(ledger, "append", side_effect=OSError("kill")):
            with self.assertRaises(OSError):
                apply_promote.apply(self.root, self.ekey, 7.0)
        self.assertEqual(verdicts(self.root), [])
        self.assertTrue(os.path.exists(os.path.join(self.root, apply_promote.VERDICTS, self.ekey + ".json")))
        self.assertTrue(apply_promote.apply(self.root, self.ekey, 8.0)["ok"])
        apply_promote.apply(self.root, self.ekey, 9.0)
        self.assertEqual(len(verdicts(self.root)), 1)
        self.assertIs(ledger.append, real)

    def test_pending_lists_training_before_evaluation_and_drops_applied_ones(self):
        self.assertEqual(apply_main.pending(self.root), [("train", self.tkey), ("promote", self.ekey)])
        self.assertEqual([(r["kind"], r["ok"]) for r in run.apply_all(self.root)], [("train", True), ("promote", True)])
        self.assertEqual(apply_main.pending(self.root), [])
        self.assertEqual(len(registry.load(self.root)["models"]), 1)
        self.assertEqual([v["task_key"] for v in verdicts(self.root)], [self.ekey])
        self.assertEqual(run.apply_all(self.root), [])  # 다시 돌려도 요약이 비고 아무것도 늘지 않는다
        self.assertEqual((len(registry.load(self.root)["models"]), len(verdicts(self.root))), (1, 1))


if __name__ == "__main__":
    unittest.main()

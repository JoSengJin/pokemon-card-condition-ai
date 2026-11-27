"""승격 관문과 멱등: 층·분모·봉인 판본 비교, 봉인 층, 이중 승격, 무효·가중치 누락 거절. 합성 시험이며 모델 성능 근거가 아니다."""
import os
import unittest

from harness import cas, champion, ledger, registry
from tests.test_harness_champion_support import add_model, make_root, pointer_model, read_events


class PromoteTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)

    def test_first_promotion_sets_pointer_grade_and_both_ledgers(self):
        a = add_model(self.root, "a")
        res = champion.promote(self.root, 2.0, a)
        self.assertEqual({"ok": True, "already": False, "model_id": a, "previous": None}, res)
        self.assertEqual(a, pointer_model(self.root))
        state = registry.load(self.root)
        self.assertEqual("Champion", state["models"][a]["grade"])
        self.assertEqual([a], [h["model_id"] for h in state["history"]])
        self.assertIsNone(state["pending"])
        main = read_events(self.root, "ledger.jsonl")
        self.assertEqual(["champion_promoted"], [e["event"] for e in main])
        self.assertEqual([], ledger.verify(os.path.join(self.root, "ledger.jsonl")))
        self.assertEqual([], ledger.verify(os.path.join(self.root, registry.REGISTRY)))

    def test_replacement_keeps_previous_champion_record_and_weights(self):
        a, b = add_model(self.root, "a"), add_model(self.root, "b")
        champion.promote(self.root, 2.0, a)
        pointer = os.path.join(self.root, registry.POINTER)
        inode = os.stat(pointer).st_ino
        res = champion.promote(self.root, 3.0, b)
        self.assertNotEqual(inode, os.stat(pointer).st_ino)  # 같은 파일을 덮어쓴 것이 아니라 새 파일로 교체했다
        self.assertEqual(a, res["previous"])
        state = registry.load(self.root)
        self.assertEqual(b, pointer_model(self.root))
        self.assertEqual([a, b], [h["model_id"] for h in state["history"]])
        self.assertEqual("valid", state["models"][a]["status"])  # 삭제·무효화하지 않는다
        self.assertTrue(cas.has(os.path.join(self.root, "cas"), state["models"][a]["weights_sha"]))

    def test_different_layer_denominator_or_seal_version_is_refused(self):
        a = add_model(self.root, "a")
        champion.promote(self.root, 2.0, a)
        cases = {"layer": dict(layer="dev"), "denominator": dict(denominator="defect-zones:n=119"),
                 "seal_version": dict(seal="seal-v2")}
        for field, kwargs in cases.items():
            with self.subTest(field):
                cand = add_model(self.root, "c-" + field, **kwargs)
                before = read_events(self.root)
                res = champion.promote(self.root, 3.0, cand)
                self.assertFalse(res["ok"])
                self.assertEqual("not_comparable", res["reason"])
                self.assertEqual([field], res["detail"])
                self.assertEqual(a, pointer_model(self.root))
                self.assertEqual(before, read_events(self.root))  # 거절은 아무 것도 쓰지 않는다

    def test_non_sealed_layer_cannot_become_champion(self):
        dev = add_model(self.root, "dev", layer="dev")
        res = champion.promote(self.root, 2.0, dev)
        self.assertEqual(("not_sealed", False), (res["reason"], res["ok"]))
        self.assertIsNone(pointer_model(self.root))

    def test_double_promotion_writes_nothing_the_second_time(self):
        a = add_model(self.root, "a")
        champion.promote(self.root, 2.0, a)
        events, main = read_events(self.root), read_events(self.root, "ledger.jsonl")
        again = champion.promote(self.root, 9.0, a)
        self.assertEqual({"ok": True, "already": True, "model_id": a}, again)
        self.assertEqual(events, read_events(self.root))
        self.assertEqual(main, read_events(self.root, "ledger.jsonl"))

    def test_unknown_invalidated_and_missing_weights_are_refused(self):
        a, b = add_model(self.root, "a"), add_model(self.root, "b")
        self.assertEqual("unknown_model", champion.promote(self.root, 2.0, "0" * 64)["reason"])
        ledger.append(os.path.join(self.root, registry.REGISTRY), 3.0, "invalidated", {"models": [a], "cause": "test"})
        self.assertEqual("invalidated", champion.promote(self.root, 4.0, a)["reason"])
        blob = cas.blob_path(os.path.join(self.root, "cas"), registry.load(self.root)["models"][b]["weights_sha"])
        os.unlink(blob)
        self.assertEqual("weights_missing", champion.promote(self.root, 5.0, b)["reason"])
        self.assertIsNone(pointer_model(self.root))


if __name__ == "__main__":
    unittest.main()

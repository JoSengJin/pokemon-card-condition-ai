"""포인터 대조 강화, 무효 현재 Champion·조상 무효 후보 거절, settle의 장부 보충과 임시 파일 정리, 승격 kill 뒤 계보 무효화. 합성 시험이다."""
import json
import os
import unittest

from harness import champion, ledger, lineage, registry
from tests.test_harness_champion_support import add_model, kill_at, make_root, pointer_model, read_events


class GuardsTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.a, self.b, self.c = [add_model(self.root, n) for n in "abc"]
        self.pointer = os.path.join(self.root, registry.POINTER)

    def temp_files(self):
        return [n for _, _, names in os.walk(os.path.join(self.root, "models")) for n in names if ".tmp." in n]

    def test_tampered_stale_or_missing_pointer_is_refused(self):
        champion.promote(self.root, 2.0, self.a)
        with open(self.pointer, "r", encoding="utf-8") as handle:
            old = json.load(handle)
        champion.promote(self.root, 3.0, self.b)
        with open(self.pointer, "r", encoding="utf-8") as handle:
            new = json.load(handle)
        registered_hash = read_events(self.root)[0]["hash"]
        cases = {"other_registered_model": dict(new, model_id=self.c), "registered_event_hash": dict(new, intent_hash=registered_hash),
                 "stale_pointer_file": old, "other_models_intent": dict(new, intent_hash=old["intent_hash"]),
                 "unknown_model": dict(new, model_id="f" * 64), "weights_sha": dict(new, weights_sha="0" * 64), "not_an_object": [1]}
        for name, content in cases.items():
            with self.subTest(name):
                with open(self.pointer, "w", encoding="utf-8") as handle:
                    json.dump(content, handle)
                with self.assertRaises(champion.ChampionError):
                    champion.read_current(self.root)
        with open(self.pointer, "w", encoding="utf-8") as handle:
            json.dump(new, handle)
        self.assertEqual(self.b, champion.read_current(self.root)["model_id"])
        os.unlink(self.pointer)  # 승격 기록이 있는데 포인터가 사라짐
        with self.assertRaises(champion.ChampionError):
            champion.read_current(self.root)

    def test_invalid_current_champion_cannot_be_reconfirmed_by_promote(self):
        champion.promote(self.root, 2.0, self.a)
        res = champion.restore_last_verified(self.root, 3.0, regression="r", model_id=self.a)  # 돌아갈 곳이 없어 무효인 채 남는다
        self.assertEqual("no_verified_champion", res["reason"])
        self.assertFalse(champion.read_current(self.root)["valid"])
        again = champion.promote(self.root, 4.0, self.a)
        self.assertEqual((False, "invalidated"), (again["ok"], again["reason"]))  # already=True로 통과하지 않는다
        self.assertTrue(champion.promote(self.root, 5.0, self.b)["ok"])  # 유효한 다른 모델로의 교체는 된다
        self.assertEqual(self.b, pointer_model(self.root))

    def test_child_of_an_invalid_ancestor_is_refused_for_promotion_and_restore(self):
        child, x = add_model(self.root, "child", parent=self.a), add_model(self.root, "x")
        for i, model in enumerate((self.a, child, x)):
            self.assertTrue(champion.promote(self.root, 2.0 + i, model)["ok"])
        ledger.append(os.path.join(self.root, registry.REGISTRY), 6.0, "invalidated",
                      {"models": [self.a], "cause": "earlier regression"})  # 부모만 무효, 자식은 상태상 valid
        self.assertEqual("valid", registry.load(self.root)["models"][child]["status"])
        self.assertEqual("invalidated", champion.promote(self.root, 7.0, child)["reason"])
        res = champion.restore_last_verified(self.root, 8.0, regression="r", model_id=x)
        self.assertEqual((False, "no_verified_champion"), (res["ok"], res["reason"]))  # 자식도 부모도 후보가 아니다
        self.assertEqual(x, pointer_model(self.root))

    def test_settle_supplements_main_ledger_and_removes_leftover_temp_files(self):
        champion.promote(self.root, 2.0, self.a)
        kill_at(self, self.root, "after_replace", "promote", self.b)  # 포인터는 b, switched·주 장부 요약은 못 씀
        main = os.path.join(self.root, "ledger.jsonl")
        self.assertEqual(1, len(read_events(self.root, "ledger.jsonl")))
        self.assertTrue(champion.promote(self.root, 10.0, self.b)["already"])
        events = read_events(self.root, "ledger.jsonl")
        self.assertEqual(["champion_promoted", "champion_promoted"], [e["event"] for e in events])
        self.assertEqual((self.b, True), (events[-1]["data"]["target"], events[-1]["data"]["settled"]))
        self.assertEqual([], ledger.verify(main))
        kill_at(self, self.root, "before_replace", "promote", self.c)  # 임시 포인터 파일이 남는다
        self.assertTrue(self.temp_files())
        champion.promote(self.root, 11.0, self.c)
        self.assertEqual([], self.temp_files())
        # 포인터가 이미 같은 모델을 가리켜도(오래된 의도) 새 의도의 포인터 교체로 치지 않는다: 의도 해시로 판단한다
        reg = os.path.join(self.root, registry.REGISTRY)
        ledger.append(reg, 12.0, "switch_intent", {"target": self.c, "from": self.c, "reason": "promote"})
        before = len(registry.load(self.root)["history"])
        self.assertTrue(champion.promote(self.root, 13.0, self.c)["already"])
        self.assertEqual("switch_aborted", read_events(self.root)[-1]["event"])
        self.assertEqual(before, len(registry.load(self.root)["history"]))

    def test_lineage_call_after_a_killed_promotion_settles_first(self):
        bad = add_model(self.root, "bad", batches=["s1"])
        champion.promote(self.root, 2.0, self.a)
        kill_at(self, self.root, "after_replace", "promote", bad)  # 포인터는 bad, 의도는 짝 없이 남음
        self.assertIsNotNone(registry.load(self.root)["pending"])
        res = lineage.invalidate_lineage(self.root, 10.0, "s1")
        self.assertEqual(([bad], True), (res["invalidated"], res["restore"]["ok"]))
        state = registry.load(self.root)  # 짝 없는 의도 위에 새 의도가 쌓여 레지스트리가 깨지지 않았다
        self.assertIsNone(state["pending"])
        self.assertEqual([self.a, bad, self.a], [h["model_id"] for h in state["history"]])
        self.assertEqual((self.a, True), (pointer_model(self.root), champion.read_current(self.root)["valid"]))


if __name__ == "__main__":
    unittest.main()

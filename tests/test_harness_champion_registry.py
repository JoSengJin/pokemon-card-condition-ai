"""레지스트리: 기록 보존, 등록 멱등·충돌, 입력 거절, 해시 체인 변조·꼬리 잘림·앞뒤 안 맞는 줄 감지. 합성 시험이다."""
import hashlib
import json
import os
import unittest

from harness import cas, champion, ledger, registry
from tests.test_harness_champion_support import DENOM, add_model, make_root, read_events


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.path = os.path.join(self.root, registry.REGISTRY)

    def test_register_keeps_every_field_and_weights_in_cas(self):
        parent = add_model(self.root, "p", grade="Dev-leader")
        child = add_model(self.root, "c", batches=["s2", "s1", "s1"], parent=parent)
        rec = registry.load(self.root)["models"][child]
        self.assertEqual(["s1", "s2"], rec["silver_batches"])
        self.assertEqual(parent, rec["parent"])
        self.assertEqual(("Challenger", "valid"), (rec["grade"], rec["status"]))
        self.assertEqual({"layer": "sealed", "denominator": DENOM, "seal_version": "seal-v1", "metrics": {"miss": 0.2}}, rec["eval"])
        self.assertEqual(hashlib.sha1(b"c").hexdigest(), rec["code_sha"])
        self.assertEqual(hashlib.sha256(b"weights-c").hexdigest(), rec["weights_sha"])
        self.assertTrue(cas.has(os.path.join(self.root, "cas"), rec["data_manifest_sha"]))  # 학습 manifest도 CAS에 있다(시험 도구가 넣음)
        self.assertEqual("Dev-leader", registry.load(self.root)["models"][parent]["grade"])
        self.assertTrue(cas.has(os.path.join(self.root, "cas"), rec["weights_sha"]))

    def test_same_model_twice_is_idempotent_and_a_different_evaluation_conflicts(self):
        first = add_model(self.root, "a")
        events = read_events(self.root)
        self.assertEqual(first, add_model(self.root, "a", now=9.0))
        self.assertEqual(events, read_events(self.root))
        src = os.path.join(self.root, "incoming", "a")
        manifest = registry.load(self.root)["models"][first]["data_manifest_sha"]
        res = registry.register(self.root, 9.0, src, hashlib.sha1(b"a").hexdigest(), manifest,
                                {"lr": 0.001, "name": "a"}, {"layer": "sealed", "denominator": DENOM, "seal_version": "seal-v1",
                                                            "metrics": {"miss": 0.1}}, [])
        self.assertEqual((False, "conflict", True), (res["ok"], res["reason"], res["existing"]))
        self.assertEqual(events, read_events(self.root))

    def test_bad_inputs_are_refused_without_writing(self):
        add_model(self.root, "a")
        events = read_events(self.root)
        src = os.path.join(self.root, "incoming", "a")
        good = dict(code_sha="a" * 40, data_manifest_sha="b" * 64, config={}, silver_batches=[], parent=None, grade="Challenger",
                    eval_result={"layer": "sealed", "denominator": DENOM, "seal_version": "v1", "metrics": {}})
        bad = {"code_sha": "ABC", "data_manifest_sha": "b" * 40, "grade": "Champion",
               "eval_result": {"layer": "sealed", "denominator": DENOM, "metrics": {}},
               "silver_batches": "s1", "config": {"x": float("nan")}}
        for name, value in bad.items():
            with self.subTest(name):
                with self.assertRaises(registry.RegistryError):
                    registry.register(self.root, 2.0, src, **dict(good, **{name: value}))
        res = registry.register(self.root, 2.0, src, **dict(good, parent="f" * 64))
        self.assertEqual((False, "unknown_parent"), (res["ok"], res["reason"]))
        self.assertEqual(events, read_events(self.root))

    def test_edited_deleted_or_reordered_registry_lines_are_detected(self):
        for name in "abc":
            add_model(self.root, name)
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        edited = json.loads(lines[1])
        edited["data"]["eval"]["metrics"]["miss"] = 0.0  # 평가 수치 변조, 해시는 그대로
        variants = {"edit": [lines[0], json.dumps(edited, sort_keys=True), lines[2]],
                    "delete_middle": [lines[0], lines[2]], "reorder": [lines[1], lines[0], lines[2]]}
        for name, new in variants.items():
            with self.subTest(name):
                with open(self.path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(new) + "\n")
                with self.assertRaises(registry.RegistryError):
                    registry.load(self.root)

    def test_tail_truncation_is_detected_by_pointer_and_by_expected_tail(self):
        a, b = add_model(self.root, "a"), add_model(self.root, "b")
        champion.promote(self.root, 2.0, a)
        champion.promote(self.root, 3.0, b)
        tail = ledger.tail(self.path)
        with open(self.path, "r", encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        with open(self.path, "w", encoding="utf-8") as handle:  # 마지막 승격(의도·완료) 두 줄을 잘라냄: 체인 자체는 유효
            handle.write("\n".join(lines[:-2]) + "\n")
        self.assertIsNotNone(registry.load(self.root))
        with self.assertRaises(champion.ChampionError):  # 포인터가 가리키는 의도가 레지스트리에 없다
            champion.current(self.root, registry.load(self.root))
        with self.assertRaises(registry.RegistryError):  # 외부에 복제한 끝 해시와도 어긋남
            registry.load(self.root, expected_tail=tail)

    def test_valid_chain_with_unpaired_or_duplicate_events_is_rejected(self):
        a = add_model(self.root, "a")
        rec = {k: v for k, v in registry.load(self.root)["models"][a].items() if k not in ("status", "causes")}
        for event, data in (("switched", {"intent_hash": "0" * 64, "target": a, "from": None, "reason": "promote"}),
                            ("registered", rec)):
            with self.subTest(event):
                ledger.append(self.path, 2.0, event, data)  # 체인은 유효하지만 앞뒤가 맞지 않는 줄
                with self.assertRaises(registry.RegistryError):
                    registry.load(self.root)
                with open(self.path, "r", encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
                with open(self.path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(lines[:-1]) + "\n")


if __name__ == "__main__":
    unittest.main()

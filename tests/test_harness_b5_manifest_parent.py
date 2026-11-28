"""B5-2: 학습 manifest v2의 학습 시작 가중치(start_weights_sha)를 선언된 부모(parent)의 가중치 SHA와 대조한다(b924753 결함 ② 검사 쪽).

규칙: start_weights_sha가 None(처음부터 학습)이면 parent도 None, 값이 있으면 선언된 부모 모델의 weights_sha와 정확히 같아야 한다.
아니면 manifest_parent_mismatch(그 모델과 자손 모두 승격·부모 조회 거절). v1 manifest·키 없음은 확인 불가(manifest_mismatch).
합성 시험이다. '선언을 정직하게 채우는 쪽'(manifest를 하네스가 계약 입력으로 만든다)은 B5-7 train_manifest에서 닫는다.
"""
import unittest

from harness import champion, eligibility, registry, silver_store, withdrawal
from tests.test_harness_champion_support import add_model, make_root
from tests.test_harness_withdrawal_support import make_batch

MISMATCH, PARENT = "manifest_mismatch", "manifest_parent_mismatch"


class ManifestParentTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = make_batch(self.root, "b1")
        self.ids = sorted(e["data"]["label_id"] for e in silver_store.load(self.root)
                          if e["event"] == "silver_label" and e["data"]["batch_id"] == "b1")
        self.base = add_model(self.root, "base", batches=["b1"])
        self.base_sha = registry.load(self.root)["models"][self.base]["weights_sha"]

    def manifest(self, start, batches=("b1",)):
        return {"format": eligibility.MANIFEST_FORMAT, "silver_batches": sorted(batches),
                "silver_label_ids": self.ids if batches else [], "start_weights_sha": start}

    def test_omitted_parent_cannot_carry_a_held_lineage(self):
        withdrawal.withdraw(self.root, 2.0, self.policy, "criteria_change")  # base 계보는 승격 보류
        self.assertEqual("policy_withdrawn_hold", champion.promote(self.root, 3.0, self.base)["reason"])
        sneaky = add_model(self.root, "sneaky", manifest=self.manifest(self.base_sha, ()))  # 보류 모델에서 이어 학습, 부모 생략
        honest = add_model(self.root, "honest", parent=self.base, manifest=self.manifest(self.base_sha, ()))
        child = add_model(self.root, "sneaky-child", parent=sneaky, manifest=self.manifest(
            registry.load(self.root)["models"][sneaky]["weights_sha"], ()))
        for model, reason in ((sneaky, PARENT), (child, PARENT), (honest, "policy_withdrawn_hold")):
            self.assertEqual(reason, champion.promote(self.root, 4.0, model)["reason"], model)
            self.assertEqual(reason, eligibility.parent_check(self.root, model)["reason"], model)

    def test_start_weights_must_match_the_declared_parent_exactly(self):
        other = add_model(self.root, "other")
        other_sha = registry.load(self.root)["models"][other]["weights_sha"]
        variants = {"none_with_parent": None, "upper": self.base_sha.upper(), "space": self.base_sha + " ",
                    "prefix40": self.base_sha[:40], "other_model": other_sha, "int": 7, "list": [self.base_sha]}
        for name, start in variants.items():
            model = add_model(self.root, "v-" + name, parent=self.base, manifest=self.manifest(start, ()))
            self.assertEqual(PARENT, champion.promote(self.root, 2.0, model)["reason"], name)
        good = add_model(self.root, "good", parent=self.base, manifest=self.manifest(self.base_sha, ()))
        self.assertTrue(champion.promote(self.root, 3.0, good)["ok"])
        scratch = add_model(self.root, "scratch", manifest=self.manifest(None, ()))  # 처음부터 학습: 부모·시작 가중치 모두 없음
        self.assertTrue(eligibility.parent_check(self.root, scratch)["ok"])

    def test_v1_or_missing_key_manifest_is_refused(self):
        v1 = {"format": "harness-train-manifest-v1", "silver_batches": ["b1"], "silver_label_ids": self.ids}
        no_key = dict(self.manifest(None), format=eligibility.MANIFEST_FORMAT)
        del no_key["start_weights_sha"]
        for name, manifest in (("v1", v1), ("v2_without_key", no_key), ("v1_with_key", dict(v1, start_weights_sha=None))):
            model = add_model(self.root, "m-" + name, batches=["b1"], manifest=manifest)
            self.assertEqual(MISMATCH, champion.promote(self.root, 2.0, model)["reason"], name)
            self.assertEqual(MISMATCH, eligibility.parent_check(self.root, model)["reason"], name)
        self.assertNotEqual("harness-train-manifest-v1", eligibility.MANIFEST_FORMAT)


if __name__ == "__main__":
    unittest.main()

"""적격성 계산의 입력 신뢰 경계: 학습 manifest 대조(fail-closed), 철회 뒤 등록된 실행 중 작업 결과의 격리, 호출자 감사 상태 거부,
4단계 부모 조회와 초기 모델, 영향받지 않은 개발 작업(함수 수준). 합성 시험이다.

한계: manifest는 학습이 선언한 자료만 대조한다. 선언하지 않은 부모 가중치·라벨을 실제로 쓴 학습, 같은 권한으로 해시까지 다시 계산한
장부 위조는 잡지 못한다. "영향받지 않은 개발 지속"은 함수 수준만 시험했고 자율 루프 수준은 4단계 미검증이다.
"""
import os
import unittest

from harness import active_learning, audit, cas, champion, eligibility, registry, silver_gate, silver_store, withdrawal
from tests.test_harness_champion_support import add_model, make_root
from tests.test_harness_silver_support import PROTECTED, al_pool, cands, judge
from tests.test_harness_withdrawal_support import OTHER, SCHEDULE, make_batch, sample_of

FMT = eligibility.MANIFEST_FORMAT
HOLD = "policy_withdrawn_hold"


class EligibilityManifestTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.policy = make_batch(self.root, "b1")
        self.other = make_batch(self.root, "o1", scope=OTHER)
        entries = silver_store.load(self.root)
        self.ids = {b: sorted(e["data"]["label_id"] for e in entries if e["event"] == "silver_label" and e["data"]["batch_id"] == b)
                    for b in ("b1", "o1")}
        self.good = {"format": FMT, "silver_batches": ["b1"], "silver_label_ids": self.ids["b1"], "start_weights_sha": None}  # v2(B5-2)

    def test_missing_corrupt_or_mismatched_manifest_is_refused_for_the_model_and_its_descendants(self):
        cases = {"not_json": b"{not json", "wrong_format": dict(self.good, format="v0"), "extra_key": dict(self.good, gold=[]),
                 "batches_differ": dict(self.good, silver_batches=[]), "ids_not_list": dict(self.good, silver_label_ids="x"),
                 "label_of_undeclared_batch": dict(self.good, silver_label_ids=self.ids["b1"] + self.ids["o1"][:1]),
                 "unknown_label": dict(self.good, silver_label_ids=self.ids["b1"] + ["f" * 32]),
                 "duplicate_label": dict(self.good, silver_label_ids=self.ids["b1"] + self.ids["b1"][:1])}
        for name, manifest in cases.items():
            model = add_model(self.root, "m-" + name, batches=["b1"], manifest=manifest)
            res, parent = champion.promote(self.root, 2.0, model), eligibility.parent_check(self.root, model)
            self.assertEqual([(False, "manifest_mismatch")] * 2, [(res["ok"], res["reason"]), (parent["ok"], parent["reason"])], name)
        cas_root = os.path.join(self.root, "cas")
        gone, altered = add_model(self.root, "gone", batches=["b1"]), add_model(self.root, "altered", batches=["b1"])
        models = registry.load(self.root)["models"]
        os.unlink(cas.blob_path(cas_root, models[gone]["data_manifest_sha"]))  # CAS에 없음
        with open(cas.blob_path(cas_root, models[altered]["data_manifest_sha"]), "ab") as handle:
            handle.write(b" ")  # 보관본이 이름(해시)과 다름
        child = add_model(self.root, "child", parent=gone, batches=["o1"])  # 자신의 manifest는 정상, 조상이 확인 불가
        for model in (gone, altered, child):
            self.assertEqual("manifest_missing", champion.promote(self.root, 3.0, model)["reason"])
        subset = dict(self.good, silver_batches=["b1", "o1"])  # 선언 묶음 중 라벨을 안 쓴 묶음은 허용(더 막는 쪽)
        self.assertTrue(champion.promote(self.root, 4.0, add_model(self.root, "over", batches=["b1", "o1"], manifest=subset))["ok"])

    def test_pending_labels_or_a_job_trained_before_the_withdrawal_but_registered_after_is_held(self):
        rows = cands(3, prefix="p1") + [dict(c, label_value=None) for c in cands(2, prefix="p1n")]
        made = judge(self.root, "p1", self.policy, rows)
        manifest = {"format": FMT, "silver_batches": ["p1"], "silver_label_ids": sorted(made["silver"] + made["pending"]),
                    "start_weights_sha": None}
        self.assertEqual("manifest_pending_labels", champion.promote(self.root, 2.0, add_model(self.root, "pend", batches=["p1"],
                                                                                                manifest=manifest))["reason"])
        withdrawal.withdraw(self.root, 3.0, self.policy, "criteria_change")  # 학습은 철회 전 Silver로 시작했고, 결과 등록은 철회 뒤
        running = add_model(self.root, "running", batches=["b1"], manifest=self.good)
        for model in (running, add_model(self.root, "running-child", parent=running)):
            self.assertEqual(HOLD, champion.promote(self.root, 4.0, model)["reason"])
            self.assertFalse(eligibility.parent_check(self.root, model)["ok"])
        self.assertEqual(set(), set(self.ids["b1"]) & {d["label_id"] for d in silver_gate.trainable_labels(self.root)})

    def test_stale_or_forged_audit_status_cannot_bypass_the_gate(self):
        make_batch(self.root, "b2", "planned")
        model = add_model(self.root, "m", batches=["b2"])
        with self.assertRaises(TypeError):  # 승격은 감사 상태 인자를 받지 않는다(위치 인자로도 이름 인자로도)
            champion.promote(self.root, 2.0, model, {"b2": "complete"})
        with self.assertRaises(TypeError):
            champion.promote(self.root, 2.0, model, audit_status={"b2": "complete"})
        self.assertEqual("audit_pending", champion.promote(self.root, 2.0, model)["reason"])
        audit.record_verdicts(self.root, 3.0, "b2", {sample_of(self.root, "b2")[0]: "incorrect"})
        silver_store.append(self.root, 4.0, "audit_completed", {"batch_id": "b2", "policy_id": self.policy, "status": "complete",
                                                               "errors": 0, "judged": 2, "n_sample": 2, "cap": "1/10"})  # 같은 권한의 덧붙임
        self.assertEqual("complete", audit.audit_status(self.root)["b2"])  # 조회는 마지막 줄을 보이지만
        self.assertEqual("lineage_invalid", champion.promote(self.root, 5.0, add_model(self.root, "late", batches=["b2"]))["reason"])
        path = os.path.join(self.root, silver_store.STORE)
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text.replace('"incorrect"', '"correct"'))  # 줄 고쳐 쓰기(해시 불일치) = 무결성 정지
        with self.assertRaises(silver_store.StoreError):
            champion.promote(self.root, 6.0, add_model(self.root, "plain"))

    def test_parent_query_and_initial_model_use_the_same_calculation(self):
        initial = add_model(self.root, "initial")  # Silver 묶음·부모 없음 = 새 계보의 초기 가중치 후보
        self.assertEqual({"ok": True, "model_id": initial}, eligibility.parent_check(self.root, initial))
        make_batch(self.root, "b2", "planned")
        waiting = add_model(self.root, "waiting", batches=["b2"])
        self.assertTrue(eligibility.parent_check(self.root, waiting)["ok"])  # 감사 대기는 부모 사용을 막지 않는다(학습 계속)
        self.assertEqual("audit_pending", champion.promote(self.root, 2.0, waiting)["reason"])
        bad = add_model(self.root, "bad-initial", manifest=b"x")
        self.assertEqual(("manifest_mismatch", "manifest_mismatch"),
                         (eligibility.parent_check(self.root, bad)["reason"], champion.promote(self.root, 2.0, bad)["reason"]))
        self.assertEqual("unknown_model", eligibility.parent_check(self.root, "0" * 64)["reason"])
        os.unlink(cas.blob_path(os.path.join(self.root, "cas"), registry.load(self.root)["models"][initial]["weights_sha"]))
        self.assertEqual("weights_missing", eligibility.parent_check(self.root, initial)["reason"])

    def test_unaffected_policy_work_continues_at_function_level(self):
        withdrawal.withdraw(self.root, 2.0, self.policy, "systematic_error")
        self.assertEqual(5, len(judge(self.root, "o2", self.other, cands(5, prefix="o2", scope=OTHER))["silver"]))  # 다른 정책 라벨 생성
        audit.plan_audit(self.root, 3.0, "o2", seed=1, schedule=SCHEDULE)
        audit.record_verdicts(self.root, 3.0, "o2", {i: "correct" for i in sample_of(self.root, "o2")})
        trainable = silver_gate.trainable_labels(self.root)
        self.assertEqual((25, {self.other}), (len(trainable), {d["policy_id"] for d in trainable}))  # 학습 가능 라벨은 다른 정책 것만
        self.assertTrue(champion.promote(self.root, 4.0, add_model(self.root, "q", batches=["o1", "o2"]))["ok"])
        scopes = [OTHER]  # 승인 상태로 남은 정책 범위
        self.assertEqual(6, len(active_learning.select(al_pool(30), PROTECTED, {
            "error_priority": {"FN": 2.0, "FP": 1.0}, "stratum_scarcity": {"front": 1.0, "back": 0.5}, "threshold_width": 0.4,
            "per_group_cap": 2, "per_seller_cap": 4, "cluster_quota": 6}, 6, 1, scopes)["selected"]))


if __name__ == "__main__":
    unittest.main()

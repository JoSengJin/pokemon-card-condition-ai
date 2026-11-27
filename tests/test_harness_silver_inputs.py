"""Silver 입력 경계: 제외 목록 형식·정규화, 선별 설정의 수 범위, 판정 함수의 이상 반환, 미리 채운 0, 재라벨 대상의 모델 필드. 합성 입력이다."""
import unittest
from functools import partial

from harness import active_learning, relabel, silver_gate, silver_policy, silver_store
from tests.test_harness_champion_support import make_root
from tests.test_harness_silver_support import PROTECTED, al_pool, approve, cands, judge, stored_labels
from tests.test_harness_silver_verifiers import answer, boom

CONFIG = {"error_priority": {"FN": 2.0, "FP": 1.0}, "stratum_scarcity": {"front": 1.0, "back": 0.5}, "threshold_width": 0.4,
          "per_group_cap": 100, "per_seller_cap": 100, "cluster_quota": 100}
CHANGE = {"old": "c0", "new": "c1", "affected_types": ["corner"]}
POOL = [{"image_sha": "img%03d" % i, "zone": "z1", "defect_type": "corner"} for i in range(4)]


class InputBoundaryTest(unittest.TestCase):
    def test_protected_lists_that_are_not_collections_of_strings_are_an_error_everywhere(self):
        root = make_root(self)
        policy = approve(root)
        good = {"image_shas": [], "group_ids": []}
        for bad in ("sha000sha001", b"sha000", None, {"sha000": 1}, [None], [""], ["  "], [1]):
            for name, field in (("sealed", "image_shas"), ("sealed", "group_ids"), ("calibration", "image_shas"),
                                ("calibration", "group_ids")):
                protected = dict(PROTECTED, **{name: dict(good, **{field: bad})})
                for call in (partial(active_learning.select, al_pool(4), protected, CONFIG, 2, 1, []),
                             partial(active_learning.select, [], protected, CONFIG, 2, 1, []),
                             partial(active_learning.protected_reason, al_pool(1)[0], protected),
                             partial(judge, root, "b1", policy, cands(2), protected=protected)):
                    with self.assertRaises(active_learning.ActiveLearningError, msg=(name, field, bad)):
                        call()
        # sealed에 걸리는 항목이라도 calibration 목록이 틀리면 조용히 'sealed'를 돌려주지 않는다
        broken = {"sealed": {"image_shas": ["sha000"], "group_ids": []}, "calibration": {"image_shas": "x", "group_ids": []}}
        with self.assertRaises(active_learning.ActiveLearningError):
            active_learning.protected_reason(al_pool(1)[0], broken)
        self.assertEqual([], stored_labels(root))
        for kind in (list, tuple, set):
            protected = dict(PROTECTED, sealed={"image_shas": kind(["sha000"]), "group_ids": kind(["g001"])})
            self.assertEqual("sealed", active_learning.protected_reason(al_pool(1)[0], protected))

    def test_case_and_surrounding_space_variants_are_still_excluded(self):
        for listed, own in ((" SHA000\n", "sha000"), ("sha000", "  Sha000 ")):
            item = dict(al_pool(1)[0], image_sha=own, group_id="free")
            for name in ("sealed", "calibration"):
                protected = dict(PROTECTED, **{name: {"image_shas": [listed], "group_ids": []}})
                self.assertEqual(name, active_learning.protected_reason(item, protected))
                self.assertEqual([], active_learning.select([item], protected, CONFIG, 1, 1, [])["selected"])
        grouped = dict(PROTECTED, calibration={"image_shas": [], "group_ids": [" G000 "]})
        self.assertEqual("calibration", active_learning.protected_reason(al_pool(1)[0], grouped))
        root = make_root(self)
        res = judge(root, "b1", approve(root), cands(1), protected=dict(PROTECTED, sealed={"image_shas": ["IMG000 "], "group_ids": []}))
        self.assertEqual((["sealed_image"], []), ([r["reason"] for r in res["rejected"]], res["silver"]))

    def test_nan_infinite_and_negative_selection_weights_are_refused(self):
        nan, inf = float("nan"), float("inf")
        item = al_pool(1)[0]
        for table, values in (("error_priority", (nan, inf, -1.0, 0, True, "1")), ("stratum_scarcity", (nan, inf, -inf, -0.5, True, "1"))):
            for value in values:
                for key in (item["error_type"] if table == "error_priority" else item["stratum"], "unused"):
                    config = dict(CONFIG, **{table: dict(CONFIG[table], **{key: value})})
                    with self.assertRaises(active_learning.ActiveLearningError, msg=(table, key, value)):
                        active_learning.select([item], PROTECTED, config, 1, 1, [])
        for value in (nan, inf, -1.0, True):
            with self.assertRaises(active_learning.ActiveLearningError, msg=value):
                active_learning.select([dict(item, learning_value=value)], PROTECTED, CONFIG, 1, 1, [])
        zero = dict(CONFIG, stratum_scarcity={"front": 0, "back": 0})  # 0은 허용(층 부족도 0)
        self.assertEqual(1, len(active_learning.select([dict(item, learning_value=0)], PROTECTED, zero, 1, 1, [])["selected"]))

    def test_non_label_verifier_results_become_pending_and_the_store_stays_readable(self):
        root = make_root(self)
        policy = approve(root)
        for n, odd in enumerate((["normal"], {"value": "normal"}, {"normal"}, float("nan"), object(), 1)):
            for m, verifiers in enumerate(({"independent": answer(odd)}, {"independent": answer(odd), "cv": boom})):
                res = judge(root, "o%d_%d" % (n, m), policy, cands(1, prefix="o%d_%d" % (n, m), uncertain=True), verifiers=verifiers)
                self.assertEqual((1, []), (len(res["pending"]), res["silver"]), odd)
        self.assertEqual({"verifier_invalid_result", "verifier_error:cv:RuntimeError"}, {d["reason"] for d in stored_labels(root)})
        self.assertEqual([], silver_gate.trainable_labels(root))
        self.assertEqual("invalid:list", stored_labels(root)[0]["verification"]["cross_verified"]["independent"])

    def test_a_prefilled_zero_is_not_an_empty_value(self):
        for value in (0, 0.0, 1, "x", [0], True, (), set()):
            with self.assertRaises(silver_policy.PolicyError, msg=value):
                silver_policy.reject_prefilled({"items": [{"Model_Score": value}]})
        for value in (None, "", [], {}, False):
            silver_policy.reject_prefilled({"model_score": value})

    def test_relabel_inputs_with_nested_or_recased_model_fields_are_refused_before_anything_is_written(self):
        root = make_root(self)
        selection = relabel.select_targets(POOL, CHANGE, "human", seed=1)
        repeat = {"image_sha": "img000", "zone": "z1", "criteria_version": "c1", "judge": "human", "repeat_index": 1}
        for leaked in ({"score": 0}, {"Score": 0.9}, {" PRED ": None}, {"meta": {"Is_Error": False}}, {"history": [{"x": ({"FN": 1},)}]}):
            with self.assertRaises(relabel.RelabelError, msg=leaked):
                relabel.select_targets(POOL + [dict(POOL[0], **leaked)], CHANGE, "human", seed=1)
            dirty = [selection["targets"][0], dict(selection["targets"][1], **leaked)]  # 깨끗한 항목이 앞에 있어도 아무 것도 쓰지 않는다
            for targets in (dirty, iter(dirty)):
                with self.assertRaises(relabel.RelabelError, msg=leaked):
                    relabel.request_relabel(root, 1.0, dict(selection, targets=targets))
            with self.assertRaises(relabel.RelabelError, msg=leaked):
                relabel.request_repeat(root, 1.0, [repeat, dict(repeat, repeat_index=2, **leaked)], "plan-a", completed=[
                    ("img000", "z1", "c1", "human")])
        self.assertEqual([], silver_store.load(root))
        self.assertEqual(4, len(relabel.request_relabel(root, 2.0, dict(selection, targets=iter(selection["targets"])))["accepted"]))


if __name__ == "__main__":
    unittest.main()

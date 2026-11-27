"""재라벨 규칙: 중복·끝난 라벨 거절, 기준 판본 변경 유형만 모델 결과 없이 선정, 자기 일치도 재판정은 계획된 반복. 합성 후보이며 라벨 품질 근거가 아니다."""
import unittest

from harness import relabel, silver_policy, silver_store
from tests.test_harness_champion_support import make_root, read_events
from tests.test_harness_silver_support import approve, cands, judge

CHANGE = {"old": "c0", "new": "c1", "affected_types": ["corner"]}
POOL = [{"image_sha": "img%03d" % i, "zone": "z1", "defect_type": "corner" if i % 2 else "surface"} for i in range(20)]


class RelabelTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)

    def requests(self, kind=None):
        return [e["data"] for e in read_events(self.root, silver_store.STORE)
                if e["event"] == "relabel_requested" and (kind is None or e["data"]["kind"] == kind)]

    def test_the_same_key_is_refused_inside_one_call_and_across_calls(self):
        selection = relabel.select_targets(POOL, CHANGE, "human", seed=1)
        self.assertEqual(10, len(selection["targets"]))  # 영향받는 유형(corner)만
        doubled = dict(selection, targets=selection["targets"] + selection["targets"][:2])
        first = relabel.request_relabel(self.root, 1.0, doubled)
        self.assertEqual((10, ["duplicate_request"] * 2), (len(first["accepted"]), [r["reason"] for r in first["rejected"]]))
        second = relabel.request_relabel(self.root, 2.0, selection)
        self.assertEqual((0, {"duplicate_request"}), (len(second["accepted"]), {r["reason"] for r in second["rejected"]}))
        self.assertEqual(10, len(self.requests("relabel")))
        by_judge = relabel.request_relabel(self.root, 3.0, relabel.select_targets(POOL, CHANGE, "agent", seed=1))
        self.assertEqual(10, len(by_judge["accepted"]))  # 판정자가 다르면 다른 키다

    def test_a_label_that_is_already_finished_is_never_requested_again(self):
        policy = approve(self.root)
        finished = judge(self.root, "b2", policy, [dict(cands(1, prefix="x")[0], image_sha="img001")])  # 에이전트 라벨이 기준 판본 c1로 끝남
        self.assertEqual(1, len(finished["silver"]))
        agent = relabel.request_relabel(self.root, 4.0, relabel.select_targets(POOL, CHANGE, "agent", seed=1))
        self.assertEqual([("img001", "z1", "c1", "agent")], [tuple(r["key"]) for r in agent["rejected"] if r["reason"] == "already_completed"])
        human = relabel.request_relabel(self.root, 5.0, relabel.select_targets(POOL, CHANGE, "human", seed=1),
                                        completed=[("img003", "z1", "c1", "human"), ["img005", "z1", "c1", "human"]])
        self.assertEqual({"img003", "img005"}, {r["key"][0] for r in human["rejected"]})
        self.assertEqual(8, len(human["accepted"]))

    def test_targets_are_chosen_without_model_results_and_only_for_the_changed_types(self):
        for leaked in ({"score": 0.9}, {"model_correct": False}, {"error_type": "FN"}, {"pred": "normal"}, {"is_error": True}):
            with self.assertRaises(relabel.RelabelError, msg=leaked):
                relabel.select_targets(POOL + [dict(POOL[0], **leaked)], CHANGE, "human", seed=1)  # 모델이 틀린 구역만 고르는 입력 경로 차단
        for bad in ({"old": "c1", "new": "c1", "affected_types": ["corner"]}, {"old": "c0", "new": "c1", "affected_types": []},
                    {"old": "c0", "new": "c1"}, None):
            with self.assertRaises(relabel.RelabelError, msg=bad):
                relabel.select_targets(POOL, bad, "human", seed=1)
        both = relabel.select_targets(POOL, dict(CHANGE, affected_types=["corner", "surface"]), "human", seed=1)
        self.assertEqual(20, len(both["targets"]))
        one = relabel.select_targets(POOL, CHANGE, "human", seed=1)
        self.assertEqual(({"corner"}, {"c1"}, False), ({t["defect_type"] for t in one["targets"]}, {t["criteria_version"] for t in one["targets"]},
                                                       one["basis"]["model_results_used"]))
        self.assertEqual("all", one["basis"]["mode"])
        first = relabel.select_targets(POOL, CHANGE, "human", seed=3, fraction=0.4)  # 무작위 부분: seed가 같으면 입력 순서와 무관하게 같다
        self.assertEqual(first, relabel.select_targets(list(reversed(POOL)), CHANGE, "human", seed=3, fraction=0.4))
        self.assertEqual((4, "random"), (len(first["targets"]), first["basis"]["mode"]))  # 10개의 40%
        self.assertNotEqual(first["targets"], relabel.select_targets(POOL, CHANGE, "human", seed=4, fraction=0.4)["targets"])
        for bad in (0, 1.5, -0.2):
            with self.assertRaises(relabel.RelabelError):
                relabel.select_targets(POOL, CHANGE, "human", seed=3, fraction=bad)

    def test_self_agreement_repeats_are_planned_marked_separately_and_need_an_original_label(self):
        policy = approve(self.root)
        judge(self.root, "b1", policy, [dict(cands(1, prefix="x")[0], image_sha="img001")])
        item = {"image_sha": "img001", "zone": "z1", "criteria_version": "c1", "judge": "agent", "repeat_index": 1}
        with self.assertRaises(relabel.RelabelError):
            relabel.request_repeat(self.root, 5.0, [item], "")  # 계획 ID 없이는 재판정을 요청하지 못한다
        ok = relabel.request_repeat(self.root, 5.0, [item, dict(item, repeat_index=2)], "plan-a")
        self.assertEqual(2, len(ok["accepted"]))
        dup = relabel.request_repeat(self.root, 6.0, [item], "plan-a")
        self.assertEqual(["duplicate_repeat"], [r["reason"] for r in dup["rejected"]])
        self.assertEqual(1, len(relabel.request_repeat(self.root, 7.0, [item], "plan-b")["accepted"]))  # 다른 계획의 반복은 따로 센다
        orphan = relabel.request_repeat(self.root, 8.0, [dict(item, image_sha="img999")], "plan-a")
        self.assertEqual(["no_original_label"], [r["reason"] for r in orphan["rejected"]])
        marks = self.requests("self_agreement")
        self.assertEqual((3, {True}), (len(marks), {m["planned_repeat"] for m in marks}))
        self.assertEqual([], self.requests("relabel"))  # 새 라벨 요청으로 세지 않는다
        with self.assertRaises(relabel.RelabelError):
            relabel.request_repeat(self.root, 9.0, [dict(item, repeat_index=0)], "plan-a")

    def test_prefilled_items_and_selections_that_do_not_come_from_the_criteria_change_are_refused(self):
        selection = relabel.select_targets(POOL, CHANGE, "human", seed=1)
        dirty = dict(selection, targets=[dict(selection["targets"][0], prediction="normal")])
        with self.assertRaises(silver_policy.PolicyError):
            relabel.request_relabel(self.root, 1.0, dirty)
        forged = dict(selection, basis=dict(selection["basis"], model_results_used=True))
        with self.assertRaises(relabel.RelabelError):
            relabel.request_relabel(self.root, 1.0, forged)
        wrong_version = dict(selection, targets=[dict(selection["targets"][0], criteria_version="c0")])
        with self.assertRaises(relabel.RelabelError):
            relabel.request_relabel(self.root, 1.0, wrong_version)
        wrong_type = dict(selection, targets=[dict(selection["targets"][0], defect_type="surface")])
        with self.assertRaises(relabel.RelabelError):
            relabel.request_relabel(self.root, 1.0, wrong_type)
        self.assertEqual([], self.requests())


if __name__ == "__main__":
    unittest.main()

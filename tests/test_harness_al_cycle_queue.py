"""D7 B조각: 사람 대기열 기록(al_cycle.record_queue)과 relabel.fold_requests의 al_queued 인식. 합성 항목만 쓴다(실제 선별·사람 화면 없음).
기록에는 점수·기대 라벨·모델 출력·결함 유형·층을 넣지 않고 group_id는 남긴다(반대 방향 제외 근거)."""
import os
import tempfile
import unittest

from harness import al_cycle, eligibility, ledger, relabel, silver_policy, silver_store

TASK = "cd" * 32
CRITERIA = "v2"
NOW = 1000.0
ITEM = {"region_id": "r1", "image_sha": "sha1", "zone": "corner_tl", "group_id": "g1", "defect_type": "corner", "stratum": "back",
        "part": "ranked", "random_part": False}
SECOND = dict(ITEM, region_id="r2", image_sha="sha2", group_id="g2", part="random", random_part=True)


def queued(root):
    return [e for e in silver_store.load(root) if e["event"] == "al_queued"]


class RecordQueueTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_human_queue_items_become_al_queued_events_without_scores_or_expected_labels(self):
        res = al_cycle.record_queue(self.root, NOW, TASK, {"human_queue": [ITEM, SECOND], "silver_queue": [dict(ITEM, region_id="r9")]},
                                    CRITERIA)
        self.assertEqual((res["ok"], len(res["accepted"]), res["rejected"]), (True, 2, []))
        rows = queued(self.root)  # 체인 검증(silver_store.load)을 통과한 줄이다. silver_queue 항목은 기록하지 않는다
        self.assertEqual([r["data"]["key"] for r in rows], [["sha1", "corner_tl", CRITERIA, "human"], ["sha2", "corner_tl", CRITERIA, "human"]])
        self.assertEqual(set(rows[0]["data"]), {"key", "task_key", "region_id", "group_id", "random_part"})
        self.assertEqual((rows[0]["data"]["group_id"], rows[1]["data"]["random_part"], rows[0]["data"]["task_key"]), ("g1", True, TASK))
        text = str(rows)
        for hidden in ("score", "expected_label", "defect_type", "stratum", "error_type"):
            self.assertNotIn(hidden, text)

    def test_second_call_and_relabel_requests_see_the_same_key_as_requested(self):
        al_cycle.record_queue(self.root, NOW, TASK, {"human_queue": [ITEM]}, CRITERIA)
        again = al_cycle.record_queue(self.root, NOW + 1, TASK, {"human_queue": [ITEM, SECOND]}, CRITERIA)
        self.assertEqual((len(again["accepted"]), again["rejected"]), (1, [{"key": ["sha1", "corner_tl", CRITERIA, "human"],
                                                                           "reason": "duplicate_request"}]))
        self.assertEqual(len(queued(self.root)), 2)
        self.assertEqual(relabel.fold_requests(silver_store.load(self.root))["requested"],
                         {("sha1", "corner_tl", CRITERIA, "human"), ("sha2", "corner_tl", CRITERIA, "human")})
        change = {"old": "v1", "new": CRITERIA, "affected_types": ["corner"]}  # 같은 키를 재라벨로 다시 요청해도 중복이다
        targets = relabel.select_targets([{"image_sha": "sha1", "zone": "corner_tl", "defect_type": "corner"}], change, "human", 1)
        self.assertEqual(relabel.request_relabel(self.root, NOW + 2, targets)["rejected"][0]["reason"], "duplicate_request")

    def test_same_key_twice_in_one_call_is_queued_once(self):
        res = al_cycle.record_queue(self.root, NOW, TASK, {"human_queue": [ITEM, dict(ITEM, region_id="r1b")]}, CRITERIA)
        self.assertEqual((len(res["accepted"]), [r["reason"] for r in res["rejected"]], len(queued(self.root))), (1, ["duplicate_request"], 1))

    def test_requested_relabel_blocks_the_queue_and_completed_human_label_is_not_queued_again(self):
        change = {"old": "v1", "new": CRITERIA, "affected_types": ["corner"]}
        targets = relabel.select_targets([{"image_sha": "sha1", "zone": "corner_tl", "defect_type": "corner"}], change, "human", 1)
        relabel.request_relabel(self.root, NOW, targets)
        res = al_cycle.record_queue(self.root, NOW + 1, TASK, {"human_queue": [ITEM, SECOND]}, CRITERIA,
                                    completed=[("sha2", "corner_tl", CRITERIA, "human")])
        self.assertEqual((res["accepted"], [r["reason"] for r in res["rejected"]]), ([], ["duplicate_request", "already_completed"]))
        self.assertEqual(queued(self.root), [])

    def test_prefilled_or_model_fields_and_bad_shapes_are_refused_and_nothing_is_written(self):
        bad = {"기대 라벨": dict(ITEM, expected_label="normal"), "점수": dict(ITEM, score=0.4), "모델 점수 중첩": dict(ITEM, extra={"champion_score": 1}),
               "group_id 없음": {k: v for k, v in ITEM.items() if k != "group_id"}, "random_part 문자열": dict(ITEM, random_part="no"),
               "빈 zone": dict(ITEM, zone="")}
        for label, item in bad.items():
            with self.subTest(label), self.assertRaises((al_cycle.AlCycleError, relabel.RelabelError, silver_policy.PolicyError)):
                al_cycle.record_queue(self.root, NOW, TASK, {"human_queue": [SECOND, item]}, CRITERIA)  # 앞 항목이 정상이어도 전부 쓰지 않는다
        for result, criteria, key in (({"silver_queue": []}, CRITERIA, TASK), ([ITEM], CRITERIA, TASK), ({"human_queue": [ITEM]}, "", TASK),
                                      ({"human_queue": [ITEM]}, CRITERIA, "zz")):
            with self.subTest(repr(result)[:30] + criteria + key[:2]), self.assertRaises(ValueError):
                al_cycle.record_queue(self.root, NOW, key, result, criteria)
        self.assertEqual(queued(self.root), [])

    def test_other_silver_readers_ignore_the_new_event_and_chain_stays_valid(self):
        al_cycle.record_queue(self.root, NOW, TASK, {"human_queue": [ITEM]}, CRITERIA)
        entries = silver_store.load(self.root)
        self.assertEqual(silver_policy.fold(entries)["policies"], {})
        self.assertEqual(eligibility.silver_facts(entries)["labels"], {})
        self.assertEqual(ledger.verify(os.path.join(self.root, silver_store.STORE)), [])


if __name__ == "__main__":
    unittest.main()

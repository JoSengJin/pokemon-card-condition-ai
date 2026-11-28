"""D7 대기열 연결: supervisor.run이 VERIFIED al_select의 out/human_queue.json을 al_cycle.record_queue로 대기열에 한 번만 기록한다.
합성 작업·합성 항목만 쓴다(실제 선별·사진·봉인 자료·claude 없음). 사람 화면 발급(gold_issue.issue·relabel.request_relabel)은 부르지 않는다.
기본 꺼짐: NEED_LABEL_CODES·APPROVED_INPUTS·CRITERIA_VERSION 중 하나라도 비면 VERIFIED al_select가 있어도 아무 일도 없다."""
import json
import os
import tempfile
import unittest
from unittest import mock

from harness import al_cycle, gold_issue, ledger, opstate, queue, relabel, silver_store, supervisor
from tests.test_harness_al_cycle_queue import ITEM, SECOND
from tests.test_harness_al_cycle_run import ARMED, INPUTS
from tests.test_harness_support import finish, make_contract

NOW = 1_000_000.0
CRITERIA = "v2"
CRITERIA_ARM = mock.patch.object(al_cycle, "CRITERIA_VERSION", CRITERIA)


def contract(dep, tag=0):
    return make_contract(task_type=al_cycle.TASK_TYPE, outputs=al_cycle.OUTPUTS, inputs=dict(INPUTS, **{"al/extra%d.json" % tag: "ab" * 32}),
                         depends_on=[dep])  # tag로 작업 키를 구별한다


def make_task(root, items, dep, payload_override=None, tag=0):
    """VERIFIED al_select 작업 하나(두 산출물에 같은 내용). 반환 task_key."""
    task = contract(dep, tag)
    body = payload_override if payload_override is not None else json.dumps({"human_queue": items}).encode()
    return finish(root, task, NOW, payload=body)[0]


def lines(root, event):
    return ledger.events(os.path.join(root, "ledger.jsonl"), event)


def queued(root):
    return silver_store.load(root) if os.path.exists(os.path.join(root, silver_store.STORE)) else []


class QueueWiringTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.dep, _ = finish(self.root, make_contract("a"), NOW)

    def cycle(self, n=1):
        with ARMED[0], ARMED[1], CRITERIA_ARM, mock.patch.object(gold_issue, "issue", side_effect=AssertionError("화면 발급 금지")), \
                mock.patch.object(relabel, "request_relabel", side_effect=AssertionError("재라벨 발급 금지")):
            return supervisor.run(self.root, max_cycles=n, poll_s=0)

    def test_verified_al_select_is_queued_once_and_a_second_run_adds_nothing(self):
        key = make_task(self.root, [ITEM, SECOND], self.dep)
        self.assertNotEqual(self.cycle()["state"], opstate.INTEGRITY_HALT)
        rows = [e for e in queued(self.root) if e["event"] == "al_queued"]
        self.assertEqual(([r["data"]["key"] for r in rows], {r["data"]["task_key"] for r in rows}),
                         ([["sha1", "corner_tl", CRITERIA, "human"], ["sha2", "corner_tl", CRITERIA, "human"]], {key}))
        self.assertEqual([(d["task_key"], d["accepted"], d["rejected"]) for d in lines(self.root, al_cycle.QUEUED)], [(key, 2, [])])
        self.cycle(2)  # 재실행(같은 root 여러 회차)
        self.assertEqual((len([e for e in queued(self.root) if e["event"] == "al_queued"]), len(lines(self.root, al_cycle.QUEUED))), (2, 1))
        self.assertEqual(lines(self.root, "declaration_rejected"), [])

    def test_crash_between_record_and_marker_is_repaired_without_duplicates(self):
        key = make_task(self.root, [ITEM], self.dep)
        al_cycle.record_queue(self.root, NOW, key, {"human_queue": [ITEM]}, CRITERIA)  # 기록은 됐는데 표시 줄 전에 죽은 상황
        self.cycle()
        self.assertEqual((len([e for e in queued(self.root) if e["event"] == "al_queued"]), len(lines(self.root, al_cycle.QUEUED))), (1, 1))
        self.assertEqual(lines(self.root, al_cycle.QUEUED)[0]["rejected"][0]["reason"], "duplicate_request")

    def test_default_off_writes_nothing_even_with_a_verified_al_select(self):
        make_task(self.root, [ITEM], self.dep)
        before = ledger.events(os.path.join(self.root, "ledger.jsonl"), "enqueued")
        for patches in ((), (ARMED[0],), (ARMED[1],), (ARMED[0], ARMED[1]), (CRITERIA_ARM, ARMED[0]), (CRITERIA_ARM, ARMED[1])):  # 하나라도 비면 꺼짐
            with self.subTest(len(patches)):
                for p in patches:
                    p.start()
                try:
                    out = supervisor.run(self.root, max_cycles=2, poll_s=0)
                finally:
                    mock.patch.stopall()
                self.assertEqual(al_cycle.pending_queue(self.root), ({}, {}))
                self.assertEqual((queued(self.root), lines(self.root, al_cycle.QUEUED), lines(self.root, "declaration_rejected")), ([], [], []))
        self.assertEqual((ledger.events(os.path.join(self.root, "ledger.jsonl"), "enqueued"), out["cycles"], os.path.exists(os.path.join(self.root, "silver"))), (before, 2, False))

    def test_unverified_or_bad_outputs_are_not_recorded_and_the_cycle_is_not_halted(self):
        queue.enqueue(self.root, contract(self.dep, 9), NOW)
        bad = {"형식 오류(region_id 없음)": json.dumps({"human_queue": [{"group_id": "g", "random_part": True}]}).encode(),
               "미리 채운 점수": json.dumps({"human_queue": [dict(ITEM, score=0.4)]}).encode(),
               "human_queue 아님": json.dumps({"selected": []}).encode()}
        keys = {label: make_task(self.root, None, self.dep, body, tag=i + 1) for i, (label, body) in enumerate(bad.items())}
        out = self.cycle(2)
        self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT)
        self.assertEqual((queued(self.root), lines(self.root, al_cycle.QUEUED)), ([], []))  # 대기 작업(미승인)·형식 오류 모두 기록 0건
        noted = [d["declaration"] for d in lines(self.root, "declaration_rejected")]
        self.assertEqual(sorted(noted), sorted("al_queue:" + k for k in keys.values()))  # 작업마다 한 번, 2회차에 다시 늘지 않는다

    def test_missing_human_queue_file_is_not_recorded(self):
        key = make_task(self.root, [ITEM], self.dep)
        os.remove(os.path.join(self.root, "tasks", key, "out", "human_queue.json"))
        self.cycle()
        self.assertEqual((queued(self.root), lines(self.root, al_cycle.QUEUED)), ([], []))


if __name__ == "__main__":
    unittest.main()

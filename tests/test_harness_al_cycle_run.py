"""D7 C조각: al_select 실행기(al_cycle.run_select)와 declare·need_labels·supervisor 연결. 합성 입력·가짜 판정 줄만 쓴다(실제 선별·학습·모델·claude 없음).
기본 꺼짐: 허용 사유 코드·승인 입력이 비어 있으면 선언 0건이다(Q1~Q3는 사용자 결정 전)."""
import json
import os
import tempfile
import unittest
from unittest import mock

from harness import al_cycle, dedupe, ledger, logical_zones, queue, runner, silver_store, states, supervisor
from harness import contract as ct
from harness.jsonio import read_json
from tests import harness_depth_kit as depth
from tests.test_harness_al_cycle_inputs import POOL, PROTECTED, SEALED_GROUP, stage
from tests.test_harness_support import finish, make_contract

NOW = 1_000_000.0
CODE = "bootstrap_unmeasured"
INPUTS = {rel: "%02d" % i * 32 for i, rel in enumerate((al_cycle.CANDIDATES, al_cycle.PROTECTED, al_cycle.SETTINGS), 1)}
ARMED = (mock.patch.object(al_cycle, "NEED_LABEL_CODES", frozenset({CODE})), mock.patch.object(al_cycle, "APPROVED_INPUTS", INPUTS))


def verdict(root, key, reasons):
    ledger.append(os.path.join(root, "ledger.jsonl"), NOW, "promotion_verdict", {"task_key": key, "candidate_of": "c", "model_id": "m",
                                                                                    "verdict": "reject", "promoted": False, "reasons": reasons})


def read(path):
    with open(path, "rb") as handle:
        return handle.read()


class RunSelectTest(unittest.TestCase):
    def test_writes_selection_and_human_queue_without_scores_or_protected_items(self):
        task_dir, contract = stage()
        out = tempfile.mkdtemp()
        self.assertEqual(al_cycle.run_select(contract, out, task_dir=task_dir), al_cycle.OUTPUTS)
        selection, queue = (json.loads(read(os.path.join(out, name))) for name in al_cycle.OUTPUTS)
        self.assertEqual((set(selection), set(queue), len(selection["selected"]), queue["human_queue"]), ({"selected"}, {"human_queue"}, 6,
                                                                                                           selection["selected"]))
        for name in al_cycle.OUTPUTS:  # 점수·기대 라벨·모델 출력이 파일에 없다(Claude·사람 화면에 앵커링이 새지 않게)
            for hidden in ("score", "expected_label", "error_type", "trace", "seller_id"):
                self.assertNotIn(hidden, read(os.path.join(out, name)).decode("utf-8"))
        self.assertEqual(logical_zones.ITEM_KEYS, set(selection["selected"][0]))

    def test_same_input_gives_same_bytes_and_protected_candidates_never_appear(self):
        pool = [dict(c, group_id=SEALED_GROUP) if i < 10 else c for i, c in enumerate(POOL)]
        task_dir, contract = stage({al_cycle.CANDIDATES: json.dumps(pool)})
        outs = [tempfile.mkdtemp(), tempfile.mkdtemp()]
        for out in outs:
            al_cycle.run_select(contract, out, task_dir=task_dir)
        self.assertEqual(read(os.path.join(outs[0], "selection.json")), read(os.path.join(outs[1], "selection.json")))
        chosen = json.loads(read(os.path.join(outs[0], "selection.json")))["selected"]
        self.assertTrue(chosen)
        self.assertFalse({c["region_id"] for c in pool if c["group_id"] == SEALED_GROUP} & {s["region_id"] for s in chosen})
        self.assertFalse({s["image_sha"] for s in chosen} & set(PROTECTED["sealed"]["image_shas"] + PROTECTED["calibration"]["image_shas"]))

    def test_refuses_without_input_copy_location_wrong_type_or_wrong_outputs(self):
        task_dir, contract = stage()
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HARNESS_INPUT_DIR", None)
            with self.assertRaises(al_cycle.AlCycleError):  # runner가 al_select에 입력 사본을 아직 만들지 않는다(한계): 닫힌 채 실패
                al_cycle.run_select(contract, tempfile.mkdtemp())
        with mock.patch.dict(os.environ, {"HARNESS_INPUT_DIR": os.path.join(task_dir, "in")}):
            self.assertEqual(al_cycle.run_select(contract, tempfile.mkdtemp()), al_cycle.OUTPUTS)
        for bad in (dict(contract, task_type="deterministic"), dict(contract, outputs=["selection.json"]),
                    dict(contract, outputs=list(reversed(al_cycle.OUTPUTS)))):
            with self.subTest(bad["task_type"] + str(bad["outputs"])), self.assertRaises(al_cycle.AlCycleError):
                al_cycle.run_select(bad, tempfile.mkdtemp(), task_dir=task_dir)

    def test_runs_under_the_real_runner_drain_and_feeds_record_queue(self):
        root = tempfile.mkdtemp()
        dep, _ = finish(root, make_contract("a"), NOW)
        task_dir, contract = stage(overrides={"depends_on": [dep]})
        key = queue.enqueue(root, contract, NOW)
        done = runner.drain(root, {al_cycle.TASK_TYPE: lambda task, out: al_cycle.run_select(task, out, task_dir=task_dir)}, now_fn=lambda: NOW)
        self.assertEqual((done["failed"], len(done["done"])), ([], 1))
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.VERIFIED)
        result = json.loads(read(os.path.join(root, "tasks", key, "out", "human_queue.json")))
        self.assertEqual(len(al_cycle.record_queue(root, NOW, key, result, "v2")["accepted"]), 6)
        self.assertEqual(len([e for e in silver_store.load(root) if e["event"] == "al_queued"]), 6)

    def test_registration_names_and_executor_table(self):
        self.assertIn(al_cycle.TASK_TYPE, dedupe.PLAIN_TYPES)
        self.assertEqual(al_cycle.EXECUTORS, {al_cycle.TASK_TYPE: al_cycle.run_select})
        self.assertEqual(ct.validate_contract(stage()[1])["task_type"], al_cycle.TASK_TYPE)


class DeclareTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.dep, _ = finish(self.root, make_contract("a"), NOW)
        self.other, _ = finish(self.root, make_contract("b"), NOW)
        verdict(self.root, self.dep, [CODE, "direction_unstable"])
        verdict(self.root, self.other, ["direction_unstable"])

    def test_default_is_off_nothing_is_declared_or_written(self):
        before = sorted(os.listdir(self.root))
        for declared in ({}, {"k": {"x": 1}}):
            self.assertEqual(al_cycle.declare(self.root, declared), declared)
        self.assertEqual(al_cycle.declare(self.root, None), None)
        self.assertEqual((al_cycle.NEED_LABEL_CODES, al_cycle.APPROVED_INPUTS, al_cycle.need_labels(self.root)), (frozenset(), {}, []))
        self.assertEqual(sorted(os.listdir(self.root)), before)

    def test_either_half_alone_still_declares_nothing(self):
        with ARMED[0]:
            self.assertEqual(al_cycle.declare(self.root, {}), {})
        with ARMED[1]:
            self.assertEqual(al_cycle.declare(self.root, {}), {})

    def test_armed_declares_one_deterministic_contract_per_matching_verdict(self):
        with ARMED[0], ARMED[1]:
            self.assertEqual(al_cycle.need_labels(self.root), [self.dep])
            first = al_cycle.declare(self.root, {"user": {"keep": 1}})
            [(key, task)] = [(k, v) for k, v in first.items() if k != "user"]
            self.assertEqual((first["user"], ct.task_key(task), task["depends_on"], task["task_type"], task["inputs"], task["outputs"]),
                             ({"keep": 1}, key, [self.dep], al_cycle.TASK_TYPE, INPUTS, al_cycle.OUTPUTS))
            self.assertEqual((task["needs_llm"], task["needs_vision"], "run_conditions" in task), (False, False, False))
            ct.validate_contract(task)
            self.assertEqual(al_cycle.declare(self.root, first), first)  # 같은 입력은 같은 선언(멱등)

    def test_malformed_verdict_lines_are_ignored(self):
        os.remove(os.path.join(self.root, "ledger.jsonl"))  # setUp의 정상 판정 줄·완료 줄을 지우고 형식이 틀린 줄만 남긴다
        for data in ({"task_key": 7, "reasons": [CODE]}, {"task_key": self.dep, "reasons": CODE}, {"task_key": self.dep, "reasons": [[CODE], 3]},
                     {"reasons": [CODE]}):
            ledger.append(os.path.join(self.root, "ledger.jsonl"), NOW, "promotion_verdict", data)
        with ARMED[0], ARMED[1]:
            self.assertEqual(al_cycle.need_labels(self.root), [])


class SupervisorWiringTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.dep, _ = finish(self.root, make_contract("a"), NOW)
        verdict(self.root, self.dep, [CODE])

    def registered(self):
        tasks = os.path.join(self.root, "tasks")
        return [k for k in os.listdir(tasks) if read_json(os.path.join(tasks, k, "contract.json"))["task_type"] == al_cycle.TASK_TYPE]

    def test_empty_codes_mean_the_supervisor_cycle_registers_no_al_select_task(self):
        before = ledger.events(os.path.join(self.root, "ledger.jsonl"), "enqueued")
        out = supervisor.run(self.root, max_cycles=2, poll_s=0)
        self.assertEqual((out["cycles"], self.registered(), ledger.events(os.path.join(self.root, "ledger.jsonl"), "enqueued")),
                         (2, [], before))
        self.assertFalse(os.path.exists(os.path.join(self.root, "supervisor", "declared.json")))

    def test_armed_cycle_registers_the_declared_task_once(self):
        with ARMED[0], ARMED[1]:
            supervisor.run(self.root, max_cycles=2, poll_s=0)
        [key] = self.registered()
        self.assertEqual(read_json(os.path.join(self.root, "tasks", key, "contract.json"))["depends_on"], [self.dep])
        self.assertEqual(len([d for d in ledger.events(os.path.join(self.root, "ledger.jsonl"), "enqueued") if d["task_type"] == al_cycle.TASK_TYPE]), 1)


class DepthTest(unittest.TestCase):
    def test_supervisor_path_stays_within_four_and_executor_paths_within_four(self):
        graph = depth.call_graph()
        self.assertLessEqual(depth.longest("supervisor.run", graph)[0], 4)
        for name in ("al_cycle.declare", "al_cycle.record_queue", "al_cycle.load_inputs", "al_cycle.run_select"):
            self.assertLessEqual(depth.longest(name, graph)[0], 3, name)
        self.assertEqual(depth.longest("al_cycle.declare", graph)[1][1:], ["al_cycle.need_labels", "ledger.events", "ledger._load"])


if __name__ == "__main__":
    unittest.main()

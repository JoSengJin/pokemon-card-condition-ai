"""상태 판정 방어: 재시도 중 RUNNING, done.json 형식, 계약 변조, 임시 파일 무시, task_key 형식, 기록 실패 시 잠금."""
import json
import os
import pathlib
import tempfile
import unittest

from harness import contract, lease, queue, states
from tests.test_harness_support import BOOT, claim, alive_with, finish, make_contract

T0 = 1_000_000.0


class StateGuardsTest(unittest.TestCase):
    def test_retry_run_after_a_failure_is_running_and_its_own_failure_makes_it_failed(self):
        with tempfile.TemporaryDirectory() as root:
            key, alive = queue.enqueue(root, make_contract(), T0), alive_with()
            tdir = os.path.join(root, "tasks", key)
            first = claim(root, key, os.getpid(), BOOT, T0)
            queue.fail(root, key, first["run_id"], first["lease"], "transient", "ConnectionError", T0 + 1)
            retry = claim(root, key, os.getpid(), BOOT, T0 + 2)  # 실패 이력이 있는 작업의 재시도
            self.assertEqual((retry["ok"], retry["plan"]["action"]), (True, "retry"))
            self.assertEqual(states.classify(tdir, T0, alive), states.RUNNING)  # 실패 기록이 있어도 실행 중이다
            queue.fail(root, key, retry["run_id"], retry["lease"], "transient", "ConnectionError", T0 + 3)
            self.assertEqual(states.classify(tdir, T0, alive), states.FAILED)

    def test_done_record_that_is_not_an_object_is_corrupt_and_rerun(self):
        for text in ("null", "[]", '"x"', "7"):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as root:
                key, _ = finish(root, make_contract(), T0)
                tdir = os.path.join(root, "tasks", key)
                pathlib.Path(tdir, "done.json").write_text(text)
                self.assertEqual(states.classify(tdir, T0, alive_with()), states.CORRUPT)
                plan = queue.recover(root, key, T0 + 2, is_alive=alive_with())
                self.assertEqual((plan["action"], plan["runnable"]), ("rerun", True))
                self.assertEqual(states.classify(tdir, T0, alive_with()), states.PENDING)  # 손상 기록은 history로 보관

    def test_tampered_contract_is_corrupt_and_blocks_instead_of_running(self):
        with tempfile.TemporaryDirectory() as root:
            key, _ = finish(root, make_contract(), T0)
            tdir = os.path.join(root, "tasks", key)
            path = pathlib.Path(tdir, "contract.json")
            record = json.loads(path.read_text())
            record["outputs"] = []  # 산출물 선언을 비우고 manifest도 비운 뒤 산출물을 지우는 위조
            path.write_text(json.dumps(record))
            pathlib.Path(tdir, "done.json").write_text(json.dumps({"manifest": {}}))
            os.unlink(os.path.join(tdir, "out", "result.txt"))
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.CORRUPT)  # task_key와 폴더명이 다르다
            other, _ = finish(root, make_contract(tag="o"), T0)  # outputs는 그대로, 다른 필드만 바꿔도 키가 달라진다
            path2 = pathlib.Path(root, "tasks", other, "contract.json")
            path2.write_text(json.dumps(dict(json.loads(path2.read_text()), risk="high")))
            self.assertEqual(states.classify(os.path.dirname(path2), T0, alive_with()), states.CORRUPT)
            refused = claim(root, key, os.getpid(), BOOT, T0 + 1)
            self.assertEqual((refused["ok"], refused["reason"]), (False, "blocked"))
            empty = dict(make_contract(tag="e"), outputs=[])  # 폴더명과 키가 맞아도 outputs가 비어 있으면 안 된다
            bad_dir = os.path.join(root, "tasks", contract.task_key(empty))
            os.makedirs(bad_dir)
            pathlib.Path(bad_dir, "contract.json").write_text(json.dumps(empty))
            self.assertEqual(states.classify(bad_dir, T0, alive_with()), states.CORRUPT)

    def test_stray_temp_files_in_failures_are_not_counted_as_failures(self):
        with tempfile.TemporaryDirectory() as root:
            key = queue.enqueue(root, make_contract(), T0)
            first = claim(root, key, os.getpid(), BOOT, T0)
            queue.fail(root, key, first["run_id"], first["lease"], "transient", "ConnectionError", T0)
            fdir = pathlib.Path(root, "tasks", key, "failures")
            (fdir / "002-abc.json.tmp.123").write_text('{"kind": "determ')
            (fdir / "note.txt").write_text("x")
            plan = queue.recover(root, key, T0 + 1, is_alive=alive_with())
            self.assertEqual((plan["attempts"], plan["failure_kind"], plan["action"]), (1, "transient", "retry"))
            second = claim(root, key, os.getpid(), BOOT, T0 + 2)
            queue.fail(root, key, second["run_id"], second["lease"], "transient", "ConnectionError", T0 + 3)
            self.assertTrue(any(p.name.startswith("002-") and p.suffix == ".json" for p in fdir.iterdir()))

    def test_task_key_must_be_lowercase_hex_64_for_claim_recover_complete_and_fail(self):
        with tempfile.TemporaryDirectory() as root:
            for bad in ("..", "../x", "/etc", "A" * 64, "a" * 63, "a" * 64 + "\n", "", None, 5):
                for call in (lambda k: claim(root, k, 1, BOOT, T0), lambda k: queue.recover(root, k, T0),
                             lambda k: queue.complete(root, k, "r", None, T0),
                             lambda k: queue.fail(root, k, "r", None, "transient", "x", T0)):
                    with self.subTest(key=bad), self.assertRaises(contract.ContractError):
                        call(bad)
            self.assertEqual(os.listdir(root), [])  # root 아래에 아무것도 만들지 않았다

    def test_claim_restores_corrupt_outputs_from_cas_then_skips_and_reruns_when_cas_is_damaged(self):
        with tempfile.TemporaryDirectory() as root:
            key, _ = finish(root, make_contract(), T0, payload=b"data")
            tdir = os.path.join(root, "tasks", key)
            out = pathlib.Path(tdir, "out", "result.txt")
            out.unlink()
            res = claim(root, key, os.getpid(), BOOT, T0 + 1)  # claim도 같은 복구를 한다
            self.assertEqual((res["ok"], res["reason"], res["state"]), (False, "skip", states.CORRUPT))
            self.assertEqual(out.read_bytes(), b"data")
            self.assertEqual(states.classify(tdir, T0, alive_with()), states.VERIFIED)
            out.write_bytes(b"datX")
            recorded = json.loads(pathlib.Path(tdir, "done.json").read_text())["manifest"]["result.txt"]
            pathlib.Path(root, "cas", recorded[:2], recorded).write_bytes(b"damaged")
            again = claim(root, key, os.getpid(), BOOT, T0 + 2)  # 보관본도 손상: 새로 실행한다
            self.assertEqual((again["ok"], again["plan"]["action"]), (True, "rerun"))
            lease.release(again["lease"])

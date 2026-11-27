"""runner 오류 범위: 한 작업의 기록 오류는 그 작업만 멈추고 drain은 계속한다. SystemExit은 결정적 실패, KeyboardInterrupt는 전파."""
import functools
import os
import sys
import tempfile
import unittest
from unittest import mock

from harness import cas, ledger, queue, runner, states
from tests.test_harness_runner_kit import task, write_result
from tests.test_harness_support import alive_with

T0 = 1_000_000.0


def failing_on(event, error, real, path, ts, name, data):
    """ledger.append 대용: 지정한 이벤트에서만 오류를 내고 나머지는 실제 append."""
    if name == event:
        raise error
    return real(path, ts, name, data)


def raise_(exc):
    raise exc


@unittest.skipUnless(sys.platform == "darwin", "runner는 실제 부팅 식별자(macOS kern.boottime)를 쓴다")
class RunnerErrorsTest(unittest.TestCase):
    def test_ledger_failure_after_the_done_record_is_a_warning_and_the_task_stays_verified(self):
        with tempfile.TemporaryDirectory() as root:
            keys = [queue.enqueue(root, task(n, task_type="ok"), T0) for n in ("A", "B")]
            hook = functools.partial(failing_on, "completed", OSError("장부 쓰기 실패"), ledger.append)
            with mock.patch.object(queue.ledger, "append", side_effect=hook):
                summary = runner.drain(root, {"ok": write_result}, now_fn=lambda: T0)
            self.assertEqual((sorted(summary["done"]), summary["failed"], summary["stopped"]), (sorted(keys), [], {}))
            self.assertEqual(sorted(k for k, why in summary["warnings"]), sorted(keys))
            for key in keys:
                tdir = os.path.join(root, "tasks", key)
                self.assertEqual(states.classify(tdir, T0, alive_with()), states.VERIFIED)
                self.assertFalse(os.path.exists(os.path.join(tdir, "lease.json")))

    def test_cas_error_in_complete_is_a_deterministic_failure_and_drain_continues(self):
        with tempfile.TemporaryDirectory() as root:
            keys = [queue.enqueue(root, task(n, task_type="ok"), T0) for n in ("A", "B")]
            with mock.patch.object(queue.cas, "put", side_effect=cas.CasError("보관 실패")):
                summary = runner.drain(root, {"ok": write_result}, now_fn=lambda: T0)
            self.assertEqual((summary["done"], sorted(summary["failed"])), ([], sorted([[k, "deterministic"] for k in keys])))
            self.assertTrue(all(not os.path.exists(os.path.join(root, "tasks", k, "lease.json")) for k in keys))

    def test_failure_record_error_stops_only_that_task_even_when_only_the_ledger_write_fails(self):
        with tempfile.TemporaryDirectory() as root:
            bad, good = queue.enqueue(root, task("BAD", task_type="bad"), T0), queue.enqueue(root, task("GOOD", task_type="ok"), T0)
            executors = {"bad": lambda t, o: raise_(TypeError("x")), "ok": write_result}
            with mock.patch.object(queue, "fail", side_effect=queue.QueueError("기록 불가")):
                summary = runner.drain(root, executors, now_fn=lambda: T0)
            self.assertEqual(summary["done"], [good])
            self.assertTrue(summary["stopped"][bad].startswith("fail_record_error: QueueError"))
        with tempfile.TemporaryDirectory() as root:  # queue.fail 안쪽에서 장부 쓰기만 실패: fail의 finally가 이미 작업권을 닫았다
            bad, good = queue.enqueue(root, task("BAD", task_type="bad"), T0), queue.enqueue(root, task("GOOD", task_type="ok"), T0)
            hook = functools.partial(failing_on, "failed", OSError("장부 쓰기 실패(실패 기록 직후)"), ledger.append)
            with mock.patch.object(queue.ledger, "append", side_effect=hook):
                summary = runner.drain(root, executors, now_fn=lambda: T0)  # 이중 해제로 EBADF가 나면 여기서 중단된다
            self.assertEqual(summary["done"], [good])
            self.assertTrue(summary["stopped"][bad].startswith("fail_record_error: OSError"))
            self.assertEqual(states.classify(os.path.join(root, "tasks", bad), T0, alive_with()), states.FAILED)  # 실패 기록은 남았다

    def test_claim_recording_error_stops_only_that_task_and_leaves_no_lease(self):
        with tempfile.TemporaryDirectory() as root:
            keys = [queue.enqueue(root, task(n, task_type="ok"), T0) for n in ("A", "B")]
            hook = functools.partial(failing_on, "claimed", OSError("장부 쓰기 실패"), ledger.append)
            with mock.patch.object(queue.ledger, "append", side_effect=hook):
                summary = runner.drain(root, {"ok": write_result}, now_fn=lambda: T0)
            self.assertEqual((summary["done"], summary["executed"]), ([], 0))
            self.assertEqual(sorted(summary["stopped"]), sorted(keys))
            self.assertTrue(all(v.startswith("claim_error: OSError") for v in summary["stopped"].values()))
            self.assertTrue(all(not os.path.exists(os.path.join(root, "tasks", k, "lease.json")) for k in keys))

    def test_system_exit_is_a_deterministic_failure_and_keyboard_interrupt_propagates(self):
        with tempfile.TemporaryDirectory() as root:
            exiter, good = queue.enqueue(root, task("EXIT", task_type="exit"), T0), queue.enqueue(root, task("GOOD", task_type="ok"), T0)
            summary = runner.drain(root, {"exit": lambda t, o: raise_(SystemExit(3)), "ok": write_result}, now_fn=lambda: T0)
            self.assertEqual((summary["done"], summary["failed"]), ([good], [[exiter, "deterministic"]]))
            self.assertIn("SystemExit", states.failures(os.path.join(root, "tasks", exiter))[0]["error"])
            self.assertFalse(os.path.exists(os.path.join(root, "tasks", exiter, "lease.json")))
        with tempfile.TemporaryDirectory() as root:
            queue.enqueue(root, task("KI", task_type="ki"), T0)
            with self.assertRaises(KeyboardInterrupt):  # 사용자 중단은 삼키지 않는다
                runner.drain(root, {"ki": lambda t, o: raise_(KeyboardInterrupt())}, now_fn=lambda: T0)

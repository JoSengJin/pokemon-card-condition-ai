"""처리 도중 건 정지 상태(검증 지적 1·3·8): Python 작업 처리 중 USER_STOPPED 뒤 새 작업 0, 각 단계 뒤 정지면 회차 종료,
조건 값 형식 오류는 fail-closed, 정지 상태(USER_STOPPED·INTEGRITY_HALT·DONE)에서 예산 charge 거절."""
import calendar
import functools
import itertools
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from harness import budget, claude_job, opstate, queue, states, supervisor
from tests.test_harness_runner_kit import SUPERVISOR_MARKED, WRAPPED_RUNNER, task
from tests.test_harness_supervisor_kit import REPO, llm_task, make_fake, runs

EXEC = "tests.test_harness_executors:EXECUTORS"
WED = calendar.timegm((2030, 1, 9, 1, 0, 0))


def nap(task_, out_dir):
    """1.5초 걸리는 Python 작업. 시작하자마자 HARNESS_MARK_DIR에 작업 이름 표식을 남긴다(시작한 작업 수 확인용)."""
    open(os.path.join(os.environ["HARNESS_MARK_DIR"], task_["inputs"]["name"]), "w").close()
    time.sleep(1.5)
    with open(os.path.join(out_dir, "result.txt"), "w") as handle:
        handle.write("nap")
    return ["result.txt"]


EXECUTORS = {"nap": nap}


def _after(name, real, root, *args, **kw):
    """mock side_effect: 실제 단계를 실행한 직후(처리 도중) 정지 상태 name을 건다. 단계의 결과를 그대로 돌려준다."""
    out = real(root, *args, **kw)
    opstate.set_condition(root, name, time.time(), "user", "처리 중 정지")
    return out


class HaltMidCycleTest(unittest.TestCase):
    def test_user_stop_during_python_starts_nothing_after(self):
        root, marks = tempfile.mkdtemp(), tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success"}])
        llm_task(root)
        keys = [queue.enqueue(root, task(n, task_type="nap"), 1.0) for n in ("a", "b", "c")]
        proc = subprocess.Popen(SUPERVISOR_MARKED + ["--root", root, "--claude-bin", claude, "--max-cycles", "3", "--poll", "0.2",
                                              "--executors", "tests.test_harness_supervisor_halt:EXECUTORS"],
                                cwd=REPO, env=dict(env, HARNESS_MARK_DIR=marks), stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, text=True)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        deadline = time.time() + 30
        while not os.listdir(marks) and time.time() < deadline:
            time.sleep(0.02)
        opstate.set_condition(root, opstate.USER_STOPPED, time.time(), "user", "Python 처리 중 정지")
        out = json.loads(proc.communicate(timeout=120)[0].strip().splitlines()[-1])
        self.assertEqual(len(os.listdir(marks)), 1)  # 정지 뒤 새로 시작한 Python 작업 0(처리 중이던 1개만)
        self.assertEqual((runs(log), out["claude_runs"], out["state"]), ([], 0, opstate.USER_STOPPED))
        done = [k for k in keys if states.state_of(states.facts(os.path.join(root, "tasks", k)), False) == states.VERIFIED]
        self.assertEqual(len(done), 1)  # 처리 중이던 작업은 끝까지 마친다(강제 종료하지 않음)

    def test_stop_after_each_step_ends_the_cycle(self):
        claude, log, env = make_fake(self, [{"do": "success"}] * 16)
        # (단계, Python 작업 수): _python은 작업을 처리한 runner와 아무것도 안 한 runner(곧바로 clear_auto로 가는 경로) 둘 다
        steps = [(supervisor, "_python", 2), (supervisor, "_python", 0), (opstate, "clear_auto", 2), (claude_job, "pick", 2)]
        for (owner, attr, count), name in itertools.product(steps, opstate.HALTING):
            root = tempfile.mkdtemp()
            llm_task(root)
            py = [queue.enqueue(root, task(n), 1.0) for n in ("p", "q")[:count]]
            opstate.set_condition(root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "한도", {"next_try_at": 0.0})
            hook = functools.partial(_after, name, getattr(owner, attr))
            with mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": tempfile.mkdtemp()}), \
                    mock.patch.object(supervisor, "RUNNER", WRAPPED_RUNNER), \
                    mock.patch.object(owner, attr, side_effect=hook) as hooked:
                out = supervisor.run(root, claude, EXEC, max_cycles=2, poll_s=0, env=env)
            where = (attr, count, name)
            self.assertEqual((hooked.call_count, out["state"], out["claude_runs"]), (1, name, 0), where)
            verified = [states.state_of(states.facts(os.path.join(root, "tasks", k)), False) == states.VERIFIED for k in py]
            cond = opstate.load(root)["conditions"]
            picked = bool(os.path.isdir(os.path.join(root, claude_job.JOBS)) and os.listdir(os.path.join(root, claude_job.JOBS)))
            if attr == "_python":  # 작업 1개 처리 뒤 정지: 다음 Python 작업·한도 해제·Claude 고르기 모두 안 함
                self.assertEqual((out["python_runs"], sorted(verified), opstate.RATE_LIMITED_SHORT in cond, picked),
                                 (1, [False, True][:count], True, False), where)
            elif attr == "clear_auto":  # 한도 해제 뒤 정지: Claude 작업을 고르지 않는다
                self.assertEqual((verified, opstate.RATE_LIMITED_SHORT in cond, picked), ([True, True], False, False), where)
            else:  # 고른 뒤 정지: claude를 실행하지 않는다
                self.assertEqual((verified, picked), ([True, True], True), where)
        self.assertEqual(runs(log), [])

    def test_malformed_condition_values_fail_closed(self):
        claude, log, env = make_fake(self, [{"do": "success"}])
        bad = [{"RATE_LIMITED_SHORT": None}, {"RATE_LIMITED_SHORT": {"next_try_at": True}},
               {"RATE_LIMITED_WEEKLY": {"next_try_at": "soon"}}, {"RATE_LIMITED_SHORT": {"next_try_at": float("nan")}},
               {"RATE_LIMITED_UNKNOWN": {"next_try_at": float("inf")}}, {"USER_STOPPED": []}]
        good = [{"RATE_LIMITED_SHORT": {"next_try_at": None}}, {"RATE_LIMITED_SHORT": {"next_try_at": 5}},
                {"RATE_LIMITED_WEEKLY": {"next_try_at": 5.5}}, {"DONE": {}}]
        for conds in bad + good:
            root = tempfile.mkdtemp()
            os.makedirs(os.path.join(root, "supervisor"))
            with open(os.path.join(root, opstate.OPSTATE), "w", encoding="utf-8") as handle:
                json.dump({"conditions": conds}, handle)  # NaN·Infinity도 그대로 쓴다(json 기본값)
            self.assertEqual(bool(opstate.load(root).get("unreadable")), conds in bad, conds)
            if conds in bad:
                llm_task(root)
                out = supervisor.run(root, claude, max_cycles=2, poll_s=0, env=env)
                self.assertEqual((out["state"], out["claude_runs"]), (opstate.INTEGRITY_HALT, 0), conds)
        self.assertEqual(runs(log), [])

    def test_budget_charge_refused_in_every_halting_state(self):
        for name in opstate.HALTING:
            root = tempfile.mkdtemp()
            opstate.set_condition(root, name, 1.0, "user", "정지")
            got = budget.charge(root, "experiment", 1, WED)
            self.assertEqual((got["ok"], got["reason"]), (False, "halted:" + name))
            self.assertFalse(os.path.exists(os.path.join(root, budget.BUDGET)))  # 사용량 기록 없음


if __name__ == "__main__":
    unittest.main()

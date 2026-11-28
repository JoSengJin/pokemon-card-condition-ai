"""운영 상태 쓰기 경합(검증 지적 2): 실제 하위 프로세스 4개가 동시에 set_condition·clear_auto를 해도 조건이 사라지지 않는다.

각 프로세스는 opstate.write_json 앞에 0.2초 지연을 넣어(읽기→쓰기 사이를 넓혀) 잠금이 없으면 거의 확실히 덮어쓰기가 나게 한다.
"""
import os
import subprocess
import sys
import tempfile
import time
import unittest

from harness import ledger, opstate
from tests.test_harness_supervisor_kit import REPO, events

SCRIPT = r'''
import os, sys, time
from harness import opstate
root, action, name, go = sys.argv[1:5]
real = opstate.write_json
def slow(path, obj):
    time.sleep(0.2)
    return real(path, obj)
opstate.write_json = slow
open("%s.ready.%d" % (go, os.getpid()), "w").close()
while not os.path.exists(go):
    time.sleep(0.001)
if action == "set":
    opstate.set_condition(root, name, time.time(), "test", "경합 시험")
else:
    opstate.clear_auto(root, name, time.time(), "경합 시험")
'''


class OpStateRaceTest(unittest.TestCase):
    def test_concurrent_set_and_clear_lose_nothing(self):
        jobs = [("set", opstate.USER_STOPPED), ("set", opstate.DONE), ("set", opstate.BUDGET_EXCEEDED),
                ("clear", opstate.RATE_LIMITED_SHORT)]
        for _ in range(3):
            root = tempfile.mkdtemp()
            opstate.set_condition(root, opstate.RATE_LIMITED_SHORT, 1.0, "supervisor", "한도", {"next_try_at": 0.0})
            go = os.path.join(root, "go")
            procs = [subprocess.Popen([sys.executable, "-c", SCRIPT, root, action, name, go], cwd=REPO,
                                      stderr=subprocess.PIPE, text=True) for action, name in jobs]
            for proc in procs:
                self.addCleanup(proc.wait)
                self.addCleanup(proc.kill)
            deadline = time.time() + 30
            while len([n for n in os.listdir(root) if n.startswith("go.ready.")]) < len(jobs) and time.time() < deadline:
                time.sleep(0.01)
            open(go, "w").close()  # 모두 출발선에 선 뒤 동시에 출발
            for proc in procs:
                err = proc.communicate(timeout=60)[1]
                self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(set(opstate.load(root)["conditions"]),
                             {opstate.USER_STOPPED, opstate.DONE, opstate.BUDGET_EXCEEDED})  # 하나도 사라지지 않음
            self.assertEqual(ledger.verify(os.path.join(root, "ledger.jsonl")), [])
            self.assertEqual(len(events(root, "opstate_transition")), 1 + len(jobs))


if __name__ == "__main__":
    unittest.main()

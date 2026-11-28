"""3차 변이 S26: 같은 실행 조건의 동시 등록은 queue.enqueue와 graph.register_missing이 섞여도(enqueue+graph, graph×2) 하나만 들어간다
(둘 다 root의 등록 잠금 안에서 중복 검사·저장을 한다, 2차 결함 G4). 두 하위 프로세스가 같은 시각에 등록한다."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from tests.test_harness_dedupe_keys import exp
from tests.test_harness_git_kit import git_source
from tests.test_harness_support import REPO

RACE = r'''
import sys, time
from harness import contract as ct
from harness import graph, queue
from tests.test_harness_dedupe_keys import exp
root, src, risk, how, gate = sys.argv[1:6]
task = dict(exp(src), risk=risk)
while time.time() < float(gate):
    pass
if how == "graph":
    got = graph.register_missing(root, {ct.task_key(task): task}, 1.0, source_root=src)
    print("DUP" if got.get("duplicates") else "REG" if got["registered"] else "OTHER %r" % got)
else:
    try:
        queue.enqueue(root, task, 1.0, source_root=src)
        print("REG")
    except queue.DuplicateTask:
        print("DUP")
'''


class RegisterRaceTest(unittest.TestCase):
    def test_mixed_and_graph_only_concurrent_registration_admits_one(self):
        src = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, src, True)
        git_source(src)
        exp(src)
        for hows in (("enqueue", "graph"), ("graph", "graph")):
            for trial in range(5):
                root = tempfile.mkdtemp()
                gate = "%.3f" % (time.time() + 1.5)
                procs = [subprocess.Popen([sys.executable, "-c", RACE, root, src, risk, how, gate], cwd=REPO, stdout=subprocess.PIPE,
                                          text=True) for risk, how in zip(("low", "high"), hows)]
                outs = sorted(p.communicate(timeout=60)[0].strip() for p in procs)
                self.assertEqual(outs, ["DUP", "REG"], (hows, trial))
                self.assertEqual(len(os.listdir(os.path.join(root, "tasks"))), 1, (hows, trial))


if __name__ == "__main__":
    unittest.main()

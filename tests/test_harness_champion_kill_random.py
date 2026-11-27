"""임의 시각 kill -9 반복과 동시 승격. 합성 시험이며 모델 성능 근거가 아니다."""
import json
import os
import random
import signal
import subprocess
import sys
import time
import unittest

from harness import champion, registry
from tests.test_harness_champion_support import REPO, add_model, assert_consistent, make_root, pointer_model, read_events

LOOP = r'''
import sys, time
from harness import champion
root, a, b = sys.argv[1:4]
print("READY", flush=True)
while True:
    for model in (a, b):
        champion.promote(root, time.time(), model)
'''
PROMOTE_ONCE = r'''
import os, sys, time
from harness import champion
root, model, gate = sys.argv[1:4]
print("READY", flush=True)
while not os.path.exists(gate):
    time.sleep(0.001)
print(champion.promote(root, time.time(), model)["ok"], flush=True)
'''


def spawn(code, *args):
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.Popen([sys.executable, "-c", code] + [str(a) for a in args], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


class RandomKillTest(unittest.TestCase):
    def setUp(self):
        self.root = make_root(self)
        self.ids = [add_model(self.root, n) for n in "abc"]

    def test_repeated_kill_at_random_moments_never_breaks_the_pointer(self):
        a, b, _ = self.ids
        champion.promote(self.root, 1.0, a)
        rng = random.Random(20261127)
        for round_no in range(30):
            proc = spawn(LOOP, self.root, a, b)
            self.assertEqual("READY", proc.stdout.readline().strip())
            time.sleep(rng.uniform(0.0, 0.09))
            proc.send_signal(signal.SIGKILL)
            proc.communicate()
            self.assertEqual(-signal.SIGKILL, proc.returncode)
            assert_consistent(self, self.root, {a, b})
            self.assertTrue(champion.promote(self.root, 100.0 + round_no, a)["ok"])  # 어떤 중간 상태에서도 재호출로 이어진다
            state = assert_consistent(self, self.root, {a})
            self.assertEqual((a, None), (pointer_model(self.root), state["pending"]))
        self.assertGreater(len([e for e in read_events(self.root) if e["event"] == "switched"]), 30)  # 실제로 승격이 오갔다

    def test_concurrent_promotions_are_serialized_by_the_lock(self):
        a, b, c = self.ids
        champion.promote(self.root, 1.0, a)
        for round_no, models in enumerate(((b, c), (b, b))):
            if round_no:
                champion.promote(self.root, 5.0, a)  # 같은 모델 동시 승격은 a가 현재 Champion일 때 시작한다
            before = len(registry.load(self.root)["history"])
            gate = os.path.join(self.root, "gate-%d" % round_no)
            procs = [spawn(PROMOTE_ONCE, self.root, m, gate) for m in models]
            for proc in procs:
                self.assertEqual("READY", proc.stdout.readline().strip())
            open(gate, "w").close()
            for proc in procs:
                out, err = proc.communicate(timeout=60)
                self.assertEqual((0, "True"), (proc.returncode, out.strip().splitlines()[-1]), err)
            state = assert_consistent(self, self.root, set(models))
            self.assertEqual(pointer_model(self.root), state["history"][-1]["model_id"])
            self.assertIsNone(state["pending"])
            gained = len(state["history"]) - before
            self.assertEqual(2 if models[0] != models[1] else 1, gained)  # 같은 모델이면 한 번만 전환
        events = [e["event"] for e in read_events(self.root)]
        self.assertEqual(events.count("switch_intent"), events.count("switched"))
    def test_reader_never_sees_a_partial_pointer_while_champions_alternate(self):
        a, b, _ = self.ids
        champion.promote(self.root, 1.0, a)
        proc = spawn(LOOP, self.root, a, b)
        self.assertEqual("READY", proc.stdout.readline().strip())
        seen, path, deadline = set(), os.path.join(self.root, registry.POINTER), time.time() + 1.5
        try:
            while time.time() < deadline:
                with open(path, "r", encoding="utf-8") as handle:
                    seen.add(json.load(handle)["model_id"])  # 비어 있거나 잘린 파일이면 여기서 실패한다
        finally:
            proc.send_signal(signal.SIGKILL)
            proc.communicate()
        self.assertEqual({a, b}, seen)  # 읽는 동안 실제로 Champion이 바뀌었다

    def test_unlocked_readers_get_no_false_error_while_promotions_keep_happening(self):
        a, b, _ = self.ids
        champion.promote(self.root, 1.0, a)
        proc = spawn(LOOP, self.root, a, b)
        self.assertEqual("READY", proc.stdout.readline().strip())
        seen, reads, deadline = set(), 0, time.time() + 2.0
        try:
            while time.time() < deadline:
                holder = champion.read_current(self.root)  # 잠금을 쥐지 않은 읽는 쪽의 규약(pointer.py 참조)
                seen.add(holder["model_id"])
                reads += 1
        finally:
            proc.send_signal(signal.SIGKILL)
            proc.communicate()
        self.assertEqual({a, b}, seen)  # ChampionError가 한 번도 나지 않았고, 읽는 동안 실제로 Champion이 바뀌었다
        self.assertGreater(reads, 20)


if __name__ == "__main__":
    unittest.main()

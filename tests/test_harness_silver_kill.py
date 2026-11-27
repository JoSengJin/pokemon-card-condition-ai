"""kill -9 시험: 감사 실패 연쇄·라벨 저장 중에 실제 프로세스가 SIGKILL을 맞아도 저장소가 일관되고, 같은 인자 재호출이 이어서 끝낸다. 합성 데이터다."""
import json
import os
import random
import signal
import subprocess
import sys
import time
import unittest

from harness import audit, champion, ledger, registry, silver_gate, silver_store
from tests.test_harness_champion_support import make_root, pointer_model
from tests.test_harness_silver_support import KILL, PROTECTED, REPO, approve, cands, cascade_setup, run_kill

POINTS = ["before:audit_verdicts:1", "after:audit_verdicts:1", "before:audit_completed:1", "after:audit_completed:1",
          "after:policy_withdrawn:1", "after:invalidated:1", "after:lineage_invalidated:1", "after:switch_intent:1", "after:switched:1",
          "after:champion_restored:1"]  # 2026-11-27: cascade_done은 더 쓰지 않는다(철회 관문이 장부에서 다시 계산해 이어간다)
EVENTS = ("audit_verdicts", "audit_completed", "policy_withdrawn")


class KillTest(unittest.TestCase):
    def failing(self, s):
        """표본 10개 중 2개가 incorrect인 판정(2/10 > 상한 10%)."""
        return {i: ("incorrect" if n < 2 else "correct") for n, i in enumerate(s["sample"])}

    def consistent(self, s):
        """kill 뒤 불변식: 세 장부의 체인이 정상이고 감사 상태는 complete가 아니다(실패 확정 또는 판정 대기). 저장소 이벤트 이름 목록을 돌려준다."""
        root = s["root"]
        for rel in (silver_store.STORE, registry.REGISTRY, "ledger.jsonl"):
            self.assertEqual([], ledger.verify(os.path.join(root, rel)), rel)
        registry.load(root)
        self.assertIn(audit.audit_status(root)["b1"], ("pending", "failed"))
        return [e["event"] for e in silver_store.load(root)]

    def test_kill_at_every_step_of_the_failure_cascade_then_the_same_call_finishes_it(self):
        for point in POINTS:
            s = cascade_setup(self)
            verdicts = self.failing(s)
            run_kill(self, s["root"], "verdicts", point, {"batch_id": "b1", "verdicts": verdicts})
            events = self.consistent(s)
            if "audit_completed" in events:  # 연쇄가 끝나기 전(철회 기록 전 포함)에도 승격은 거절된다
                refused = champion.promote(s["root"], 9.6, s["models"]["m1"])
                self.assertFalse(refused["ok"], point)
            res = audit.record_verdicts(s["root"], 10.0, "b1", verdicts)  # 같은 인자 재호출 = 이어가기
            events = [e["event"] for e in silver_store.load(s["root"])]
            self.assertEqual("failed", res["status"], point)
            for name in EVENTS:
                self.assertEqual(1, events.count(name), (point, name))
            models = registry.load(s["root"])["models"]
            self.assertEqual(("invalidated", "invalidated", "valid"), tuple(models[s["models"][n]]["status"] for n in ("m1", "c1", "base")), point)
            self.assertEqual((s["models"]["base"], "failed"), (pointer_model(s["root"]), audit.audit_status(s["root"])["b1"]), point)

    def test_kill_in_the_middle_of_labeling_then_the_rerun_gives_exactly_the_uninterrupted_result(self):
        root = make_root(self)
        policy = approve(root)
        payload = {"batch_id": "b1", "policy_id": policy, "candidates": cands(8), "protected": PROTECTED}
        run_kill(self, root, "judge", "after:silver_label:3", payload)
        self.assertEqual(3, len(silver_store.load(root)) - 2)  # 정책 승인 두 줄(보정 사용·승인) 뒤 라벨 3개
        run_kill(self, root, "judge", "before:silver_label:2", payload)  # 이어 쓰기 중 또 죽는다(라벨 1개 추가 뒤)
        run_kill(self, root, "judge", "none", payload)
        done = silver_store.load(root)
        ids = [e["data"]["label_id"] for e in done if e["event"] == "silver_label"]
        self.assertEqual((8, 8), (len(ids), len(set(ids))))
        self.assertEqual([], ledger.verify(os.path.join(root, silver_store.STORE)))
        fresh = make_root(self)
        policy2 = approve(fresh)
        silver_gate.judge_candidates(fresh, 9.0, "b1", policy2, cands(8), PROTECTED, {}, criteria_version="c1", model_version="m1")
        self.assertEqual(sorted(ids), sorted(d["label_id"] for d in silver_gate.trainable_labels(fresh)))  # 끊김 없는 실행과 같은 라벨

    def test_kills_at_random_moments_never_corrupt_the_state_and_the_rerun_always_finishes(self):
        rng = random.Random(20261127)
        killed = partial = 0
        for _ in range(30):  # 실행 하나가 약 40ms라서 지연을 그 안에서 뽑는다(시작·import 중에 죽는 경우도 포함)
            s = cascade_setup(self)
            verdicts = self.failing(s)
            proc = subprocess.Popen([sys.executable, "-c", KILL, s["root"], "verdicts", "none",
                                     '{"batch_id": "b1", "verdicts": %s}' % json.dumps(verdicts)], cwd=REPO,
                                    env=dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1"),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            time.sleep(rng.uniform(0.015, 0.07))
            if proc.poll() is None:
                proc.send_signal(signal.SIGKILL)
                killed += 1
            proc.communicate()
            events = self.consistent(s)
            partial += "audit_verdicts" in events and "policy_withdrawn" not in events  # 연쇄 도중에 죽은 횟수(단언하지 않고 관찰만)
            res = audit.record_verdicts(s["root"], 10.0, "b1", verdicts)
            events = [e["event"] for e in silver_store.load(s["root"])]
            self.assertEqual(("failed", [1, 1, 1]), (res["status"], [events.count(n) for n in EVENTS]))
            self.assertEqual(s["models"]["base"], pointer_model(s["root"]))
        self.assertGreater(killed, 0)  # 일회성 관찰(2026-11-27): 30회 중 killed=10, 연쇄 도중 partial=3

    def test_two_processes_running_the_same_cascade_at_once_do_it_exactly_once(self):
        s = cascade_setup(self)
        payload = '{"batch_id": "b1", "verdicts": %s}' % json.dumps(self.failing(s))
        env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
        procs = [subprocess.Popen([sys.executable, "-c", KILL, s["root"], "verdicts", "none", payload], cwd=REPO, env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True) for _ in range(3)]
        outputs = [p.communicate() for p in procs]
        self.assertEqual([0, 0, 0], [p.returncode for p in procs], outputs)
        events = [e["event"] for e in silver_store.load(s["root"])]
        self.assertEqual([1, 1, 1], [events.count(n) for n in EVENTS])
        self.assertEqual(s["models"]["base"], pointer_model(s["root"]))


if __name__ == "__main__":
    unittest.main()

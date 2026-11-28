"""VS4: claude_job의 비전 구역 예산(B5-5) 연결. needs_vision 작업은 claude 실행 시작 직전에 논리 구역 수를 한 번 차감한다(key=task_key).

합성 root·가짜 claude·합성 후보 목록만 쓴다(실제 claude·비전 호출 없음). 이 수는 실제 AI 사용량이 아니다. 이미지 유형(B 묶음)은 여전히 실행
불가라, 아래에서 차감에 닿는 계약은 A 묶음 유형에 needs_vision=true를 선언한 합성 계약뿐이다.
"""
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from unittest import mock

from harness import budget, claude_job, claude_run, logical_zones, opstate, queue, states, supervisor
from harness.jsonio import read_json, write_json
from tests.test_harness_b5_logical_zones import ITEM
from tests.test_harness_supervisor_kit import SUPERVISOR, events, make_fake, runs
from tests.test_harness_support import REPO, make_contract

def world(case, scenario=({"do": "success"},), zones=2, name="v", task_type="misanalysis_general", vision=True, extra=None, root=None):
    """후보 구역 zones개를 입력으로 선언한 작업 하나. (root, task_key, claude, log, env, source). zones=0이면 입력 없음."""
    root, source = root or tempfile.mkdtemp(), tempfile.mkdtemp()
    inputs = dict(extra or {})
    if zones:
        data = json.dumps({"selected": [dict(ITEM, region_id="%s%d" % (name, i), zone="z%d" % i) for i in range(zones)]}).encode()
        os.makedirs(os.path.join(source, "candidates"))
        with open(os.path.join(source, logical_zones.INPUT), "wb") as handle:
            handle.write(data)
        inputs[logical_zones.INPUT] = hashlib.sha256(data).hexdigest()
    task = make_contract(name, task_type=task_type, needs_llm=True, outputs=(name + ".md",))
    key = queue.enqueue(root, dict(task, needs_vision=vision, inputs=inputs), 1.0)
    return (root, key) + make_fake(case, list(scenario)) + (source,)


def charged(root):
    """비전 차감 줄의 (key, amount) 목록."""
    return [(r["data"]["key"], r["data"]["amount"]) for r in events(root, "charge", budget.BUDGET) if r["data"]["kind"] == "vision_zone"]


def job_of(root, key):
    return read_json(claude_job.paths(root, key)[0])


class VisionChargeTest(unittest.TestCase):
    def test_entrypoint_charges_once_before_the_run_and_image_bundles_never_reach_it(self):
        root, key, claude, log, env, source = world(self, [{"do": "success"}] * 3, zones=3)
        image = world(self, name="img", task_type="silver_labeling", root=root)[1]
        plain = world(self, name="plain", zones=0, vision=False, root=root)[1]
        argv = SUPERVISOR + ["--root", root, "--claude-bin", claude, "--source-root", source, "--max-cycles", "4", "--poll", "0"]
        done = subprocess.run(argv, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        if os.environ.get("VS4_EVIDENCE"):
            print(json.dumps({"argv": argv, "stdout": done.stdout.strip(), "root": root, "vision": key, "image": image}))
        self.assertEqual(charged(root), [(key, 3)])
        self.assertEqual([states.state_of(states.facts(os.path.join(root, "tasks", k)), False) for k in (key, plain, image)],
                         [states.VERIFIED, states.VERIFIED, states.PENDING])
        self.assertIn("no_runnable_permission_bundle", job_of(root, image)["hold_reason"])  # B 묶음: 차감 전에 막힌다
        self.assertEqual(len(runs(log)), 2)
        root, key, claude, log, env, source = world(self)
        real, seen = claude_run.run_once, []
        with mock.patch.object(claude_run, "run_once", side_effect=lambda *a, **k: (seen.append(charged(root)), real(*a, **k))[1]):
            supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual(seen, [[(key, 2)]])  # claude 실행이 시작되는 시점에 이미 차감돼 있다

    def test_uncountable_or_refused_charge_never_runs_and_a_user_stop_keeps_the_job(self):
        root, key, claude, log, env, source = world(self, zones=0)  # 후보 목록 입력이 없다: 셀 수 없다
        supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual((job_of(root, key)["status"], job_of(root, key)["hold_reason"].split(":")[0]), ("blocked", "logical_zone_uncountable"))
        self.assertEqual((runs(log), charged(root)), ([], []))
        root, key, claude, log, env, source = world(self, [{"do": "success"}] * 2)
        budget.charge(root, "vision_zone", 299, time.time(), key="earlier")
        got = supervisor.run(root, claude, max_cycles=2, poll_s=0, env=env, source_root=source)  # 2구역 > 남은 1
        self.assertEqual((got["state"], job_of(root, key)["hold_reason"][:28]), (opstate.BUDGET_EXCEEDED, "vision_budget_refused: limit"))
        self.assertEqual((runs(log), charged(root)), ([], [("earlier", 299)]))
        opstate.clear_by_user(root, opstate.BUDGET_EXCEEDED, time.time(), "사람 재승인")
        other = world(self, name="other", zones=0, vision=False, root=root)[1]
        got = supervisor.run(root, claude, max_cycles=3, poll_s=0, env=env, source_root=source)
        self.assertEqual((got["state"], len(runs(log)), states.state_of(states.facts(os.path.join(root, "tasks", other)), False)),
                         (opstate.RUNNING, 1, states.VERIFIED))  # 거절된 작업만 대기: 다시 골라 전체를 또 멈추지 않는다
        root, key, claude, log, env, source = world(self)  # 회차의 정지 확인 뒤·차감 직전에 사용자 중단
        real = budget.charge
        with mock.patch.object(budget, "charge", side_effect=lambda *a, **k: (opstate.set_condition(
                root, opstate.USER_STOPPED, time.time(), "user", "RC 중단"), real(*a, **k))[1]):
            got = supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual((got["outcomes"], job_of(root, key)["status"], job_of(root, key)["session_id"]), (["halted"], "new", None))
        self.assertEqual((runs(log), charged(root)), ([], []))
        opstate.clear_by_user(root, opstate.USER_STOPPED, time.time(), "사용자 재개")
        supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual((len(runs(log)), charged(root)), (1, [(key, 2)]))
        root, key, claude, log, env, source = world(self)
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        with open(os.path.join(root, budget.BUDGET), "w", encoding="utf-8") as handle:
            handle.write('{"seq": 0, "event": "char')  # 반쯤 쓴 장부: 사용량을 모른다
        got = supervisor.run(root, claude, max_cycles=1, env=env, source_root=source)
        self.assertEqual((got["state"], runs(log), job_of(root, key)["status"]), (opstate.INTEGRITY_HALT, [], "new"))


if __name__ == "__main__":
    unittest.main()

"""VS3 독립 검증 필수 결함 D1~D4 수정 시험(artifacts/harness-resume-20261127/verify-vs3-20261128.md).

- D1: Claude가 쓴 next_plan.json 내용으로 생기는 예외는 그 계획만 거절·대기한다(Supervisor 전체 INTEGRITY_HALT 없음).
- D2: 승인 변수 experiment_parameter.value는 수로 비교한다(1 = 1.0): baseline·대조 값과 같으면 거절, 기각 대조는 int·float 두 표기로.
  전역 dedupe의 config 자료형 규칙(사람 등록 config의 1 ≠ 1.0)은 바꾸지 않는다.
- D3: LLM 작업에 직·간접 의존하는 실험·학습·평가는 장부에 관문 통과 줄(plan_gate_declared)이 있을 때만 runner가 실행한다(공개 등록 함수
  queue.enqueue·graph.register_missing 직접 호출·업그레이드 전 PENDING 우회 차단). 선언 저장·장부 줄·등록 사이 SIGKILL 뒤에도 통과한 실험은 정확히 한 번.
- D4: 기각 대조에서 비교할 수 없는 하네스 기록(손상 계약·사라진 커밋)과 원본 artifacts/experiments의 판별할 수 없는 ./experiment 기록은 그 계획을
  대기시키고, 하네스 밖 ./experiment 기록과 실행 조건(동결 plan·command·source_hashes)이 같으면 거절한다.
가짜 실험 executor·합성 git 원본만 쓴다(실제 ./experiment·claude·모델 호출 없음). 합성 통과는 모델 성능 근거가 아니다.
"""
import functools
import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from harness import contract as ct
from harness import cas, graph, opstate, plan_gate, queue, runner, states, supervisor
from harness.jsonio import read_json
from tests import harness_plan_gate_kit as kit
from tests import test_harness_vs3_gate as vs3_gate  # 모듈로 가져온다(시험 클래스를 이 모듈에 다시 노출하지 않게)
from tests import test_harness_vs3_gate_flow as vs3_flow
from tests.test_harness_support import REPO, make_contract
from tests.test_harness_git_kit import git
from tests.test_harness_supervisor_kit import events

# SIGKILL 지점(D3): k0 declared.json 저장 직전, k1 다음 실험의 plan_gate_declared 장부 줄 직전, k2 그 줄 직후(등록 전), k3 등록 직후
KILL = ("import os, signal, sys\nfrom harness import graph, ledger, plan_gate, supervisor\nmode = sys.argv[3]\n"
        "orig_w, orig_a, orig_r = plan_gate.write_json, ledger.append, graph.register_missing\n"
        "def write(path, obj):\n    if mode == 'k0' and path.endswith('declared.json'):\n        os.kill(os.getpid(), signal.SIGKILL)\n"
        "    return orig_w(path, obj)\n"
        "def append(path, ts, event, data):\n    hit = event == 'plan_gate_declared' and data.get('task_type') == 'experiment'\n"
        "    if hit and mode == 'k1':\n        os.kill(os.getpid(), signal.SIGKILL)\n    out = orig_a(path, ts, event, data)\n"
        "    if hit and mode == 'k2':\n        os.kill(os.getpid(), signal.SIGKILL)\n    return out\n"
        "def register(*a, **k):\n    out = orig_r(*a, **k)\n    if mode == 'k3':\n        os.kill(os.getpid(), signal.SIGKILL)\n    return out\n"
        "plan_gate.write_json, ledger.append, graph.register_missing = write, append, register\n"
        "supervisor.run(sys.argv[1], max_cycles=1, poll_s=0, source_root=sys.argv[2], now_fn=lambda: %r)\n" % kit.NOW)


class PlanGateFixTest(unittest.TestCase):
    _chain = vs3_gate.PlanGateTest._chain  # 대조 VERIFIED → 분석 완료(사양대로 쓴 next_plan.json) → gate (같은 도구를 다시 쓴다)
    _refused = vs3_gate.PlanGateTest._refused
    _analysis = vs3_flow.PlanGateFlowTest._analysis

    def test_d1_plan_content_exceptions_hold_only_that_plan(self):
        huge = json.dumps(kit.proposal(kit.control("0" * 40))).replace("0.7", "1" + "0" * 400)  # 401자리 정수: int로 읽히고 float 범위 밖
        got = self._chain({"raw": huge})
        self.assertTrue(got["reason"].startswith("refused") and "유한한 숫자" in got["reason"], got["reason"])
        root, src, head = got["root"], got["src"], got["head"]
        other = self._chain(world=(root, src, head), plan={"hid": "H2", "value": 0.65})  # 같은 root의 독립 계획
        self.assertIsNone(other["reason"])
        out = supervisor.run(root, max_cycles=2, poll_s=0, sleep_fn=float, now_fn=functools.partial(float, kit.NOW), source_root=src)
        self.assertEqual((out["state"], opstate.effective(opstate.load(root))), (opstate.RUNNING, opstate.RUNNING))
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        self.assertEqual([k for k, c in tasks.items() if c["depends_on"] == [got["analyze"]]], [])
        self.assertEqual(len([k for k, c in tasks.items() if c["depends_on"] == [other["analyze"]]]), 1)  # 독립 계획은 등록된다
        self.assertIn("plan:" + got["analyze"], read_json(os.path.join(root, graph.REJECTED)))
        for exc in (IndexError("x"), ZeroDivisionError("x"), OverflowError("x")):  # 재현 지점 밖의 같은 원인: 계획 검사의 다른 예외 부류
            with mock.patch.object(plan_gate, "_diff", side_effect=exc):
                got = self._chain()
            self.assertTrue(got["reason"].startswith("waiting: " + type(exc).__name__), got["reason"])

    def test_d2_type_only_change_of_the_approved_variable_is_the_same_number(self):
        for words, chain in (("baseline 또는 대조", {"spec": {"over": {"value": 1}}, "plan": {"value": 1.0}}),  # A: 대조 1.0 → 1(실질 변경 0)
                             ("baseline 또는 대조", {"spec": {"over": {"value": 0.5}}}),  # C: value = baseline(기존 check_experiment_parameter 규칙)
                             ("기각·중복 가설", {"spec": {"over": {"value": 2}}, "fail": 2.0}),  # B: 실패 F 2.0 → 2
                             ("기각·중복 가설", {"spec": {"over": {"value": 2.0}}, "fail": 2})):  # B′: 사람이 int로 등록한 실패 F 2 → 2.0
            self._refused(words, **chain)
        got = self._chain({"over": {"value": 2.5}}, fail=2.0)  # 다른 수는 그대로 통과(과잉 차단 없음)
        self.assertIsNone(got["reason"])
        dup = queue.enqueue(got["root"], kit.control(got["head"], value=2, hid="Z"), kit.NOW, source_root=got["src"])  # 전역 규칙은 그대로: 사람 등록 config의 2 ≠ 2.0
        self.assertTrue(os.path.isdir(os.path.join(got["root"], "tasks", dup)))

    def test_d3_registration_outside_the_gate_never_runs(self):
        root, src, head, e1, a1 = self._analysis()
        out = plan_gate.gate(root, read_json(os.path.join(root, vs3_gate.DECLARED)), kit.NOW, src)
        [k2] = [k for k, c in out.items() if c["depends_on"] == [a1]]
        graph.register_missing(root, out, kit.NOW, source_root=src)
        helper = queue.enqueue(root, make_contract("d", task_type="deterministic", depends_on=[a1]), kit.NOW)  # 결정론 작업 경유 간접 의존
        kit.finish(root, helper, {"result.txt": "x"})
        x = queue.enqueue(root, dict(kit.control(head, value=9.9, hid="X"), depends_on=[a1]), kit.NOW, source_root=src)  # 공개 함수 1(업그레이드 전 PENDING도 같은 모양)
        y = dict(kit.control(head, value=7.7, hid="Y"), depends_on=[a1])
        graph.register_missing(root, {ct.task_key(y): y}, kit.NOW, source_root=src)  # 공개 함수 2: supervisor 밖 직접 호출
        w = queue.enqueue(root, dict(kit.control(head, value=8.8, hid="W"), depends_on=[helper]), kit.NOW, source_root=src)
        for hid in ("H-next", "X", "Y", "W"):
            kit.seed(src, hid)  # 실행되면 성공할 기록(막힘이 기록 부재 때문이 아님)
        summary = runner.drain(root, kit.EXECUTORS, now_fn=functools.partial(float, kit.NOW), source_root=src)
        self.assertEqual(summary["done"], [k2])  # 관문을 통과한 실험만
        for key in (x, ct.task_key(y), w):
            self.assertIn(key, summary["untouched"]["llm_dependents"])
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", key)), False), states.PENDING)

    def test_d3_kill_between_declaration_ledger_and_registration_runs_the_passed_experiment_exactly_once(self):
        for mode in ("k0", "k1", "k2", "k3"):
            root, src, head, e1, a1 = self._analysis()
            forged = queue.enqueue(root, dict(kit.control(head, value=9.9, hid="X"), depends_on=[a1]), kit.NOW, source_root=src)
            done = subprocess.run([sys.executable, "-c", KILL, root, src, mode], cwd=REPO, capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, -9, (mode, done.stderr[-500:]))
            supervisor.run(root, max_cycles=2, poll_s=0, sleep_fn=float, now_fn=functools.partial(float, kit.NOW + 1), source_root=src)
            for hid in ("H-next", "X"):
                kit.seed(src, hid)
            for _ in range(2):
                runner.drain(root, kit.EXECUTORS, now_fn=functools.partial(float, kit.NOW + 1), source_root=src)
            children = [k for k in os.listdir(os.path.join(root, "tasks"))
                        if read_json(os.path.join(root, "tasks", k, "contract.json"))["depends_on"] == [a1] and k != forged]
            self.assertEqual(len(children), 1, mode)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", children[0])), False), states.VERIFIED, mode)
            self.assertEqual([e["data"]["task_key"] for e in events(root, "completed")].count(children[0]), 1, mode)
            self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", forged)), False), states.PENDING, mode)
            self.assertEqual([e["data"]["task_key"] for e in events(root, "claimed")].count(forged), 0, mode)

    def _record(self, src, name, value=0.8, code=None, record=None):
        """원본 artifacts/experiments/<name>/에 ./experiment(experiment_record.prepare) 형식 기록을 쓴다: 동결 plan.json = 계획 + 설명 키 +
        schema_version·threshold·independent·production_adopted, record.json = command·files(plan.json SHA)·source_hashes. record로 덮어쓴다."""
        folder = os.path.join(src, "artifacts", "experiments", name)
        os.makedirs(folder, exist_ok=True)
        body = dict(kit.control("0" * 40, value=value)["run_conditions"]["config"]["plan"], hypothesis_id="CODEX-H9", hypothesis="다른 설명",
                    change="c", success_criterion="s", failure_criterion="f", schema_version=1, threshold=0.5, independent=False,
                    production_adopted=False)
        with open(os.path.join(folder, "plan.json"), "w", encoding="utf-8") as handle:
            json.dump(body, handle)
        sha = cas.sha_file(os.path.join(folder, "plan.json"))
        with open(os.path.join(folder, "record.json"), "w", encoding="utf-8") as handle:
            json.dump(dict({"schema_version": 1, "experiment_id": name, "hypothesis_id": "CODEX-H9", "status": "failed",
                            "started_at": "2030-01-01T00:00:00+00:00", "command": ["python", "-m", "card_condition.worker"],
                            "files": {"plan.json": sha}, "source_hashes": {"code.py": code or cas.sha_file(os.path.join(src, "code.py"))}},
                           **(record or {})), handle)
        return folder

    def test_d4_unverifiable_records_wait_and_records_outside_the_harness_are_compared(self):
        root, src, head = kit.world(self)
        fail = queue.enqueue(root, kit.control(head, value=0.8, hid="F"), kit.NOW, source_root=src)
        runner.drain(root, kit.EXECUTORS, source_root=src)
        with open(os.path.join(root, "tasks", fail, "contract.json"), "w", encoding="utf-8") as handle:
            handle.write("{깨짐")  # 1: 실패 실험의 계약 손상(CORRUPT)
        got = self._chain({"over": {"value": 0.8}}, world=(root, src, head))
        self.assertTrue((got["reason"] or "").startswith("waiting") and "비교할 수 없는 등록 기록" in got["reason"], got["reason"])
        root, src, h0 = kit.world(self)  # 2: 실패 실험의 커밋 소실(문서만 다른 커밋 X에서 실패 → reset·gc)
        os.makedirs(os.path.join(src, "docs"))
        with open(os.path.join(src, "docs", "note.md"), "w", encoding="utf-8") as handle:
            handle.write("메모\n")
        git(src, "add", "docs")
        git(src, "commit", "-q", "-m", "docs")
        queue.enqueue(root, kit.control(git(src, "rev-parse", "HEAD"), value=0.8, hid="F"), kit.NOW, source_root=src)
        runner.drain(root, kit.EXECUTORS, source_root=src)
        for args in (("reset", "-q", "--hard", h0), ("reflog", "expire", "--expire=now", "--all"), ("gc", "-q", "--prune=now")):
            git(src, *args)
        got = self._chain({"over": {"value": 0.8}}, world=(root, src, h0))
        self.assertTrue((got["reason"] or "").startswith("waiting") and "비교할 수 없는 등록 기록" in got["reason"], got["reason"])
        root, src, head = kit.world(self)  # 3: 하네스 밖 ./experiment 실패 기록만 있는 같은 실행 조건(가설 ID·문구 무관)
        self._record(src, "20300102T000000-0badc0de")
        got = self._refused("artifacts/experiments/20300102T000000-0badc0de", spec={"over": {"value": 0.8}}, world=(root, src, head))
        self.assertTrue(got["reason"].startswith("refused: 기각·중복 가설"), got["reason"])
        unknown = "판별할 수 없는 ./experiment 기록"
        for name, kw, after, words in (("20300103T000000-00000001", {"code": "0" * 64}, None, None),  # 코드(source_hashes)가 다르면 다른 실험
                                       ("20300103T000000-00000002", {"value": 0.85}, None, None),  # 값이 다르면 다른 실험
                                       ("20300104T000000-00000003", {"record": {"command": ["python", "-m", "card_condition.other"]}}, None, None),
                                       ("notes", {}, "record.json", None),  # 실험 폴더 이름이 아니고 record.json도 없으면 기록이 아니다
                                       ("20300105T000000-00000004", {}, "record.json", unknown),  # 실험 폴더인데 record.json 없음(prepare 중단 등)
                                       ("20300106T000000-00000005", {}, "plan.json", unknown),  # 기록 뒤에 plan.json이 바뀜(SHA 불일치)
                                       ("20300107T000000-00000006", {"record": {"source_hashes": None}}, None, unknown)):
            root, src, head = kit.world(self)
            folder = self._record(src, name, **kw)
            if after == "record.json":
                os.remove(os.path.join(folder, after))
            elif after:
                with open(os.path.join(folder, after), "w", encoding="utf-8") as handle:
                    json.dump({"tampered": True}, handle)
            got = self._chain({"over": {"value": 0.8}}, world=(root, src, head))
            if words is None:
                self.assertIsNone(got["reason"], name)
            else:
                self.assertTrue((got["reason"] or "").startswith("waiting") and words in got["reason"], (name, got["reason"]))

if __name__ == "__main__":
    unittest.main()

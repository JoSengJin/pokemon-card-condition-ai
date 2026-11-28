"""VS3 필수 합성 시험 6·7·8·10과 runner 오염원 변경(나): 예산·우회 차단·중단 재개·대기 중 독립 작업.

- 예산: PLAN_GATE는 실험 예산을 읽기만 하고(한도면 그 계획만 대기) 차감은 실행 직전 runner의 charge(논리 키 멱등) 하나뿐이다.
- 우회: LLM 작업 출력에 직·간접 의존하는 실험 선언은 PLAN_GATE가 만든 계약과 같을 때만 등록된다. 하네스가 만들지 않은 Claude 작업의
  next_plan.json, Claude가 out/에 쓴 다른 파일은 계획으로 보지 않는다.
- 중단: 선언 저장 뒤·등록 전/등록 뒤 SIGKILL, 그 사이 문서 커밋이 있어도 다음 실험은 한 번만 등록된다.
- runner(나): VERIFIED LLM 작업에 의존하는 Python 작업만 실행하고, 미검증·실패 LLM 작업(간접 포함)에 의존하는 작업과 LLM 작업 자체는 실행하지 않는다.
가짜 executor·합성 git 원본만 쓴다(실제 ./experiment·claude·모델 호출 없음).
"""
import functools
import os
import subprocess
import sys
import unittest
from unittest import mock

from harness import contract as ct
from harness import budget, dedupe, graph, lease, opstate, plan_gate, queue, runner, states, supervisor
from harness.jsonio import read_json, write_json
from tests import harness_plan_gate_kit as kit
from tests.test_harness_git_kit import git
from tests.test_harness_runner_kit import WRAPPED_RUNNER, task, write_result
from tests.test_harness_support import REPO, make_contract
from tests.test_harness_supervisor_kit import events

DECLARED = os.path.join("supervisor", "declared.json")
WEEK = 7 * 86400.0
KILL = ("import os, signal, sys\nfrom harness import graph, supervisor\norig = graph.register_missing\n"
        "def hook(*a, **k):\n    if sys.argv[3] == 'before':\n        os.kill(os.getpid(), signal.SIGKILL)\n"
        "    out = orig(*a, **k)\n    os.kill(os.getpid(), signal.SIGKILL)\n"
        "graph.register_missing = hook\nsupervisor.run(sys.argv[1], max_cycles=1, poll_s=0, source_root=sys.argv[2], now_fn=lambda: %r)\n"
        % kit.NOW)


class PlanGateFlowTest(unittest.TestCase):
    def _analysis(self, finish=True, world=None, **plan):
        """대조 실험 VERIFIED → 분석 등록(finish면 적격 next_plan.json으로 완료). (root, src, head, 대조 키, 분석 키)."""
        root, src, head = world or kit.world(self)
        e1 = kit.verified(root, src, kit.control(head, hid=plan.pop("hid", "H1"), **plan))
        [(a1, analyze)] = [(k, c) for k, c in plan_gate.gate(root, {}, kit.NOW, src).items() if c["depends_on"] == [e1]]
        graph.register_missing(root, {a1: analyze}, kit.NOW, source_root=src)
        if finish:
            kit.finish(root, a1, {plan_gate.NEXT_PLAN: kit.proposal(read_json(os.path.join(root, "tasks", e1, "contract.json")))})
        return root, src, head, e1, a1

    def test_budget_exhausted_plan_waits_and_the_gate_never_charges(self):
        root, src, head, e1, a1 = self._analysis()
        for index in range(budget.LIMITS["experiment"][1] - 1):  # 대조 실험 1건 + 19건 = 이번 주 한도
            budget.charge(root, "experiment", 1, kit.NOW, key="other-%d" % index)
        self.assertEqual([c["depends_on"] for c in plan_gate.gate(root, {}, kit.NOW, src).values() if c["task_type"] == "experiment"], [])
        self.assertTrue(read_json(os.path.join(root, graph.REJECTED))["plan:" + a1].startswith("waiting: 이번 주 실험 예산"))
        self.assertEqual(len(events(root, "charge", budget.BUDGET)), 20)  # 계획 관문은 차감하지 않는다
        self.assertNotIn(opstate.BUDGET_EXCEEDED, opstate.load(root)["conditions"])  # 읽기만: 정지 조건을 켜지 않는다
        later = kit.NOW + WEEK  # 다음 주: 예산이 생기면 같은 계획을 등록한다
        for _ in range(2):  # 두 번 돌려도(재시작) 차감은 실행 직전 한 번
            graph.register_missing(root, plan_gate.gate(root, read_json(os.path.join(root, DECLARED)), later, src), later, source_root=src)
            kit.seed(src, "H-next")
            runner.drain(root, kit.EXECUTORS, now_fn=functools.partial(float, later), source_root=src)
        [k2] = [k for k, c in read_json(os.path.join(root, DECLARED)).items() if c["depends_on"] == [a1]]
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", k2)), False), states.VERIFIED)
        charged = [e["data"]["key"] for e in events(root, "charge", budget.BUDGET)]
        self.assertEqual((len(charged), charged.count(dedupe.logical_key(read_json(os.path.join(root, "tasks", k2, "contract.json"))))), (21, 1))

    def test_declarations_bypassing_the_gate_are_not_registered(self):
        root, src, head, e1, a1 = self._analysis()
        write_json(os.path.join(root, "tasks", a1, "out", "declared.json"), {"x": kit.control(head, value=0.99, hid="claude")})  # Claude가 쓴 다른 파일
        user = queue.enqueue(root, make_contract("u", task_type=plan_gate.ANALYZE_TYPE, needs_llm=True, depends_on=[e1],
                                                outputs=(plan_gate.NEXT_PLAN,)), kit.NOW)
        kit.finish(root, user, {plan_gate.NEXT_PLAN: kit.proposal(kit.control(head), value=0.8)})  # 하네스가 만들지 않은 분석(같은 실험에 의존, 입력이 다름)
        helper = make_contract("d", task_type="deterministic", depends_on=[a1])
        forged = dict(kit.control(head, value=0.9, hid="forged"), depends_on=[a1])  # 분석에 의존하지만 PLAN_GATE 파생과 다르다
        indirect = dict(kit.control(head, value=0.95, hid="indirect"), depends_on=[ct.task_key(helper)])
        foreign = dict(kit.control(head, value=0.8, hid="foreign"), depends_on=[user])
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        write_json(os.path.join(root, DECLARED), {ct.task_key(t): t for t in (helper, forged, indirect, foreign)})
        supervisor.run(root, max_cycles=2, poll_s=0, sleep_fn=float, now_fn=functools.partial(float, kit.NOW), source_root=src)
        conditions = {k: c["depends_on"] for k, c in ((k, read_json(os.path.join(root, "tasks", k, "contract.json")))
                                                      for k in os.listdir(os.path.join(root, "tasks"))) if c["task_type"] == "experiment"}
        self.assertEqual(sorted(conditions.values()), [[], [a1]])  # 대조 실험 + PLAN_GATE 파생 하나뿐
        notes = read_json(os.path.join(root, graph.REJECTED))
        for bad in (forged, indirect, foreign):
            self.assertTrue(notes[ct.task_key(bad)].startswith("plan_gate_required"), notes)
        self.assertNotIn("plan:" + user, notes)  # 남의 분석 출력은 계획으로 보지도 않는다

    def test_kill_and_restart_do_not_register_the_next_experiment_twice(self):
        for mode in ("before", "after"):
            root, src, head, e1, a1 = self._analysis()
            done = subprocess.run([sys.executable, "-c", KILL, root, src, mode], cwd=REPO, capture_output=True, text=True, timeout=120)
            self.assertEqual(done.returncode, -9, done.stderr[-500:])
            self.assertTrue([k for k, c in read_json(os.path.join(root, DECLARED)).items() if c["depends_on"] == [a1]], mode)
            if mode == "before":  # 등록 전에 죽은 사이 문서만 바뀐 커밋: 새 HEAD로 다시 파생하고 낡은 선언은 등록하지 않는다
                os.makedirs(os.path.join(src, "docs"), exist_ok=True)
                with open(os.path.join(src, "docs", "while-down.md"), "w", encoding="utf-8") as handle:
                    handle.write("x\n")
                git(src, "add", "docs")
                git(src, "commit", "-q", "-m", "docs while down")
            for _ in range(2):
                supervisor.run(root, max_cycles=1, poll_s=0, now_fn=functools.partial(float, kit.NOW + 1), source_root=src)
            children = [k for k in os.listdir(os.path.join(root, "tasks"))
                        if read_json(os.path.join(root, "tasks", k, "contract.json"))["depends_on"] == [a1]]
            self.assertEqual(len(children), 1, mode)
            self.assertEqual([e["data"]["task_key"] for e in events(root, "enqueued")].count(children[0]), 1, mode)

    def test_unverifiable_plan_waits_while_independent_work_continues(self):
        root, src, head, ex, ax = self._analysis(finish=False, hid="HX", experiment_parameter=None)
        kit.finish(root, ax, {plan_gate.NEXT_PLAN: kit.proposal(kit.control(head))})
        root, src, head, ey, ay = self._analysis(world=(root, src, head), hid="HY")
        indep = queue.enqueue(root, task("I"), kit.NOW)
        marks = os.path.join(os.path.dirname(root), "marks")
        os.makedirs(marks)
        with mock.patch.object(supervisor, "RUNNER", WRAPPED_RUNNER), mock.patch.dict(os.environ, {"HARNESS_MARK_DIR": marks}):
            out = supervisor.run(root, executors="tests.test_harness_executors:EXECUTORS", max_cycles=2, poll_s=0,
                                 sleep_fn=float, now_fn=functools.partial(float, kit.NOW), source_root=src)
        self.assertNotEqual(out["state"], opstate.INTEGRITY_HALT)
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", indep)), False), states.VERIFIED)  # 독립 Python 작업
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        self.assertEqual([k for k, c in tasks.items() if c["depends_on"] == [ax]], [])  # 검증할 수 없는 계획만 대기
        self.assertEqual(len([k for k, c in tasks.items() if c["depends_on"] == [ay]]), 1)  # 독립 계획은 등록
        rejected = [e["data"] for e in events(root, "declaration_rejected") if e["data"]["declaration"] == "plan:" + ax]
        self.assertEqual(len(rejected), 1)  # 회차마다 다시 알리지 않는다
        self.assertTrue(rejected[0]["reason"].startswith("waiting") and "experiment_parameter" in rejected[0]["reason"], rejected)

    def test_runner_runs_dependents_of_verified_llm_tasks_only_and_never_llm_tasks(self):
        root, src, head = kit.world(self)
        done_llm, open_llm, failed_llm = (queue.enqueue(root, make_contract(n, task_type=plan_gate.ANALYZE_TYPE, needs_llm=True, outputs=(n + ".md",)), kit.NOW)
                                          for n in ("l1", "l2", "l3"))
        kit.finish(root, done_llm, {"l1.md": "claude"})
        res = queue.claim(root, failed_llm, os.getpid(), lease.boot_id(), kit.NOW)
        queue.fail(root, failed_llm, res["run_id"], res["lease"], "deterministic", "x", kit.NOW)
        p1, p2, p3 = (queue.enqueue(root, make_contract(n, task_type="calc", depends_on=[d]), kit.NOW)
                      for n, d in (("p1", done_llm), ("p2", open_llm), ("p3", failed_llm)))
        p4 = queue.enqueue(root, make_contract("p4", task_type="calc", depends_on=[p2]), kit.NOW)
        calls = mock.Mock(side_effect=write_result)
        summary = runner.drain(root, {"calc": calls, plan_gate.ANALYZE_TYPE: calls}, source_root=src)
        self.assertEqual((summary["done"], calls.call_count), ([p1], 1))
        self.assertEqual(summary["untouched"]["llm_dependents"], sorted([p2, p3, p4]))
        self.assertEqual(summary["untouched"]["llm"], sorted([done_llm, open_llm, failed_llm]))
        self.assertEqual([e["data"]["task_key"] for e in events(root, "claimed") if e["data"]["task_key"] in (open_llm,)], [])


if __name__ == "__main__":
    unittest.main()

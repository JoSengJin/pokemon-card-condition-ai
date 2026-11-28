"""VS3 필수 합성 시험 1~5: PLAN_GATE의 결정론 검사(변수 하나·사전 등록·기각 가설·명령/입력 고정).

실험 VERIFIED → plan_gate.gate가 ANALYZE 선언 → (Claude 대신 kit.finish가 next_plan.json을 쓰고 완료) → gate가 다음 실험을 만들거나 그 계획만 거절한다.
가짜 실험 executor·합성 git 원본만 쓴다(실제 ./experiment·claude·모델 호출 없음). 합성 통과는 모델 성능 근거가 아니다.
제안 변형은 사양 dict로 준다: over(kit.proposal 인자), extra(최상위 키 추가), plan_extra(plan 키 추가), param(experiment_parameter 값 덮어쓰기), raw(글자 그대로).
"""
import json
import os
import unittest

from harness import contract as ct
from harness import graph, plan_gate, queue, runner, states
from harness.jsonio import read_json
from tests import harness_plan_gate_kit as kit
from tests.test_harness_git_kit import git
from tests.test_harness_supervisor_kit import events

DECLARED = os.path.join("supervisor", "declared.json")


class PlanGateTest(unittest.TestCase):
    def _chain(self, spec=None, plan=None, fail=None, world=None, parent_key=None, edit=None):
        """대조 실험 VERIFIED → 분석 등록 → 사양대로 쓴 next_plan.json 완료 → gate. fail: 같은 조건·그 값의 실패 실험을 먼저 만든다.
        world·parent_key를 주면 그 root의 VERIFIED 실험을 대조로 쓴다. edit=(추적 파일, 내용, 커밋 여부): 마지막 gate 전에 원본 코드를 바꾼다.
        dict(root, src, parent, analyze, out, reason)."""
        root, src, head = world or kit.world(self)
        if parent_key is None:
            parent_key = kit.verified(root, src, kit.control(head, **(plan or {})))
        if fail is not None:
            queue.enqueue(root, kit.control(head, value=fail, hid="F"), kit.NOW, source_root=src)
            runner.drain(root, kit.EXECUTORS, source_root=src)  # F는 심은 기록이 없어 실패한다
        first = plan_gate.gate(root, {}, kit.NOW, src)
        [a1] = [k for k, c in first.items() if c["depends_on"] == [parent_key]]
        graph.register_missing(root, {a1: first[a1]}, kit.NOW, source_root=src)
        spec, parent = spec or {}, read_json(os.path.join(root, "tasks", parent_key, "contract.json"))
        body = spec.get("raw")
        if body is None:
            body = kit.proposal(parent, **spec.get("over", {}))
            body.update(spec.get("extra", {}))
            body["plan"].update(spec.get("plan_extra", {}))
            body["plan"]["experiment_parameter"].update(spec.get("param", {}))
        kit.finish(root, a1, {plan_gate.NEXT_PLAN: body})
        if edit:
            with open(os.path.join(src, edit[0]), "a", encoding="utf-8") as handle:
                handle.write(edit[1])
            if edit[2]:
                git(src, "commit", "-q", "-am", "code change")
        out = plan_gate.gate(root, read_json(os.path.join(root, DECLARED)), kit.NOW, src)
        reason = (read_json(os.path.join(root, graph.REJECTED), {}) or {}).get("plan:" + a1)
        return {"root": root, "src": src, "head": head, "parent": parent_key, "analyze": a1, "out": out, "reason": reason}

    def _refused(self, words, **chain):
        got = self._chain(**chain)
        self.assertTrue(got["reason"] and got["reason"].startswith("refused") and words in got["reason"], (chain, got["reason"]))
        self.assertEqual([k for k, c in got["out"].items() if got["analyze"] in c["depends_on"]], [])  # 그 분석에서 나온 선언 없음
        return got

    def test_eligible_single_variable_plan_is_declared_registered_and_runs_with_its_lineage(self):
        got = self._chain()
        root, src, out, a1 = got["root"], got["src"], got["out"], got["analyze"]
        self.assertIsNone(got["reason"])
        [(k2, e2)] = [(k, c) for k, c in out.items() if c["depends_on"] == [a1]]
        parent = read_json(os.path.join(root, "tasks", got["parent"], "contract.json"))
        cond, base = e2["run_conditions"], parent["run_conditions"]
        self.assertEqual(plan_gate._diff(base["config"], cond["config"]), [("plan", "experiment_parameter", "value")])
        self.assertEqual(cond["config"]["plan"]["experiment_parameter"]["value"], 0.7)
        self.assertEqual((cond["command"], cond["seed"], e2["inputs"], e2["outputs"]), (base["command"], base["seed"], parent["inputs"],
                                                                                         parent["outputs"]))
        self.assertEqual(cond["code_sha"], git(src, "rev-parse", "HEAD"))  # 결정론 코드가 정한 코드(Claude 아님)
        self.assertEqual({k: cond["description"][k] for k in ("success_criterion", "failure_criterion")},
                         {k: base["description"][k] for k in ("success_criterion", "failure_criterion")})  # 기준 문구는 대조 그대로
        self.assertIn(k2, read_json(os.path.join(root, DECLARED)))
        self.assertEqual(sorted(e["data"]["task_type"] for e in events(root, "plan_gate_declared")), ["experiment", plan_gate.ANALYZE_TYPE])
        self.assertEqual(graph.register_missing(root, out, kit.NOW, source_root=src)["registered"], [k2])
        kit.seed(src, "H-next")
        runner.drain(root, kit.EXECUTORS, source_root=src)  # VERIFIED 분석에 의존하는 실험은 실행된다(runner 오염원 변경 (나))
        self.assertEqual(states.state_of(states.facts(os.path.join(root, "tasks", k2)), False), states.VERIFIED)
        again = plan_gate.gate(root, read_json(os.path.join(root, DECLARED)), kit.NOW, src)
        self.assertEqual([c["depends_on"] for c in again.values() if c["task_type"] == plan_gate.ANALYZE_TYPE and k2 in c["depends_on"]], [[k2]])
        self.assertEqual(len([e for e in events(root, "plan_gate_declared") if e["data"]["depends_on"] == [a1]]), 1)  # 다시 파생하지 않는다

    def test_multiple_variables_or_a_false_single_variable_declaration_are_refused(self):
        for spec in ({"param": {"baseline": 0.6}}, {"plan_extra": {"extra_knob": 3}}, {"over": {"variable": "experiment_parameter.baseline"}},
                     {"over": {"value": 0.6}, "plan_extra": {"experiment_parameter.value": 0.7}},  # 점이 든 키로 승인 변수 위장
                     {"over": {"value": 0.6}}, {"over": {"variable": "lr 하나만 바꿈(자기 선언)"}}):
            self._refused("변수 하나", spec=spec)
        for value in (True, "0.7", float("nan")):  # 자료형이 다른 값·NaN은 숫자 변수 하나가 아니다
            self._refused("유한한 숫자", spec={"over": {"value": value}})
        text = json.dumps(kit.proposal(kit.control("0" * 40))).replace("0.7", "1" + "0" * 5000)  # 거대 정수(읽을 때 NaN)
        self._refused("유한한 숫자", spec={"raw": text})
        for edit, words in ((("code.py", "LR = 2\n", True), "두 번째 변수"), (("code.py", "LR = 3\n", False), "추적 파일 변경")):
            got = self._chain(edit=edit)  # 코드가 바뀌면(커밋·미커밋) 변수 하나를 확인할 수 없다: 그 계획만 대기
            self.assertTrue(got["reason"].startswith("waiting") and words in got["reason"], got["reason"])

    def test_unapproved_command_arguments_or_inputs_are_refused(self):
        for extra in ({"command": ["python", "evil.py"]}, {"inputs": {"data/other.json": "a" * 64}}, {"run_conditions": {}},
                      {"depends_on": []}, {"seed": 2}, {"task_type": "deterministic"}, {"code_sha": "b" * 40}):
            self._refused("만(문구는", spec={"extra": extra})
        for key, value in (("command", ["python", "evil.py"]), ("extra_args", ["--epochs", "99"]), ("worker", "evil.py"),
                           ("code_changes", [{"path": "card_condition/other.py", "baseline": None}])):
            self._refused("변수 하나", spec={"plan_extra": {key: value}})

    def test_rejected_hypothesis_with_a_new_id_or_description_is_refused_even_after_a_docs_commit(self):
        got = self._refused("기각·중복 가설", spec={"over": {"value": 0.9, "hypothesis_id": "H-new", "hypothesis": "다른 설명"}}, fail=0.9)
        failed = ct.task_key(kit.control(got["head"], value=0.9, hid="F"))
        self.assertEqual(states.state_of(states.facts(os.path.join(got["root"], "tasks", failed)), False), states.FAILED)
        self.assertIn(failed, got["reason"])
        got = self._chain()  # 0.6(완료) → 0.7(실행) 다음에 0.6으로 되돌리는 제안 = 완료된 대조와 같은 실행 조건
        root, src = got["root"], got["src"]
        graph.register_missing(root, got["out"], kit.NOW, source_root=src)
        kit.seed(src, "H-next")
        runner.drain(root, kit.EXECUTORS, source_root=src)
        os.makedirs(os.path.join(src, "docs"), exist_ok=True)
        with open(os.path.join(src, "docs", "note.md"), "w", encoding="utf-8") as handle:
            handle.write("문서만 바뀐 커밋\n")
        git(src, "add", "docs/note.md")
        git(src, "commit", "-q", "-m", "docs only")
        [k2] = [k for k, c in got["out"].items() if c["depends_on"] == [got["analyze"]]]
        again = self._chain({"over": {"value": 0.6, "hypothesis_id": "H-renamed", "change": "다른 문구"}},
                            world=(root, src, got["head"]), parent_key=k2)
        self.assertTrue(again["reason"].startswith("refused: 기각·중복 가설") and got["parent"] in again["reason"], again["reason"])
        self.assertNotIn("plan:" + got["analyze"], read_json(os.path.join(root, graph.REJECTED)))  # 이미 다음 실험을 낸 분석은 다시 보지 않는다

    def test_evaluation_data_and_success_criteria_cannot_be_changed_by_the_plan(self):
        for key, value in (("reference_result", "artifacts/ref/other.json"), ("acceptance", dict(kit.ACCEPT, max_fn=5)),
                           ("acceptance", dict(kit.ACCEPT, no_new_errors=False)), ("acceptance", dict(kit.ACCEPT, max_fn=2.0)),  # 값은 같고 자료형만 다름(2 → 2.0)
                           ("required_cohorts", []), ("threshold", 0.4),
                           ("independent", True)):
            self._refused("변수 하나", spec={"plan_extra": {key: value}})
        for key in ("success_criterion", "failure_criterion", "description"):
            self._refused("만(문구는", spec={"extra": {key: "fn<=99"}})
        got = self._chain({"raw": json.dumps(kit.proposal(kit.control("0" * 40)))}, plan={"experiment_parameter": None})  # 대조에 승인 변수 없음: 대기
        self.assertTrue(got["reason"].startswith("waiting") and "experiment_parameter" in got["reason"], got["reason"])


if __name__ == "__main__":
    unittest.main()

"""ANALYZE 입력 형식 안내: 실제 Claude가 PLAN_GATE를 통과하는 next_plan.json을 쓰려면 프롬프트가 형식·대조 계획 위치를 알려야 한다.
(a) claude_job._prompt는 ANALYZE 작업에만 plan_gate 상수에서 만든 형식 설명을 붙이고 다른 유형은 기존 문구 그대로다.
(b) 연결(C): 가짜 claude가 **프롬프트의 형식 설명만** 읽고 next_plan.json을 만들어 `python -m harness.supervisor` 1회 실행에서
    PLAN_GATE 통과 → 다음 실험 선언 등록까지 이어진다. 실제 claude·모델·./experiment 없음(합성). 실환경 성공 근거가 아니다.
"""
import ast
import json
import os
import re
import subprocess
import sys
import unittest

from harness import claude_job, experiment_exec, plan_gate, sandbox, states
from harness import contract as ct
from harness.jsonio import read_json, write_json
from tests import harness_plan_gate_kit as kit
from tests.test_harness_support import REPO
from tests.test_harness_supervisor_kit import events, make_fake, runs

EID = "20300101T000000-0123abcd"
INPUTS = {"artifacts/experiments/%s/%s" % (EID, n): "0" * 64 for n in ("record.json", "result.json", "plan.json")}
OLD = ("하네스 작업 %s를 수행한다.\n실행 토큰: %s\n계약 파일: %s\n산출물 폴더: %s\n계약의 outputs를 산출물 폴더에 쓴다.\n"
       "규칙(프로젝트 지침이 로드되지 않을 수 있어 여기에 적는다):\n"
       "1. 이 작업 폴더 안의 파일만 읽는다. 계약 입력은 in/ 아래 복사본만 쓴다.\n"
       "2. 쓰기는 산출물 폴더 아래에만 한다. 하네스 상태(장부·작업권·완료 기록·운영 상태·예산)를 고치려 하지 않는다.\n"
       "3. 명령 실행·외부 호출·하위 에이전트·MCP를 쓰지 않는다. 사람 라벨·Gold·봉인 자료를 만들거나 고치지 않는다.\n"
       "4. outputs를 모두 쓴 뒤 맨 마지막에 산출물 폴더의 %s 파일에 JSON {\"task_key\": \"%s\", \"run_token\": \"%s\","
       " \"outputs\": [outputs 경로 목록]}을 쓴다. 그 뒤에는 산출물을 고치지 않는다.")
# 가짜 claude가 프롬프트 글만으로 next_plan.json을 만드는 코드(가짜 claude 파일 앞부분에 붙인다). 정규식은 프롬프트 형식 설명의 글을 읽는다.
HELPER = r'''
def _from_prompt(prompt):
    keys = re.search(r"- 키: (.+?) \(이 키만", prompt).group(1).split(", ")
    var = re.search(r"- 변수: (\S+) 하나만", prompt).group(1)
    copy, drop = re.search(r"대조 계획 사본 (\S+) 을 읽어 키 (.+?) 를 뺀", prompt).groups()
    plan = json.load(open(copy))
    for name in drop.split(", "):
        plan.pop(name, None)
    first, second = var.split(".")
    plan[first][second] = round(plan[first][second] + 0.1, 6)
    return json.dumps(dict(zip(keys, ["H-next", "lr를 더 올리면 누락이 준다", "lr 0.6→0.7", var, plan])))
'''
WRITE = 'open(os.path.join(out_dir, rel), "w").write("claude:" + session)'
FROM_PROMPT = 'open(os.path.join(out_dir, rel), "w").write(_from_prompt(argv[1]) if rel == "next_plan.json" else "claude:" + session)'


def _prompt(task_type):
    job = {"task_key": "a" * 64, "run_token": "b" * 32}
    return claude_job._prompt("/r", job, "new", {"task_type": task_type, "inputs": INPUTS, "outputs": [plan_gate.NEXT_PLAN]}), job


def _entry(case):
    """합성 root에서 `python -m harness.supervisor` 1회 실행(프롬프트만 읽는 가짜 claude). (root, 가짜 claude 로그, 실행 결과, 대조 계약)."""
    root, src, head = kit.world(case)
    control = kit.control(head)
    kit.seed(src, "H1", plan=dict(experiment_exec.build_plan(control), **plan_gate._FROZEN))  # 하네스가 보는 ./experiment 동결 plan.json 모양
    kit.seed(src, "H-next")
    write_json(os.path.join(root, "supervisor", "declared.json"), {ct.task_key(control): control})
    path, log, _ = make_fake(case, [{"do": "success"}])
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    case.assertIn(WRITE, text)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text.replace(WRITE, FROM_PROMPT).replace("\ndef note(", HELPER + "def note(", 1))
    done = subprocess.run([sys.executable, "-m", "harness.supervisor", "--root", root, "--claude-bin", path, "--executors",
                           "tests.harness_plan_gate_kit:EXECUTORS", "--source-root", src, "--max-cycles", "3", "--poll", "0"],
                          cwd=REPO, capture_output=True, text=True, timeout=600)
    return root, log, done, control


class AnalyzePromptTest(unittest.TestCase):
    def test_analyze_prompt_states_the_plan_format_and_the_control_copy_location(self):
        text, job = _prompt(plan_gate.ANALYZE_TYPE)
        for key in plan_gate.PLAN_KEYS + plan_gate.PARAM_KEYS[2:3] + experiment_exec.TEXT_KEYS + tuple(plan_gate._FROZEN):
            self.assertIn(key, text)
        self.assertIn(".".join(plan_gate.VARIABLE), text)
        self.assertIn("in/artifacts/experiments/%s/plan.json" % EID, text)  # record·result 사본이 아니라 plan.json 사본
        self.assertNotIn("in/artifacts/experiments/%s/record.json" % EID, text)
        self.assertTrue(text.startswith("하네스 작업 " + job["task_key"]))

    def test_other_task_types_keep_the_old_prompt_byte_for_byte(self):
        for task_type in ("experiment", "label_review", "unknown_type"):
            text, job = _prompt(task_type)
            self.assertEqual(text, OLD % (job["task_key"], job["run_token"], "/r/tasks/%s/contract.json" % job["task_key"],
                                          "/r/tasks/%s/out" % job["task_key"], ct.DECLARATION, job["task_key"], job["run_token"]))


class AnalyzeEntryTest(unittest.TestCase):
    def test_prompt_only_fake_claude_passes_the_gate_and_registers_the_next_experiment_through_the_entry_point(self):
        if not sandbox.available():
            self.skipTest("sandbox-exec 없음")
        root, log, done, control = _entry(self)
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        tasks = {k: read_json(os.path.join(root, "tasks", k, "contract.json")) for k in os.listdir(os.path.join(root, "tasks"))}
        [a1] = [k for k, c in tasks.items() if c["task_type"] == plan_gate.ANALYZE_TYPE]
        [e2] = [k for k, c in tasks.items() if c["depends_on"] == [a1]]
        sent = runs(log)[0]["prompt"]
        self.assertIn("대조 계획 사본 in/artifacts/experiments/", sent)
        self.assertEqual(tasks[e2]["run_conditions"]["config"]["plan"]["experiment_parameter"]["value"], 0.7)
        self.assertEqual(sorted(e["data"]["task_type"] for e in events(root, "plan_gate_declared")), ["experiment", plan_gate.ANALYZE_TYPE])
        self.assertEqual(events(root, "declaration_rejected"), [])
        self.assertEqual({states.state_of(states.facts(os.path.join(root, "tasks", k)), False) for k in (ct.task_key(control), a1, e2)}, {states.VERIFIED})

    def test_structure_function_counts(self):
        for rel in ("harness/claude_job.py", "tests/test_harness_analyze_input.py"):
            with open(os.path.join(REPO, rel), encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
            self.assertLessEqual(sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) for n in ast.walk(tree)), 7, rel)


if __name__ == "__main__":
    unittest.main()

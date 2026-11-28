"""B5-8: ./experiment 실행 어댑터 합성 시험. 실제 ./experiment·./develop 잠금·저장소 artifacts/는 쓰지 않는다.

임시 git 저장소에 가짜 `experiment` 스크립트(계획 JSON을 받아 record.json을 쓰고 종료 코드 0/1/2/130 등을 내는 것)를 커밋해 두고 어댑터가
그것을 부르는 경로만 본다. 실제 연결은 미완료다(사용자 결정 2026-11-28: 합성까지, 기존 sandbox 원칙 유지). 합성 통과는 실제 실험 실행·
다음 가설 생성 검증이 아니고 모델 성능 근거도 아니다.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from harness import claude_perm, experiment_exec, queue, recovery

FAKE = r'''#!%(python)s
import hashlib, json, os, sys, time, uuid
args = sys.argv[1:]
split = args.index("--")
opts, cmd = args[:split], args[split + 1:]  # argparse REMAINDER처럼: "--" 앞만 옵션
plan = json.load(open(opts[opts.index("--plan") + 1]))
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(os.path.join(here, "artifacts"), exist_ok=True)
with open(os.path.join(here, "artifacts", "argv.log"), "a") as log:
    log.write(json.dumps({"opts": opts, "cmd": cmd, "plan": plan}) + "\n")
mode = plan["fake"]
if mode == "busy":
    print("다른 개발·실험·검토가 진행 중입니다. 새 실험을 실행하지 않았습니다."); sys.exit(1)
if mode == "setup":
    print("실험 계획·기준 결과·코드 경로를 확인하세요. 원문 오류는 출력하지 않습니다."); sys.exit(2)
if mode == "sleep":
    time.sleep(30)
if mode == "quiet_fail":
    sys.exit(1)  # 안내문·기록 줄 없는 1: 실행됐는지 알 수 없다
folder = os.path.join(here, "artifacts", "experiments", "x-" + uuid.uuid4().hex[:8])
os.makedirs(folder)
status = {"completed": "completed", "failed": "failed", "failed_with_result": "failed", "interrupted": "interrupted", "lie_code": "failed", "running": "running",
          "escape": "completed", "tamper": "completed", "other_cmd": "completed", "no_line": "completed", "killed": "running"}[mode]
files = {}
if status == "completed" or mode == "failed_with_result":
    with open(os.path.join(folder, "result.json"), "w") as h:
        json.dump({"acceptance_passed": False, "hypothesis_id": plan["hypothesis_id"]}, h)
    files["result.json"] = hashlib.sha256(open(os.path.join(folder, "result.json"), "rb").read()).hexdigest()
    if mode == "tamper":
        open(os.path.join(folder, "result.json"), "a").write(" ")
record = {"schema_version": 1, "experiment_id": os.path.basename(folder), "hypothesis_id": plan["hypothesis_id"], "status": status,
          "command": cmd + (["--x"] if mode == "other_cmd" else []), "files": files}
path = os.path.join(folder, "record.json")
if mode == "escape":  # 실험 폴더 밖의 완결된 기록(result.json 포함)을 가리킨다
    os.makedirs(os.path.join(here, "..", "outside"), exist_ok=True)
    os.replace(os.path.join(folder, "result.json"), os.path.join(here, "..", "outside", "result.json"))
    path = os.path.join(here, "..", "outside", "record.json")
json.dump(record, open(path, "w"))
if mode == "killed":
    os.kill(os.getpid(), 9)
if mode != "no_line":
    print("실험 기록:", path, "/ 상태:", status)
sys.exit({"completed": 0, "failed": 1, "failed_with_result": 0, "interrupted": 130, "lie_code": 0, "running": 0, "escape": 0, "tamper": 0, "other_cmd": 0,
          "no_line": 0}[mode])
'''


class ExperimentExecTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp(prefix="b5-exp-")
        self.addCleanup(shutil.rmtree, self.base, True)
        self.repo = os.path.join(self.base, "repo")
        os.makedirs(self.repo)
        with open(os.path.join(self.repo, "experiment"), "w", encoding="utf-8") as handle:
            handle.write(FAKE % {"python": sys.executable})
        os.chmod(os.path.join(self.repo, "experiment"), 0o755)
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as handle:
            handle.write("artifacts/\n")
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]
        for step in (["init", "-q"], ["add", "-A"], ["commit", "-q", "-m", "fake"]):
            subprocess.run(git + step, check=True, capture_output=True)
        self.head = subprocess.run(git + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()

    def task(self, mode="completed", hypothesis="H-1", text="가설 설명", plan=None, code_sha=None, command=None):
        return {"task_type": "experiment", "inputs": {}, "outputs": list(experiment_exec.OUTPUTS), "depends_on": [], "needs_llm": False,
                "needs_vision": False, "risk": "high", "retry_policy": {}, "escalation_level": 0,
                "run_conditions": {"command": command or ["python", "-m", "card_condition.fake", "--seed", "1"],
                                   "code_sha": code_sha or self.head, "config": {"plan": plan or {"fake": mode, "reference_result": "r.json",
                                                                                               "acceptance": {"max_fn": 1}}},
                                   "hypothesis_id": hypothesis,
                                   "description": {"hypothesis": text, "change": "변수 하나", "success_criterion": "fn<=1",
                                                   "failure_criterion": "fn>1"}}}

    def outcome(self, task, timeout=20):
        """(종류, 상태) — 완료면 ("done", 출력 목록)."""
        out = os.path.join(self.base, "out-" + os.urandom(4).hex())
        try:
            return "done", experiment_exec.run(task, out, self.repo, timeout=timeout)
        except experiment_exec.ExperimentError as exc:
            return exc.args[0], exc.args[1]

    def test_plan_comes_only_from_the_contract_and_command_stays_after_separator(self):
        task = self.task(command=["python", "run.py", "--plan", "/evil.json", "--", "x"])  # 명령 안 --plan은 "--" 뒤라 옵션이 아니다
        kind, produced = self.outcome(task)
        self.assertEqual((kind, sorted(produced)), ("done", sorted(experiment_exec.OUTPUTS)))
        with open(os.path.join(self.repo, "artifacts", "argv.log"), encoding="utf-8") as handle:
            [seen] = [json.loads(line) for line in handle]
        self.assertEqual((len(seen["opts"]), seen["opts"][0], seen["cmd"]), (2, "--plan", task["run_conditions"]["command"]))
        self.assertEqual(seen["plan"], {"fake": "completed", "reference_result": "r.json", "acceptance": {"max_fn": 1}, "hypothesis_id": "H-1",
                                        "hypothesis": "가설 설명", "change": "변수 하나", "success_criterion": "fn<=1", "failure_criterion": "fn>1"})
        bad = {"override": self.task(plan={"fake": "completed", "hypothesis_id": "H-9"}), "no_plan": dict(self.task(), run_conditions=dict(
            self.task()["run_conditions"], config={})), "no_text": dict(self.task(), run_conditions=dict(self.task()["run_conditions"], description={})),
            "outputs": dict(self.task(), outputs=["record.json"]), "type": dict(self.task(), task_type="training")}
        for name, contract in bad.items():
            self.assertEqual(self.outcome(contract)[0], "deterministic", name)
        with open(os.path.join(self.repo, "artifacts", "argv.log"), encoding="utf-8") as handle:
            self.assertEqual(len(handle.read().splitlines()), 1, "거절한 계약은 실행하지 않는다")

    def test_exit_code_and_record_status_must_agree(self):
        want = {"completed": "done", "failed": "deterministic", "failed_with_result": "interrupted", "quiet_fail": "interrupted", "interrupted": "interrupted", "busy": "deterministic", "setup": "deterministic",
                "lie_code": "interrupted", "running": "interrupted", "escape": "interrupted", "tamper": "interrupted", "other_cmd": "interrupted",
                "no_line": "interrupted", "killed": "interrupted", "sleep": "interrupted"}
        for mode, kind in want.items():
            got = self.outcome(self.task(mode, hypothesis="H-" + mode), timeout=3 if mode == "sleep" else 20)
            self.assertEqual(got[0], kind, (mode, got))
            if mode in ("busy", "setup"):
                self.assertEqual(got[1]["status"], "not_started")  # 실행되지 않았음이 객관적으로 확인된 경우만(예산 취소 후보)
            elif kind == "interrupted":
                self.assertIn(got[1]["status"], ("interrupted", "unknown"), mode)  # 결과 불명: 자동 재실행 대상 아님
            if mode in ("tamper", "failed_with_result"):  # 해석 단계만으로도 해시·상태 불일치를 거절한다(복사 뒤 재대조와 별개)
                line = "실험 기록: %s / 상태: %s" % (os.path.join(got[1]["experiment_dir"], "record.json"),
                                                  "completed" if mode == "tamper" else "failed")
                cmd = self.task()["run_conditions"]["command"]
                self.assertEqual(experiment_exec.interpret(0, line, self.repo, cmd, "H-" + mode)[0], "unknown", mode)

    def test_code_sha_mismatch_or_dirty_tree_is_refused_before_running(self):
        self.assertEqual(self.outcome(self.task(code_sha="0" * 40))[0], "deterministic")
        with open(os.path.join(self.repo, ".gitignore"), "a", encoding="utf-8") as handle:
            handle.write("# 추적 파일 변경\n")
        self.assertEqual(self.outcome(self.task())[0], "deterministic")
        self.assertFalse(os.path.exists(os.path.join(self.repo, "artifacts", "argv.log")))

    def test_same_conditions_with_other_wording_are_one_experiment_and_nothing_auto_reruns(self):
        root = os.path.join(self.base, "harness-root")
        first = queue.enqueue(root, self.task(), 1.0, source_root=self.repo)
        with self.assertRaises(queue.DuplicateTask):  # 가설 ID·설명 문구만 다르면 같은 실험
            queue.enqueue(root, self.task(hypothesis="H-2", text="다른 문구"), 2.0, source_root=self.repo)
        other = queue.enqueue(root, self.task(plan={"fake": "completed", "reference_result": "r.json", "acceptance": {"max_fn": 2}}), 3.0,
                              source_root=self.repo)  # 수치 기준이 다르면 다른 실험
        self.assertNotEqual(first, other)
        self.assertNotIn("experiment", recovery.RERUN_SAFE_TYPES)
        self.assertEqual((recovery.RERUN_SAFE_TYPES, claude_perm.AUTO_RESUME), (frozenset(), {}))


if __name__ == "__main__":
    unittest.main()

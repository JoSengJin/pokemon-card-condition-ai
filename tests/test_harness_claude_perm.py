"""3단계 Claude 권한의 코드 강제(가짜 claude = 실제 하위 프로세스): 유형 → 묶음은 코드가 정하고 A만 실행, A 옵션·작업 폴더 cwd·허용 env,
자동 재개 활성화 목록은 비어 있어 한도 뒤 재개하지 않음(첫 실행은 허용, 증거 해시가 틀리면 꺼짐), 계약 입력은 SHA 확인 복사만.
CLI 옵션의 실제 효과는 실환경 미확인이다(이 시험은 하네스가 넘기는 인자와 차단 판단만 본다)."""
import hashlib
import os
import tempfile
import unittest
from unittest import mock

from harness import claude_job, claude_perm, queue, states, supervisor
from harness.jsonio import read_json
from tests.test_harness_support import make_contract
from tests.test_harness_supervisor_kit import llm_task, make_fake, runs


def queue_state(root, key):
    return states.state_of(states.facts(os.path.join(root, "tasks", key)), False)


class ClaudePermissionTest(unittest.TestCase):
    def test_only_bundle_a_runs_and_gets_the_restricted_options_cwd_and_env(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success"}] * 4)
        held = {t: llm_task(root, task_type=t) for t in ("label_disagreement", "general_dev", "unknown_type")}
        ok = llm_task(root, task_type="experiment_log_summary")
        out = supervisor.run(root, claude, max_cycles=6, poll_s=0.01, env=dict(env, ANTHROPIC_API_KEY="sk-test-secret"))
        [run] = runs(log)  # B·C·묶음 없는 유형은 claude를 부르지 않았다
        self.assertEqual((queue_state(root, ok), sorted(out["outcomes"])), (states.VERIFIED, ["blocked"] * 3 + ["done"]))
        for name, key in held.items():
            self.assertIn("no_runnable_permission_bundle", read_json(claude_job.paths(root, key)[0])["hold_reason"], name)
        argv = run["argv"]
        self.assertEqual(argv[argv.index("--effort") + 2:-2], list(claude_perm.A_OPTIONS))  # 모델·effort 뒤, 세션 인자 앞
        self.assertNotIn("Bash", " ".join(argv[3:]))
        self.assertEqual(os.path.realpath(run["cwd"]), os.path.realpath(os.path.join(root, "tasks", ok)))
        self.assertLessEqual(set(run["env"]), set(claude_perm.ENV_ALLOW) | {"__CF_USER_TEXT_ENCODING"})  # macOS가 붙이는 값 제외
        self.assertNotIn("ANTHROPIC_API_KEY", run["env"])

    def test_auto_resume_is_off_by_default_so_rate_limit_waits_but_first_runs_continue(self):
        root = tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "limit", "after": 1}, {"do": "success"}])
        first = llm_task(root)
        supervisor.run(root, claude, max_cycles=1, env=env)
        other = llm_task(root, task_type="experiment_log_summary")
        out = supervisor.run(root, claude, max_cycles=6, poll_s=1.5, env=env)
        self.assertEqual([r["resume"] for r in runs(log)], [None, None])  # 재개 없음, 독립 작업의 첫 실행은 했다
        self.assertEqual((queue_state(root, first), queue_state(root, other)), (states.PENDING, states.VERIFIED))
        self.assertIn("auto_resume_disabled", read_json(claude_job.paths(root, first)[0])["hold_reason"])
        self.assertIn("blocked", out["outcomes"])
        self.assertEqual(claude_perm.AUTO_RESUME, {})
        evidence = os.path.join(tempfile.mkdtemp(), "e.txt")
        with open(evidence, "w") as handle:
            handle.write("x")
        with mock.patch.dict(claude_perm.AUTO_RESUME, {"misanalysis_general": {"evidence": evidence, "sha256": "0" * 64}}):
            self.assertFalse(claude_perm.auto_resume_allowed("misanalysis_general"))  # 증거 해시가 틀리면 꺼진 것으로 본다
        good = {"evidence": evidence, "sha256": hashlib.sha256(b"x").hexdigest()}
        with mock.patch.dict(claude_perm.AUTO_RESUME, {"misanalysis_general": good}):
            self.assertTrue(claude_perm.auto_resume_allowed("misanalysis_general"))

    def test_contract_inputs_are_copied_only_after_sha_and_path_checks(self):
        source, harness_root = tempfile.mkdtemp(), tempfile.mkdtemp()
        os.makedirs(os.path.join(source, "logs"))
        with open(os.path.join(source, "logs", "a.txt"), "wb") as handle:
            handle.write(b"log")
        sha = hashlib.sha256(b"log").hexdigest()
        os.symlink(os.path.join(source, "logs", "a.txt"), os.path.join(source, "link.txt"))
        task_dir = os.path.join(harness_root, "tasks", "k")
        self.assertEqual(claude_perm.stage_inputs(task_dir, {"inputs": {"logs/a.txt": sha}}, source, harness_root), ["logs/a.txt"])
        with open(os.path.join(task_dir, "in", "logs", "a.txt"), "rb") as handle:
            self.assertEqual(handle.read(), b"log")
        bad = [{"logs/a.txt": "0" * 64}, {"link.txt": sha}, {"../x": sha}, {"/etc/hosts": sha}, {"gold/a.txt": sha},
               {"data/Sealed-v1/a.txt": sha}, {"missing.txt": sha}]
        for inputs in bad:
            with self.assertRaises(ValueError, msg=inputs):
                claude_perm.stage_inputs(task_dir, {"inputs": inputs}, source, harness_root)
        with self.assertRaises(ValueError):  # 하네스 root 안의 파일(운영 상태 등)은 원본 폴더 안이어도 복사하지 않는다
            claude_perm.stage_inputs(task_dir, {"inputs": {"in/logs/a.txt": sha}}, harness_root + "/tasks/k", harness_root)

    def test_refused_input_fails_the_task_without_running_claude(self):
        root, source = tempfile.mkdtemp(), tempfile.mkdtemp()
        claude, log, env = make_fake(self, [{"do": "success"}])
        task = dict(make_contract("i", task_type="misanalysis_general", needs_llm=True), inputs={"gold/answers.json": "a" * 64})
        key = queue.enqueue(root, task, 1.0)
        out = supervisor.run(root, claude, max_cycles=2, poll_s=0.01, env=env, source_root=source)
        self.assertEqual((runs(log), out["outcomes"], queue_state(root, key)), ([], ["failed"], states.FAILED))
        self.assertIn("input_refused", states.failures(os.path.join(root, "tasks", key))[0]["error"])


if __name__ == "__main__":
    unittest.main()

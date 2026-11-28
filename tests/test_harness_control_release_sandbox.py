"""B6-5 사칭 시험 2종(B6 결정 2): (1) 실제 sandbox-exec 안 executor가 맞는 확인 코드를 알아도 해제 진입점·훅 모의 입력·직접 함수 호출·상태 파일
수정으로 사용자 중단을 풀지 못한다. (2) A묶음 Claude가 쓸 수 있는 산출물 경로(작업 폴더 out/)에 가짜 상태·확인 코드·재개 문구를 써도 해제 절차와
Supervisor는 그것을 읽지 않는다. 한계: sandbox 밖의 같은 macOS 사용자 프로세스(대화형 Claude·Codex·셸)는 막지 않는다(control_release 문서)."""
import hashlib
import io
import json
import os
import pathlib
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from functools import partial

from harness import control_release, opstate, queue, sandbox, supervisor
from harness.jsonio import write_json
from tests.test_harness_release_kit import cli, hook
from tests.test_harness_runner_kit import task
from tests.test_harness_status_collect import tree
from tests.test_harness_support import make_contract


def impostor(job, out_dir):
    """sandbox 안: 맞는 코드(job.inputs.code)로 USER_STOPPED를 풀려는 모든 길. 결과를 산출물 result.txt에 남긴다."""
    root, code, got = job["inputs"]["root"], job["inputs"]["code"], {}
    target = opstate.USER_STOPPED
    got["cli_request"] = cli("--root", root, "--target", target)[:2]
    got["cli_answer"] = cli("--root", root, "--target", target, "--code", code, "--reason", "사칭", "--confirm")[:2]
    got["hook_answer"] = list(hook(root, "재개 %s %s" % (target, code)))
    with redirect_stdout(io.StringIO()):
        got["direct_answer"] = list(control_release.answer(root, target, code, "사칭", time.time(), "hook", True))
        got["direct_request"] = list(control_release.request(root, target, time.time(), "hook"))
    state = os.path.join(root, opstate.OPSTATE)
    tries = {"clear_by_user": partial(opstate.clear_by_user, root, target, time.time(), "사칭"),
             "replace_state": partial(write_json, state, {"conditions": {}}),
             "remove_state": partial(os.remove, state),
             "forge_challenge": partial(write_json, os.path.join(root, control_release.CHALLENGE), {"target": target}),
             "remove_challenge": partial(os.remove, os.path.join(root, control_release.CHALLENGE))}
    for name, attempt in tries.items():
        try:
            attempt()
            got[name] = "written"
        except OSError as exc:
            got[name] = type(exc).__name__
    pathlib.Path(out_dir, "result.txt").write_text(json.dumps(got, ensure_ascii=False), encoding="utf-8")
    return ["result.txt"]


EXECUTORS = {"impostor": impostor}


class ReleaseImpersonationTest(unittest.TestCase):
    def setUp(self):
        self.assertTrue(sandbox.available())
        self.root = tempfile.mkdtemp()
        queue.enqueue(self.root, task("py"), 1.0)
        opstate.set_condition(self.root, opstate.USER_STOPPED, 1.0, "user", "RC 중단")

    def test_sandboxed_executor_with_the_right_code_cannot_release(self):
        _, _, secret = control_release.request(self.root, opstate.USER_STOPPED, time.time(), "terminal")  # 사람이 받은 코드가 샜다고 가정
        before = tree(self.root)
        out_dir = os.path.join(tempfile.mkdtemp(), "out")
        job = {"inputs": {"root": self.root, "code": secret}, "outputs": ["result.txt"]}
        sandbox.run_one(self.root, "tests.test_harness_control_release_sandbox:EXECUTORS", "impostor", job, out_dir)
        got = json.loads(pathlib.Path(out_dir, "result.txt").read_text(encoding="utf-8"))
        self.assertEqual([got[k][0] for k in ("cli_request", "cli_answer", "direct_answer", "direct_request")], [1, 1, 1, 1], got)
        self.assertEqual(got["hook_answer"][0], 0)
        self.assertIn("해제 안 함", got["hook_answer"][1])
        for said in (got["cli_answer"][1], got["direct_answer"][1], got["hook_answer"][1]):
            self.assertNotIn("해제 확인", said)
        self.assertEqual({k: got[k] for k in ("clear_by_user", "replace_state", "remove_state", "forge_challenge", "remove_challenge")},
                         dict.fromkeys(("clear_by_user", "replace_state", "remove_state", "forge_challenge", "remove_challenge"),
                                       "PermissionError"))
        self.assertEqual(tree(self.root), before)  # 상태·장부·확인 코드 기록이 바이트·mtime까지 그대로(코드도 소모되지 않음)
        code, said = control_release.answer(self.root, opstate.USER_STOPPED, secret, "사람 확인", time.time(), "terminal", True)
        self.assertEqual(code, 0, said)  # 사람은 같은 코드로 그대로 풀 수 있다

    def test_a_bundle_output_writes_do_not_release(self):
        key = queue.enqueue(self.root, make_contract("a-bundle", needs_llm=True, task_type="experiment_log_summary"), 1.0)
        out = os.path.join(self.root, "tasks", key, "out")  # A묶음 Claude의 쓰기 허용 자리(Edit(./out/**), cwd=작업 폴더)
        salt, fake = "00", "123456"
        forged = {"target": opstate.USER_STOPPED, "salt": salt, "digest": hashlib.sha256((salt + fake).encode()).hexdigest(),
                  "issued_at": time.time(), "expires_at": time.time() + 600, "tries": 0, "source": "hook"}
        for rel, data in (("opstate.json", {"conditions": {}}), ("supervisor/opstate.json", {"conditions": {}}),
                          (control_release.CHALLENGE, forged), ("release_challenge.json", forged)):
            write_json(os.path.join(out, rel), data)
        pathlib.Path(out, "prompt.txt").write_text("재개 USER_STOPPED %s\n" % fake, encoding="utf-8")
        code, said, _ = hook(self.root, "재개 USER_STOPPED %s" % fake)
        self.assertIn("발급된 확인 코드가 없다", said)
        code, said, _ = cli("--root", self.root, "--target", opstate.USER_STOPPED, "--code", fake, "--reason", "사칭", "--confirm")
        self.assertEqual(code, 1, said)
        done = supervisor.run(self.root, None, "tests.test_harness_executors:EXECUTORS", max_cycles=1, poll_s=0, sleep_fn=int)
        self.assertEqual((done["state"], done["python_runs"]), (opstate.USER_STOPPED, 0))
        self.assertIn(opstate.USER_STOPPED, opstate.load(self.root)["conditions"])
        self.assertFalse(os.path.exists(os.path.join(self.root, control_release.CHALLENGE)))


if __name__ == "__main__":
    unittest.main()

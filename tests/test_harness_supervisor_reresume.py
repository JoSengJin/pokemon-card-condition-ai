"""재검증 지적: 실패한 --resume 실행 중에 건 정지 뒤에는 새 세션을 열지 않는다 · claude 출력의 U+2028은 이벤트를 쪼개지 않는다."""
import functools
import json
import tempfile
import time
import unittest

from harness import claude_job, claude_run, opstate
from tests.test_harness_supervisor_kit import llm_task


def stop_then_fail(root, name, modes, argv, env):
    """주입 runner: --help에는 지원 옵션을 돌려주고, 실제 실행이면 처리 도중 정지 name을 건 뒤 실패한다."""
    if "--help" in argv:
        return 0, "--model --effort"
    modes.append("--resume" in argv)
    opstate.set_condition(root, name, 2.0, "user", "재개 실행 중 정지")
    return 1, ""


def answer(out, argv, env):
    return 0, out


class ReresumeTest(unittest.TestCase):
    def test_stop_during_a_failing_resume_opens_no_new_session(self):
        for name in opstate.HALTING:
            root, modes = tempfile.mkdtemp(), []
            llm_task(root)
            job = dict(claude_job.pick(root, 1.0), session_id="s-1", status="rate_limited")
            outcome = claude_job.execute(root, job, "claude", time.time, functools.partial(stop_then_fail, root, name, modes))
            self.assertEqual((modes, claude_job.settle(root, job, outcome, 3.0)), ([True], "halted"), name)

    def test_line_separator_characters_in_claude_output_do_not_split_events(self):
        line = json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "a b\u0085c"},
                          ensure_ascii=False)
        got = claude_run.run_once("claude", "작업", "sonnet", "medium", functools.partial(answer, line + "\n"), session_id="s")
        self.assertEqual((got["success"], got["bad_lines"]), (True, 0))


if __name__ == "__main__":
    unittest.main()

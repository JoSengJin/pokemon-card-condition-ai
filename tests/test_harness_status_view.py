"""B6-2 모바일 요약: 짧은 텍스트(20줄 이하)와 외부 자원 없는 정적 HTML. 비밀 모양 값·홈 경로를 내보내지 않는다."""
import os
import tempfile
import unittest

from harness import opstate, queue, status, status_view
from harness.jsonio import write_json
from tests.test_harness_support import make_contract

NOW = 1_800_000_000.0


def summary(*conditions, notes=(), jobs=0):
    """(조건 이름, 정보) 목록·알림·대기 Claude 작업으로 합성 root를 만들고 텍스트 요약의 줄 목록을 돌려준다."""
    root = tempfile.mkdtemp()
    queue.enqueue(root, make_contract(), NOW)
    for name, info in conditions:
        opstate.set_condition(root, name, NOW, "tester", info.pop("reason", "사유 " + name), info)
    for message in notes:
        opstate.notify(root, NOW, "note", message)
    for n in range(jobs):
        write_json(os.path.join(root, "supervisor", "claude", "%064x.json" % n), {"status": "blocked", "hold_reason": "대기%d" % n})
    return status_view.render_text(status.collect(root, NOW)).split("\n")


def line(lines, prefix):
    [found] = [row for row in lines if row.startswith(prefix)]
    return found


class StatusViewTest(unittest.TestCase):
    def test_running_summary_has_the_required_lines(self):
        lines = summary(notes=["알림 %d" % n for n in range(5)])
        self.assertIn("모델 성능·정확도 아님", lines[0])
        self.assertIn("RUNNING", line(lines, "상태:"))
        self.assertIn("실행 중 아님", line(lines, "Supervisor:"))
        self.assertIn("없음", line(lines, "사람이 할 일:"))
        self.assertIn("대기 중인 한도 없음", line(lines, "자동 재개:"))
        self.assertIn("실험 0/20(남음 20)", line(lines, "예산"))
        self.assertIn("비전 구역 0/300(남음 300)", line(lines, "예산"))
        self.assertIn("PENDING 1", line(lines, "작업:"))
        self.assertEqual([row for row in lines if "알림 " in row and row.startswith("  ")][-1].split()[-1], "4")
        self.assertEqual(len([row for row in lines if row.startswith("  ") and "note" in row]), 3)

    def test_each_stop_reads_differently_and_limit_resume_is_not_a_user_release(self):
        limited = summary((opstate.RATE_LIMITED_SHORT, {"next_try_at": NOW + 600}))
        self.assertIn("Claude 작업만 멈춤", line(limited, "상태:"))
        self.assertIn("약 10분 뒤", line(limited, "자동 재개:"))
        self.assertIn("Supervisor가 실행 중이 아니", line(limited, "자동 재개:"))
        exhausted = summary((opstate.RATE_LIMITED_UNKNOWN, {"next_try_at": None, "exhausted": True}))
        self.assertIn("3회 소진", line(exhausted, "자동 재개:"))
        self.assertIn("사람 확인", line(exhausted, "사람이 할 일:"))
        both = summary((opstate.RATE_LIMITED_SHORT, {"next_try_at": NOW + 600}), (opstate.USER_STOPPED, {}))
        self.assertIn("사용자 중단", line(both, "상태:"))
        self.assertIn("없음", line(both, "자동 재개:"))
        self.assertIn("정지는 자동으로 풀리지 않음", line(both, "자동 재개:"))
        self.assertNotIn("분 뒤", line(both, "자동 재개:"))  # 한도 시각이 지나도 사용자 중단은 안 풀린다
        self.assertIn("사용자만", line(both, "사람이 할 일:"))
        self.assertIn("예산 재승인", line(summary((opstate.BUDGET_EXCEEDED, {})), "사람이 할 일:"))
        root = tempfile.mkdtemp()
        os.makedirs(os.path.join(root, "supervisor"))
        with open(os.path.join(root, opstate.OPSTATE), "w") as handle:
            handle.write("{")
        with open(os.path.join(root, "ledger.jsonl"), "w") as handle:
            handle.write("x\n")
        broken = status_view.render_text(status.collect(root, NOW)).split("\n")
        self.assertIn("손상", line(broken, "상태:"))
        self.assertNotIn("RUNNING", line(broken, "상태:"))
        self.assertIn("작업 장부 문제 1건", line(broken, "장부:"))

    def test_secrets_home_paths_and_long_text_never_leave(self):
        nasty = "API_KEY=sk-ant-secret0123456789 /Users/someone/data/x.jpg\n둘째 줄 " + "가" * 500
        lines = summary((opstate.USER_STOPPED, {"reason": nasty}), notes=[nasty, "token: abcdefgh " + os.path.expanduser("~")])
        text = "\n".join(lines)
        for leaked in ("secret0123456789", "abcdefgh", "/Users/", "someone", os.path.expanduser("~")):
            self.assertNotIn(leaked, text)
        self.assertIn("[가림]", text)
        self.assertTrue(all(len(row) <= status_view.WIDTH for row in lines))
        self.assertTrue(any(row.endswith("…") for row in lines))
        self.assertFalse(any(row.startswith("둘째 줄") for row in lines))  # 사유의 줄바꿈이 새 줄을 만들지 않는다

    def test_worst_case_stays_within_the_line_limit(self):
        conds = [(name, {}) for name in (opstate.INTEGRITY_HALT, opstate.DONE, opstate.BUDGET_EXCEEDED,
                                         opstate.USER_STOPPED)] + [(opstate.RATE_LIMITED_WEEKLY, {"next_try_at": 1e300})]
        lines = summary(*conds, notes=["n"] * 9, jobs=30)
        self.assertLessEqual(len(lines), 20)
        self.assertIn("Claude 대기 30", line(lines, "확인 대기:"))
        self.assertIn("외 2개", "\n".join(lines))
        self.assertIn("INTEGRITY_HALT", line(lines, "상태:"))  # 우선순위가 가장 높은 정지

    def test_html_is_static_escaped_and_self_contained(self):
        root = tempfile.mkdtemp()
        opstate.set_condition(root, opstate.USER_STOPPED, NOW, "t", "<script src=x></script> & \"q\"")
        page = status_view.render_html(status.collect(root, NOW))
        for banned in ("<script", "http", "/Users/", "<link", "<img", "url(", "@import"):
            self.assertNotIn(banned, page)
        self.assertIn("&lt;script src=x&gt;", page)
        for needed in ('<meta charset="utf-8">', "width=device-width", "font-size:16px", "모델 성능·정확도 아님"):
            self.assertIn(needed, page)


if __name__ == "__main__":
    unittest.main()

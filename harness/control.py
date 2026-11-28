"""하네스 제어 명령줄(B6): python -m harness.control status|stop --root R. 사용자 중단을 푸는 명령은 없다(B6-5 미구현).

- status(읽기 전용): status.collect → status_view의 짧은 텍스트(--html이면 정적 HTML)를 표준 출력에 낸다. 파일을 쓰지 않는다.
- stop: opstate의 USER_STOPPED를 기록한다. 이미 정지면 기존 기록(since·사유)을 그대로 둔다. 상태 파일을 다시 읽어 확인한 사실만 말한다.
  새 작업만 막는다: 이미 실행 중인 claude·executor는 끊지 않는다(supervisor.py의 현 설계, pre-b6 결정 3: 사용자 확인 필요).
  실행자 이름 control_cli는 출처 기록일 뿐 사용자 인증이 아니다. 누가 부르든 중단은 켤 수 있다(막는 방향이라 허용).
  쓰기를 막는 실제 강제는 executor의 OS sandbox다: sandbox 안에서 부른 stop은 실패하고 실패했다고 말한다(같은 macOS 사용자의 다른
  프로세스는 막지 않는다).
- 종료 코드: 0 확인됨, 1 실패·확인 못 함·하네스 root 아님, 2 명령줄 오류.
호출 깊이: main → status.collect → status_tasks.scan → states.facts → 말단 4, main → stop → opstate.set_condition → ledger.append 3.
"""
import argparse
import os
import sys
import time

from . import opstate, status, status_view

ACTOR = "control_cli"


def stop(root, now, reason):
    """(종료 코드, 사람에게 보일 문장). gold_hook._stop과 같은 규칙: 기록 중 오류가 나도 상태 파일을 다시 읽어 판정한다."""
    note = "새 작업은 시작하지 않는다. 이미 실행 중인 claude·executor는 끊지 않는다(끝날 때까지 돌며 사용량을 쓸 수 있다)."
    try:
        if opstate.USER_STOPPED in opstate.load(root)["conditions"]:
            return 0, "이미 중단 상태: USER_STOPPED가 기록되어 있어 기존 기록을 그대로 둔다. " + note
    except OSError:
        pass  # 아래 기록과 다시 읽기가 실패를 보고한다
    error = ""
    try:
        opstate.set_condition(root, opstate.USER_STOPPED, now, ACTOR, reason)
    except Exception as exc:  # noqa: BLE001 — 상태 파일은 썼는데 장부 기록만 실패할 수 있으므로 아래에서 다시 읽는다
        error = " (기록 중 오류: %s)" % type(exc).__name__
    try:
        state = opstate.load(root)
    except OSError as exc:
        return 1, "중단을 기록했는지 확인하지 못함%s: 상태 파일을 읽을 수 없음(%s). 중단됐다고 보지 말 것." % (error, type(exc).__name__)
    if opstate.USER_STOPPED in state["conditions"]:
        return 0, "중단 기록 확인: USER_STOPPED%s. %s 해제는 사용자만 하며 이 명령줄에는 해제 명령이 없다." % (error, note)
    now_state = opstate.effective(state)
    held = " 이 상태에서도 Supervisor는 새 작업을 시작하지 않는다." if now_state in opstate.HALTING else \
        " Supervisor가 새 작업을 시작할 수 있다."
    return 1, "중단을 기록하지 못함%s. 현재 상태 %s.%s" % (error, now_state, held)


def main(argv):
    parser = argparse.ArgumentParser(prog="python -m harness.control", allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    shown = commands.add_parser("status", help="상태 요약(읽기 전용)", allow_abbrev=False)
    shown.add_argument("--html", action="store_true", help="정적 HTML로 출력")
    halting = commands.add_parser("stop", help="사용자 중단 기록(실행 중 작업은 끊지 않음)", allow_abbrev=False)
    halting.add_argument("--reason", default="")
    for command in (shown, halting):
        command.add_argument("--root", required=True, help="하네스 root 폴더")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return exc.code
    root = os.path.abspath(args.root)
    if not status.is_harness_root(root):
        print("하네스 root가 아니라 아무것도 하지 않음(supervisor·tasks·ledger.jsonl이 없음): %s" % root)
        return 1
    if args.command == "stop":
        code, message = stop(root, time.time(), args.reason.strip() or "control CLI: 중단")
        print(message)
        return code
    render = status_view.render_html if args.html else status_view.render_text
    print(render(status.collect(root, time.time())))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""하네스 시작(B6-4): `python -m harness.supervisor --root R ...`를 별도 세션의 하위 프로세스로 띄운다. LaunchAgent·서비스 설치가 아니다.

- --claude-bin·--executors는 호출자가 명시한 것만 넘긴다. 기본은 없음 = Claude 작업·Python 작업 모두 실행하지 않는다. 여기서는 합성
  executors·가짜 claude로만 검증했다. 실제 claude·실제 실험 executor를 붙이는 것은 승인 밖이다.
- 정지 조건은 풀지 않는다(해제 호출 없음). 정지 상태에서 띄우면 감시만 한다고 알린다(HARNESS_RULES: Supervisor는 상시 실행 가능).
- 이미 실행 중이거나 확인할 수 없으면 띄우지 않는다. 확인 뒤에 다른 쪽이 먼저 잠그면 자식이 종료 코드 4로 끝나고 그대로 보고한다
  (Supervisor의 잠금이 중복 실행을 막는 정본이다).
- 시작 확인은 "자식이 살아 있고 Supervisor 잠금이 잡혀 있다"까지다.
  shortcut: 잠금 파일에 pid가 없어 잠금의 주인이 이 자식인지는 증명하지 못한다(pre-b6 결정 6). 필요하면 supervisor.py가 pid를 쓰게 한다.
- 자식의 표준 입출력은 root/supervisor/control_start.log(추가)에 잇는다. 부모는 자식을 기다리지 않고 돌아온다.
- 종료 코드: 0 실행 확인(또는 --max-cycles로 정상 종료), 1 실패·확인 못 함, 4 이미 실행 중.
호출 깊이: start → status.supervisor_running 1, start → opstate.load → read_json 2(control.main부터 3).
"""
import os
import subprocess
import sys
import time

from . import evidence, opstate, status

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join("supervisor", "control_start.log")
GRACE_S = 1.0  # 첫 잠금 확인 전 대기: 자식이 잠금을 시도하는 순간과 겹치지 않게
CONFIRM_S = 15.0  # 이 안에 잠금을 확인하지 못하면 시작을 확인했다고 말하지 않는다
ALREADY = 4  # supervisor.py __main__의 already_running 종료 코드


def start(root, claude_bin=None, executors=None, source_root=None, max_cycles=None, poll=None):
    """root는 절대 경로. (종료 코드, 사람에게 보일 문장)."""
    running = status.supervisor_running(root)
    if running is not False:
        return (ALREADY, "이미 실행 중이라 시작하지 않음(Supervisor 잠금이 잡혀 있다).") if running else \
            (1, "시작하지 못함: Supervisor 실행 여부를 확인할 수 없어 띄우지 않았다.")
    try:
        state = opstate.effective(opstate.load(root))
    except OSError:
        state = opstate.INTEGRITY_HALT
    if claude_bin and os.sep in claude_bin:  # 자식의 cwd는 저장소다: 상대 경로는 부른 곳 기준으로 바꿔 넘긴다
        claude_bin = os.path.abspath(claude_bin)
    source_root = os.path.abspath(source_root) if source_root else None
    argv = [sys.executable, "-m", "harness.supervisor", "--root", root]
    for flag, value in (("--claude-bin", claude_bin), ("--executors", executors), ("--source-root", source_root),
                        ("--max-cycles", max_cycles), ("--poll", poll)):
        if value is not None:
            argv += [flag, str(value)]
    try:
        os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
        with open(os.path.join(root, LOG), "ab") as out:
            offset = out.tell()
            child = subprocess.Popen(argv, cwd=REPO, stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)
    except OSError as exc:
        return 1, "시작하지 못함(%s): Supervisor를 띄우지 않았다." % type(exc).__name__
    work = "Python 작업: %s · Claude 작업: %s." % ("켬" if executors else "끔(--executors 없음)",
                                              "켬" if claude_bin else "끔(--claude-bin 없음)")
    if state in opstate.HALTING:
        work += " 정지 상태(%s)라 감시만 하고 어떤 작업도 시작하지 않는다. start는 정지를 풀지 않는다(해제 명령 없음)." % state
    elif state in opstate.RATE_LIMITED:
        work += " 사용량 한도 상태(%s)라 Claude 작업은 재개 시각까지 멈춘다." % state
    deadline, pause, locked = time.monotonic() + CONFIRM_S, GRACE_S, False
    while not locked and child.poll() is None and time.monotonic() < deadline:
        try:
            child.wait(timeout=pause)
        except subprocess.TimeoutExpired:
            locked = status.supervisor_running(root) is True
        pause = 0.2
    code = child.poll()
    if code is None:
        if locked:
            return 0, "시작 확인: pid %d(자식 실행 중, Supervisor 잠금 확인). %s 출력: %s" % (child.pid, work, LOG)
        return 1, "시작을 확인하지 못함: pid %d를 띄웠지만 Supervisor 잠금이 보이지 않는다. 됐다고 보지 말 것(프로세스는 남아 있다). 출력: %s" % (
            child.pid, LOG)
    if code == ALREADY:
        return ALREADY, "이미 실행 중이라 시작하지 않음(다른 Supervisor가 먼저 잠금을 잡았다)."
    with open(os.path.join(root, LOG), "rb") as handle:
        handle.seek(offset)
        tail = evidence.mask(handle.read().decode("utf-8", "replace").strip(), 500)
    if code == 0:
        return 0, "시작해 이미 끝남(pid %d, 종료 코드 0). %s 결과: %s" % (child.pid, work, tail)
    return 1, "시작 실패: Supervisor가 종료 코드 %d로 끝났다. 출력 끝부분: %s" % (code, tail)

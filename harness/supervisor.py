"""Supervisor 루프(DESIGN 3·9·12절). LLM을 쓰지 않는 결정론 프로세스이며 launchd가 띄운다(템플릿: harness/launchd/).

한 회차: 운영 상태 확인(opstate) → 정지 상태(INTEGRITY_HALT·USER_STOPPED·DONE·BUDGET_EXCEEDED)면 아무 작업도 시작하지 않고 감시만
→ 의존 그래프 대조(graph.register_missing, 선언 파일 root/supervisor/declared.json이 있을 때) → Python 작업 처리(2단계 runner를
별도 프로세스로 `--max 1`씩, 종료 코드 3 = 장부 무결성 → INTEGRITY_HALT) → 한도 상태면 Claude 작업만 멈추고 재개 시각(next_try_at)이
지났을 때만 한도 조건을 자동 해제(clear_auto)하고 재개 → Claude 작업 칸(claude_job) 실행·반영 → 다음 회차까지 대기(sleep_fn, 한도면 재개 시각까지).
- 정지 상태는 회차 시작에만 보지 않는다: Python 작업 하나를 시작하기 전마다, Python 처리 뒤(clear_auto 직전), pick 직전, execute 직전에
  다시 읽어 정지면 그 회차를 끝낸다(처리 중 건 USER_STOPPED 뒤에 새 작업을 시작하지 않는다). 이미 돌고 있는 작업은 강제로 끊지 않는다.
  남는 틈: 확인과 runner의 claim 사이(밀리초)에 건 정지는 그 작업 1개를 막지 못한다(runner는 운영 상태를 읽지 않는다, 2단계 파일).
- 상태는 모두 파일(opstate.json·claude.json·장부)에 있어 kill -9 뒤 다시 시작해도 같은 상태에서 이어간다.
- root마다 Supervisor는 하나만 돈다(root/supervisor/supervisor.lock 비차단 flock, 이미 돌고 있으면 already_running).
- 자동 해제하지 않는 상태의 해제(opstate.clear_by_user)와 정지 해제(unlock)는 이 루프에서 부르지 않는다(사람 확인 함수).
- 예상하지 못한 예외는 추정해서 계속하지 않고 INTEGRITY_HALT로 멈춘다(fail-closed, 사람 확인).
- 실행: python -m harness.supervisor --root R [--claude-bin B] [--executors mod:ATTR] [--max-cycles N] [--poll S]
호출 깊이: run → runner.drain은 별도 프로세스라 세지 않는다. run → _live(2)·opstate.clear_auto(3)·graph.register_missing(2)·
claude_job.pick(2)·execute(3)·settle(3)이라 최대 4다. 모듈 맨 아래 __main__ 블록은 _args와 run만 부른다.
- root는 절대 경로로 바꿔 쓴다(runner는 cwd=REPO에서 돌기 때문에 상대 경로면 다른 폴더를 본다).
"""
import errno
import fcntl
import json
import os
import subprocess
import sys
import time

from . import claude_job, graph, ledger, opstate
from .jsonio import read_json

POLL_S = 60.0
INTEGRITY_EXIT = 3  # harness.runner의 장부 무결성 종료 코드(runner.INTEGRITY_EXIT와 같은 값, 시험이 대조)
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECLARED = os.path.join("supervisor", "declared.json")


def _python(root, executors, now):
    """2단계 runner를 별도 프로세스로 한 번 돌려 Python 작업을 최대 1개 처리한다(executor의 강제 종료가 Supervisor를 죽이지 않게,
    작업마다 정지 상태를 다시 보려고 `--max 1`). (종료 코드, 실행한 작업 수). 비정상 종료·요약 없음은 실행 0으로 본다."""
    done = subprocess.run([sys.executable, "-m", "harness.runner", root, executors, "--max", "1"], cwd=REPO,
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, check=False)
    if done.returncode == INTEGRITY_EXIT:
        return done.returncode, 0  # 장부가 손상됐으므로 여기서 장부에 쓰지 않는다(호출자가 INTEGRITY_HALT로 올린다)
    lines = done.stdout.strip().splitlines()
    try:
        summary = json.loads(lines[-1]) if lines else None
    except ValueError:
        summary = None
    executed = summary.get("executed") if isinstance(summary, dict) else None
    if done.returncode != 0 or not isinstance(summary, dict) or executed:
        ledger.append(os.path.join(root, "ledger.jsonl"), now, "python_drain",
                      {"returncode": done.returncode, "summary": summary, "stderr_tail": done.stderr[-500:]})
    return done.returncode, executed if done.returncode == 0 and type(executed) is int else 0


def _live(root, summary):
    """운영 상태를 다시 읽어 summary["state"]에 남긴다. 정지 상태(HALTING)면 None(그 회차를 끝낸다), 아니면 상태 dict."""
    state = opstate.load(root)
    summary["state"] = opstate.effective(state)
    return None if summary["state"] in opstate.HALTING else state


def run(root, claude_bin=None, executors=None, max_cycles=None, poll_s=POLL_S, now_fn=time.time, sleep_fn=time.sleep,
        runner=None, env=None):
    """Supervisor 루프. max_cycles가 None이면 계속 돈다. 요약 dict(회차 수, 마지막으로 읽은 유효 상태, Claude 실행 수·runner 실행 수)."""
    root = os.path.abspath(root)
    os.makedirs(os.path.join(root, "supervisor"), exist_ok=True)
    fd = os.open(os.path.join(root, "supervisor", "supervisor.lock"), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            return {"already_running": True}
        raise
    summary = {"cycles": 0, "state": None, "claude_runs": 0, "python_runs": 0, "outcomes": []}
    wake = None
    try:
        while max_cycles is None or summary["cycles"] < max_cycles:
            if wake is not None:  # 회차 사이 대기(마지막 회차 뒤에는 기다리지 않는다). continue로 회차를 끝내도 여기서 기다린다
                sleep_fn(max(0.0, wake - now_fn()))
            summary["cycles"] += 1
            now = now_fn()
            wake = now + poll_s
            try:
                if _live(root, summary) is None:
                    continue
                declared = read_json(os.path.join(root, DECLARED), {})
                if declared:
                    graph.register_missing(root, declared, now)
                while executors and _live(root, summary) is not None:  # Python 작업 하나를 시작하기 전마다 정지 상태를 본다
                    summary["python_runs"] += 1
                    code, executed = _python(root, executors, now_fn())
                    if code == INTEGRITY_EXIT:
                        opstate.set_condition(root, opstate.INTEGRITY_HALT, now_fn(), "supervisor",
                                              "runner 종료 코드 3(장부 무결성)")
                        opstate.notify(root, now_fn(), "integrity_halt", "장부 무결성 오류로 정지(사람 확인 필요)")
                        break
                    if not executed:
                        break
                state = _live(root, summary)  # Python 처리 뒤·clear_auto 직전
                if state is None:
                    continue
                eff = summary["state"]
                gate = state["conditions"].get(eff) if eff in opstate.RATE_LIMITED else None
                if gate is not None and not gate.get("exhausted") and gate.get("next_try_at") is not None \
                        and now_fn() >= gate["next_try_at"]:  # next_try_at 형식(유한한 숫자)은 opstate.load가 확인했다
                    opstate.clear_auto(root, eff, now_fn(), "재개 시각 도달: Claude 작업 재개")
                    gate = None
                if gate is not None:  # 한도 중: Claude 작업만 멈춘다(Python 작업은 위에서 계속 처리)
                    if not gate.get("exhausted") and gate.get("next_try_at") is not None:
                        wake = min(wake, gate["next_try_at"])
                elif claude_bin and _live(root, summary) is not None:  # pick 직전
                    job = claude_job.pick(root, now_fn())
                    if job is not None and _live(root, summary) is not None:  # execute 직전
                        summary["claude_runs"] += 1
                        outcome = claude_job.execute(root, job, claude_bin, now_fn, runner, env)
                        summary["outcomes"].append(claude_job.settle(root, job, outcome, now_fn()))
                        wake = now_fn()  # 결과를 반영했으면 곧바로 다음 회차
            except Exception as exc:  # noqa: BLE001 — 모르는 오류는 추정하지 않고 사람 확인으로 멈춘다
                try:
                    opstate.set_condition(root, opstate.INTEGRITY_HALT, now_fn(), "supervisor",
                                          "supervisor_error: %s: %s" % (type(exc).__name__, exc))
                    opstate.notify(root, now_fn(), "integrity_halt", "Supervisor 오류로 정지: %s" % type(exc).__name__)
                except (opstate.OpStateError, ledger.LedgerError, OSError):
                    pass  # 상태 파일·알림 장부도 못 쓰면 다음 회차의 load가 손상을 INTEGRITY_HALT로 본다
                summary["state"] = opstate.INTEGRITY_HALT
    finally:
        os.close(fd)
    return summary


def _args(argv):
    """명령행 → run 인자. 알 수 없는 인자는 ValueError."""
    names = {"--root": "root", "--claude-bin": "claude_bin", "--executors": "executors", "--max-cycles": "max_cycles",
             "--poll": "poll_s"}
    out = {}
    for flag, value in zip(argv[::2], argv[1::2]):
        if flag not in names:
            raise ValueError("알 수 없는 인자: %s" % flag)
        out[names[flag]] = int(value) if flag == "--max-cycles" else float(value) if flag == "--poll" else value
    if len(argv) % 2 or "root" not in out:
        raise ValueError("사용법: --root R [--claude-bin B] [--executors mod:ATTR] [--max-cycles N] [--poll S]")
    return out


if __name__ == "__main__":
    RESULT = run(**_args(sys.argv[1:]))
    print(json.dumps(RESULT, sort_keys=True, ensure_ascii=False), flush=True)
    sys.exit(4 if RESULT.get("already_running") else 0)

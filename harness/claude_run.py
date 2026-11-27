"""`claude -p` 한 번 실행(비대화형, stream-json)과 그 출력 해석.

- 새 세션은 `--session-id <uuid>`로 시작해 세션 ID를 실행 전에 안다(Supervisor가 실행 중에 죽어도 이어갈 수 있게).
  재개는 `--resume <session_id>`만 쓴다.
- `--continue`는 쓰지 않는다: 같은 폴더의 가장 최근 대화를 고르므로 어떤 세션이 이어질지 장부로 정할 수 없고,
  remote-control 도움말 기준 약 4시간 이내 기록만 이어진다(CONTINUE_WINDOW_HOURS, EVIDENCE 6절). 상수로만 적어 둔다.
- `/low-priority`·`/rate-limit-options`는 자동으로 쓰지 않는다(DESIGN 12절): 프롬프트가 그 명령이면 실행을 거절한다.
- `--verbose`는 -p와 stream-json을 함께 쓸 때 필요할 수 있어 붙인다(이 설치본에서 필요 여부는 미확인, 도움말에 있는 옵션).
- 권한 옵션(extra)은 호출자(claude_job, claude_perm.options)가 정한다. 세션 인자는 항상 맨 뒤에 둔다.
- 실행기는 주입한다: runner(argv, env) -> (종료 코드, 표준 출력) 또는 (종료 코드, 표준 출력, 추가 dict). 기본은 default_runner.
  default_runner는 stdout·stderr를 두 스레드로 함께 읽어 교착을 막고, 무출력 시간(idle_s)·총 시간(total_s)을 넘기면 프로세스
  그룹(start_new_session)을 TERM → KILL_GRACE_S 뒤 KILL로 끝낸다. 추가 dict: stderr, cause(timeout_idle|timeout_total|None), signal.
  claude가 끝난 뒤에도 그룹 밖(setsid) 자손이 파이프를 쥐고 있으면 최대 KILL_GRACE_S만 더 읽고 돌아오며 원인을 timeout_total로 남긴다
  (검증 결함 F6). 정상 종료 뒤 읽기 대기는 총 시간과 무관하게 KILL_GRACE_S다(2차 결함 G12). 시간 제한 원인이 있는 실행은 run_once가 성공으로
  보지 않는다.
- 기본 제한(임시값, 인계 참조): 무출력 IDLE_S 30분, 총 TOTAL_S 3시간. 실환경 출력 간격은 미확인이다.
- 세션 복원 불가 판정(session_unrecoverable)은 실환경(Claude Code 2.1.310, artifacts/harness-resume-20261127/c-realenv/t4-bogus-resume.jsonl)에서
  확보한 '없는 세션 --resume' 출력과 정확히 같은 형식만 인정한다(UNRECOVERABLE_ERROR). 조금이라도 다르면 복원 불가로 보지 않는다.
"""
import os
import signal
import subprocess
import threading
import time

from . import ratelimit
from .jsonio import write_json

CONTINUE_WINDOW_HOURS = 4  # 문서용. --continue는 쓰지 않는다
FORBIDDEN_ARGS = ("--continue", "-c")
FORBIDDEN_PROMPTS = ("/low-priority", "/rate-limit-options")
IDLE_S = 30 * 60.0  # 임시 기본값: 무출력 시간 제한
TOTAL_S = 3 * 3600.0  # 임시 기본값: 총 실행 시간 제한
KILL_GRACE_S = 5.0
UNRECOVERABLE_ERROR = "No conversation found with session ID: %s"  # 실환경 출력의 errors 문구(세션 ID 자리 %s)


def build_argv(claude_bin, prompt, model, effort, resume=None, session_id=None, extra=()):
    """argv 목록. resume와 session_id 중 하나만 준다. extra는 권한 옵션(세션 인자 앞). 금지 인자·명령은 ValueError."""
    if not isinstance(prompt, str) or not prompt.strip() or prompt.strip().split()[0] in FORBIDDEN_PROMPTS:
        raise ValueError("빈 프롬프트 또는 자동 사용 금지 명령")
    if not model or not effort or (resume is None) == (session_id is None):
        raise ValueError("모델·effort가 없거나 resume/session_id 지정이 잘못됐다")
    argv = [claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model, "--effort", effort]
    argv += list(extra)
    argv += ["--resume", resume] if resume is not None else ["--session-id", session_id]
    if any(a in FORBIDDEN_ARGS for a in argv[3:]):
        raise ValueError("금지 인자: %s" % (FORBIDDEN_ARGS,))
    return argv


def _pump(stream, sink, seen):
    """한 줄씩 읽어 sink에 모으고 마지막 출력 시각(seen[0])을 갱신한다(스레드 본체)."""
    for line in iter(stream.readline, ""):
        sink.append(line)
        seen[0] = time.monotonic()
    stream.close()


def default_runner(argv, env, pidfile=None, stamp=None, cwd=None, idle_s=IDLE_S, total_s=TOTAL_S):
    """실제 하위 프로세스로 실행. pidfile을 주면 시작 직후 stamp + {"pid"}를 원자 저장한다(실행 중 Supervisor가 죽은 경우 확인용).
    stamp에는 호출자(claude_job.execute)가 boot_id·session_id·mode·run_token을 넣는다: 낡은 pid 파일과 이번 실행을 가르는 근거다.
    (종료 코드, stdout, {"stderr", "cause", "signal"})."""
    proc = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, errors="replace", start_new_session=True)
    if pidfile:
        write_json(pidfile, dict(stamp or {}, pid=proc.pid))
    out, err, seen, start, cause = [], [], [time.monotonic()], time.monotonic(), None
    pumps = [threading.Thread(target=_pump, args=(s, k, seen), daemon=True) for s, k in ((proc.stdout, out), (proc.stderr, err))]
    for pump in pumps:
        pump.start()
    while proc.poll() is None:
        now = time.monotonic()
        cause = "timeout_total" if now - start > total_s else "timeout_idle" if now - seen[0] > idle_s else None
        if cause is not None:
            for sig, wait in ((signal.SIGTERM, KILL_GRACE_S), (signal.SIGKILL, None)):
                try:
                    os.killpg(proc.pid, sig)  # 프로세스 그룹 전체(claude가 띄운 하위 프로세스 포함)
                except (ProcessLookupError, PermissionError):
                    break
                try:
                    proc.wait(timeout=wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
            break
        time.sleep(0.05)
    proc.wait()
    try:
        os.killpg(proc.pid, signal.SIGKILL)  # 정상 종료 뒤 남은 하위 프로세스(같은 그룹)도 정리한다: 파이프를 쥔 채 남지 않게
    except (ProcessLookupError, PermissionError):
        pass
    # 남은 출력을 다 읽을 시간: 정상 종료면 총 시간과 무관하게 KILL_GRACE_S(2차 결함 G12: 총 시간 직전에 끝난 실행의 출력을 잘라 timeout으로
    # 보지 않게), 시간 제한으로 끊었으면 남은 총 시간까지. 그룹 밖(새 세션) 자손이 파이프를 쥐면 EOF가 오지 않으므로 이 시간까지만 기다린다
    deadline = time.monotonic() + (KILL_GRACE_S if cause is None else max(0.0, min(KILL_GRACE_S, start + total_s - time.monotonic())))
    for pump in pumps:
        pump.join(max(0.0, deadline - time.monotonic()))
    if any(pump.is_alive() for pump in pumps):  # shortcut: 남은 읽기 스레드(daemon)는 그 자손이 끝날 때까지 남는다(죽일 pid를 모른다)
        cause = cause or "timeout_total"
    code = proc.returncode
    return code, "".join(out), {"stderr": "".join(err), "cause": cause,
                                "signal": -code if isinstance(code, int) and code < 0 else None}


def help_text(claude_bin, runner, env, argv):
    """route.probe_cli_support에 넘기는 run(argv): argv[0]("claude")를 claude_bin으로 바꿔 `--help`를 실행한다(모델 호출 아님).
    runner를 주면 그것을, 아니면 subprocess.run을 직접 쓴다(호출 깊이를 늘리지 않으려고 default_runner를 거치지 않는다)."""
    argv = [claude_bin] + list(argv[1:])
    if runner is not None:
        return tuple(runner(argv, env))[:2]
    done = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    return done.returncode, done.stdout + done.stderr


def session_unrecoverable(found, resumed):
    """--resume <resumed> 실패 출력이 '세션 복원 불가'를 확인해 주는가. 실환경에서 확보한 형식만 True다: 종료 코드가 정확히 int 1, stdout의
    비어 있지 않은 줄이 그 result 이벤트 하나뿐(ratelimit.scan의 events 1·bad_lines 0, 실환경 t4-bogus-resume.jsonl도 한 줄, 2차 결함 G8),
    subtype=error_during_execution, is_error=true, num_turns=0(정수), errors가 정확히 [UNRECOVERABLE_ERROR % resumed] 하나.
    그 밖(다른 ID·문구·대소문자·추가 오류·앞뒤의 다른 줄·종료 코드·한도 이벤트 등)은 False(DESIGN 12절, 작업 계약 2단계 R4)."""
    result = found.get("result")
    return isinstance(resumed, str) and bool(resumed) and type(found.get("returncode")) is int and found["returncode"] == 1 \
        and found.get("events") == 1 and found.get("bad_lines") == 0 and not found.get("limited") \
        and isinstance(result, dict) and result.get("subtype") == "error_during_execution" and result.get("is_error") is True \
        and type(result.get("num_turns")) is int and result["num_turns"] == 0 \
        and result.get("errors") == [UNRECOVERABLE_ERROR % resumed]


def run_once(claude_bin, prompt, model, effort, runner=None, env=None, resume=None, session_id=None, extra=()):
    """한 번 실행하고 ratelimit.scan 요약에 argv·종료 코드·실행 오류·stderr·원인을 덧붙여 돌려준다. 실행 자체가 안 되면 returncode=None.

    cause(장애 원인, 근거가 있는 것만): rate_limit | timeout_idle | timeout_total | signal | spawn_error | unknown(그 밖의 실패) |
    None(성공)."""
    argv = build_argv(claude_bin, prompt, model, effort, resume, session_id, extra)
    try:
        got = tuple((runner or default_runner)(argv, env if env is not None else dict(os.environ)))
        code, out, more, error = got[0], got[1], (got[2] if len(got) > 2 else {}), None
    except (OSError, subprocess.SubprocessError) as exc:
        code, out, more, error = None, "", {}, "%s: %s" % (type(exc).__name__, exc)
    found = ratelimit.scan((out or "").split("\n"), code)  # 값 안의 U+2028에서 나누지 않는다
    cause = "spawn_error" if error else more.get("cause") or ("rate_limit" if found["limited"] else
                                                              "signal" if more.get("signal") else None)
    if cause in ("timeout_idle", "timeout_total"):  # 시간 제한에 걸린 실행은 성공이 아니다(파이프를 쥔 자손이 남은 경우 포함)
        found["success"] = False
    if cause is None and not found["success"]:
        cause = "unknown"
    found.update(argv=argv, returncode=code, error=error, stderr=more.get("stderr") or "", signal=more.get("signal"),
                 cause=cause)
    return found

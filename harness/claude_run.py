"""`claude -p` 한 번 실행(비대화형, stream-json)과 그 출력 해석.

- 새 세션은 `--session-id <uuid>`로 시작해 세션 ID를 실행 전에 안다(Supervisor가 실행 중에 죽어도 이어갈 수 있게).
  재개는 `--resume <session_id>`만 쓴다.
- `--continue`는 쓰지 않는다: 같은 폴더의 가장 최근 대화를 고르므로 어떤 세션이 이어질지 장부로 정할 수 없고,
  remote-control 도움말 기준 약 4시간 이내 기록만 이어진다(CONTINUE_WINDOW_HOURS, EVIDENCE 6절). 상수로만 적어 둔다.
- `/low-priority`·`/rate-limit-options`는 자동으로 쓰지 않는다(DESIGN 12절): 프롬프트가 그 명령이면 실행을 거절한다.
- `--verbose`는 -p와 stream-json을 함께 쓸 때 필요할 수 있어 붙인다(이 설치본에서 필요 여부는 미확인, 도움말에 있는 옵션).
- 실행기는 주입한다: runner(argv, env) -> (종료 코드, 표준 출력 문자열). 기본은 default_runner(실제 하위 프로세스).
  시험은 가짜 claude 실행 파일 경로를 claude_bin으로 넘긴다.
"""
import os
import subprocess

from . import ratelimit
from .jsonio import write_json

CONTINUE_WINDOW_HOURS = 4  # 문서용. --continue는 쓰지 않는다
FORBIDDEN_ARGS = ("--continue", "-c")
FORBIDDEN_PROMPTS = ("/low-priority", "/rate-limit-options")


def build_argv(claude_bin, prompt, model, effort, resume=None, session_id=None):
    """argv 목록. resume와 session_id 중 하나만 준다. 금지 인자·명령은 ValueError."""
    if not isinstance(prompt, str) or not prompt.strip() or prompt.strip().split()[0] in FORBIDDEN_PROMPTS:
        raise ValueError("빈 프롬프트 또는 자동 사용 금지 명령")
    if not model or not effort or (resume is None) == (session_id is None):
        raise ValueError("모델·effort가 없거나 resume/session_id 지정이 잘못됐다")
    argv = [claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose", "--model", model, "--effort", effort]
    argv += ["--resume", resume] if resume is not None else ["--session-id", session_id]
    if any(a in FORBIDDEN_ARGS for a in argv[3:]):
        raise ValueError("금지 인자: %s" % (FORBIDDEN_ARGS,))
    return argv


def default_runner(argv, env, pidfile=None, stamp=None):
    """실제 하위 프로세스로 실행. pidfile을 주면 시작 직후 stamp + {"pid"}를 원자 저장한다(실행 중 Supervisor가 죽은 경우 확인용).
    stamp에는 호출자(claude_job.execute)가 boot_id·session_id·mode·run_token을 넣는다: 낡은 pid 파일과 이번 실행을 가르는 근거다."""
    proc = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    if pidfile:
        write_json(pidfile, dict(stamp or {}, pid=proc.pid))
    out, _ = proc.communicate()
    return proc.returncode, out


def help_text(claude_bin, runner, env, argv):
    """route.probe_cli_support에 넘기는 run(argv): argv[0]("claude")를 claude_bin으로 바꿔 `--help`를 실행한다(모델 호출 아님).
    runner를 주면 그것을, 아니면 subprocess.run을 직접 쓴다(호출 깊이를 늘리지 않으려고 default_runner를 거치지 않는다)."""
    argv = [claude_bin] + list(argv[1:])
    if runner is not None:
        return runner(argv, env)
    done = subprocess.run(argv, env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30, check=False)
    return done.returncode, done.stdout + done.stderr


def run_once(claude_bin, prompt, model, effort, runner=None, env=None, resume=None, session_id=None):
    """한 번 실행하고 ratelimit.scan 요약에 argv·종료 코드·실행 오류를 덧붙여 돌려준다. 실행 자체가 안 되면 returncode=None."""
    argv = build_argv(claude_bin, prompt, model, effort, resume, session_id)
    try:
        code, out = (runner or default_runner)(argv, env if env is not None else dict(os.environ))
        error = None
    except (OSError, subprocess.SubprocessError) as exc:
        code, out, error = None, "", "%s: %s" % (type(exc).__name__, exc)
    found = ratelimit.scan((out or "").split("\n"), code)  # 값 안의 U+2028에서 나누지 않는다
    found.update(argv=argv, returncode=code, error=error)
    return found

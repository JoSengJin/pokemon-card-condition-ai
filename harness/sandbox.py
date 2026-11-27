"""Python executor를 macOS sandbox-exec 하위 프로세스로 실행한다(작업 계약 3단계 R6).

- runner(하네스 상태를 쓰는 프로세스)는 executor 모듈을 가져오지 않는다. 유형 목록 조회와 실행 모두 sandbox 안의 harness.sandbox_child가
  한다(모듈을 가져오는 순간의 코드도 sandbox 안에서 돈다). 그래서 executor 코드는 recovery·claude_perm 같은 등록 목록도 바꿀 수 없다.
- 프로필(검증 결함 F1·F2 뒤): 쓰기는 기본 거절이다. 허용은 그 작업의 out/, 실행별 전용 임시 폴더(run_one이 시스템 임시 폴더 아래에 새로
  만들어 TMPDIR로 넘기고 끝나면 지운다), 장치 파일 DEVICES뿐이다(목록 조회는 out/·임시 폴더도 없다). 그래서 하네스 root(상위 폴더 이름을
  바꾸는 우회 포함)·저장소 소스·site-packages·홈·시스템 임시 폴더 쓰기가 모두 거절된다. 실제 경로(realpath)로 적는다.
  launchd·LaunchServices·AppleScript를 거쳐 sandbox 밖에서 명령을 돌리는 실행 파일(DENY_EXEC) 실행과 Apple Event 보내기도 거절한다.
- sandbox-exec가 없거나 시험 실행이 실패하면 available()이 False이고 runner는 executor를 실행하지 않는다(fail-closed).
- 결과: 자식이 마지막 줄에 JSON({"ok": true, "produced"} | {"ok": false, "kind", "error"})을 낸다. 자식이 신호로 죽으면 kind=interrupted
  (runner가 작업권을 남겨 다음 claim이 INTERRUPTED 규칙대로 다룬다), JSON이 없으면 deterministic.
- 한계(인계): 같은 macOS 사용자의 다른 프로세스(Codex·대화형 Claude·사용자 셸)는 막지 못한다(OS 사용자 분리 D-7 보류). sandbox는 쓰기·
  위 실행 파일만 막는다(읽기·네트워크·프로세스 신호는 막지 않는다). executor 코드가 실행 파일 없이 launchd에 직접 XPC/mach 요청을 보내는
  경로는 막지 못한다(시스템 상태를 바꾸는 시험이라 하지 않았다). sandbox-exec는 Apple이 폐기 예정으로 표시한 도구다. 홈 캐시(~/.cache 등)에
  써야 하는 라이브러리는 sandbox 안에서 실패한다(TMPDIR·out/만 쓸 수 있다).
호출 깊이: sandboxed·run_one → profile(말단) 1.
"""
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = [sys.executable, "-m", "harness.sandbox_child"]
DEVICES = ("/dev/null",)  # 쓰기를 허용하는 장치 파일(이것뿐)
DENY_EXEC = ("/bin/launchctl", "/usr/bin/open", "/usr/bin/osascript")  # sandbox 밖(launchd·LaunchServices·AppleScript)에서 명령을 돌리는 도구


class ChildError(Exception):
    """sandbox 안 executor의 실패. kind: transient | deterministic | interrupted(신호로 죽음)."""


def profile(root, out_dir=None, tmp_dir=None):
    """SBPL 문자열: 쓰기 기본 거절 + out_dir·tmp_dir·DEVICES만 허용. out_dir은 root/tasks 아래, tmp_dir은 root 밖이어야 한다.
    경로에 따옴표·역슬래시가 있거나 위치가 맞지 않으면 ValueError(프로필을 안전하게 적을 수 없다)."""
    base, allowed = os.path.realpath(root), [os.path.realpath(p) for p in (out_dir, tmp_dir) if p]
    if any('"' in p or "\\" in p for p in [base] + allowed + list(DENY_EXEC)):
        raise ValueError("sandbox 프로필에 쓸 수 없는 경로")
    if (out_dir and os.path.commonpath([os.path.join(base, "tasks"), allowed[0]]) != os.path.join(base, "tasks")) or \
            (tmp_dir and os.path.commonpath([base, allowed[-1]]) == base):
        raise ValueError("out_dir은 root/tasks 아래, tmp_dir은 root 밖이어야 한다")
    grant = ['(subpath "%s")' % p for p in allowed] + ['(literal "%s")' % d for d in DEVICES]
    return "\n".join(['(version 1)', '(allow default)', '(deny file-write*)', '(allow file-write* %s)' % " ".join(grant),
                      '(deny process-exec %s)' % " ".join('(literal "%s")' % p for p in DENY_EXEC), '(deny appleevent-send)'])


def available():
    """sandbox-exec로 실제 하위 프로세스를 띄워 쓰기 거절 프로필이 적용되는지 확인한다. 실패·없음은 False."""
    if not os.path.isfile(SANDBOX_EXEC):
        return False
    try:
        done = subprocess.run([SANDBOX_EXEC, "-p", profile(REPO), "/usr/bin/true"], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def run_one(root, spec, task_type, task, out_dir):
    """executor 하나를 sandbox 안에서 실행한다. 정상이면 돌려준 출력 목록, 실패는 ChildError(.kind).
    실행마다 새 임시 폴더를 만들어 TMPDIR로 넘기고(그곳과 out_dir만 쓸 수 있다) 끝나면 지운다."""
    os.makedirs(out_dir, exist_ok=True)
    out_dir, tmp = os.path.realpath(out_dir), tempfile.mkdtemp(prefix="harness-exec-")
    try:
        done = subprocess.run([SANDBOX_EXEC, "-p", profile(root, out_dir, tmp)] + CHILD + ["run", spec, task_type, out_dir],
                              cwd=REPO, env=dict(os.environ, TMPDIR=tmp), input=json.dumps(task, ensure_ascii=False),
                              capture_output=True, text=True, errors="replace", check=False)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        reply = json.loads(done.stdout.strip().split("\n")[-1])
    except ValueError:
        reply = None
    if isinstance(reply, dict) and reply.get("ok") is True and isinstance(reply.get("produced"), list):
        return reply["produced"]
    err = ChildError(reply.get("error") if isinstance(reply, dict) else "executor 하위 프로세스 종료 코드 %r: %s" % (
        done.returncode, done.stderr[-300:]))
    err.kind = "interrupted" if done.returncode < 0 else reply.get("kind") if isinstance(reply, dict) \
        and reply.get("kind") in ("transient", "deterministic") else "deterministic"
    raise err


def sandboxed(root, spec):
    """sandbox 안에서 spec(module:ATTR)의 유형 목록을 읽어 {task_type: run_one 부분 적용} dict를 만든다. 실패는 ChildError."""
    done = subprocess.run([SANDBOX_EXEC, "-p", profile(root)] + CHILD + ["list", spec], cwd=REPO, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, errors="replace", check=False)
    try:
        names = json.loads(done.stdout.strip().split("\n")[-1])
    except ValueError:
        names = None
    if done.returncode != 0 or not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ChildError("executor 유형 목록을 읽지 못함(종료 코드 %r): %s" % (done.returncode, done.stderr[-300:]))
    return {name: functools.partial(run_one, root, spec, name) for name in names}

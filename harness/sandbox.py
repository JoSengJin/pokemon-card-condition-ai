"""Python executor를 macOS sandbox-exec 하위 프로세스로 실행한다(작업 계약 3단계 R6, 2차 결함 G1·G2·G6·G7 실행기 경계).

- runner(하네스 상태를 쓰는 프로세스)는 executor 모듈을 가져오지 않는다. 유형 목록 조회와 실행 모두 sandbox 안의 harness.sandbox_child가
  한다(모듈을 가져오는 순간의 코드도 sandbox 안에서 돈다). 그래서 executor 코드는 recovery·claude_perm 같은 등록 목록도 바꿀 수 없다.
- 실행기 경계(2차): 하네스는 executor가 쓸 수 있었던 경로를 믿지 않는다. run_one이 실행마다 하네스 root·저장소 밖에 새 실행 폴더
  (mkdtemp)를 만들고, executor가 쓸 수 있는 곳은 그 안의 out/(staging)·tmp/(TMPDIR)와 장치 파일 DEVICES뿐이다. 확정 out/(root/tasks/<키>/out)
  에는 executor가 쓸 권한이 한 번도 없다. 실행 뒤 하네스가 계약 outputs만 staging에서(실행 전에 연 폴더 fd 기준, 조각마다 O_NOFOLLOW) 일반
  파일·링크 수 1인지 확인하며(링크·하드 링크·FIFO·폴더 거절) 확정 out/에 새 파일로 복사한다(safefs). 그래서 늦게까지 사는 자손이 staging을
  바꾸거나 out 자리를 링크로 바꿔도 확정 산출물과 다음 실행의 허용 범위는 바뀌지 않는다. 실행 폴더는 끝나면 지운다(지운 뒤에는 그 안을
  다시 만들 권한도 없다: 실행 폴더 자체는 허용 목록에 없다).
- 실험·학습·평가 executor는 runner가 실행 직전에 SHA를 확인해 복사한 사본(작업 폴더 in/, sandbox가 쓰기를 허용하지 않는다)을 읽는다:
  환경변수 HARNESS_INPUT_DIR(G6). 원본 폴더 읽기 자체는 막지 않는다(읽기 비거절, 한계).
- 프로세스 그룹: executor 자식은 새 세션(start_new_session)으로 띄우고, 끝나면 그 그룹을 KILL한다(G7). 자식은 runner가 죽으면 0.1초 안에
  자기 그룹째 끝낸다(sandbox_child._watch). 한계: setsid로 새 세션을 만든 자손은 그룹 밖이라 남는다(pid를 모른다). 그런 자손도 sandbox를
  물려받아 그 실행 폴더 밖에는 쓰지 못하고, 확정 out/은 바꾸지 못한다. 표준 출력은 이름 없는 임시 파일로 받아(파이프 아님) 그런 자손이
  쥐고 있어도 runner가 기다리지 않는다.
- 프로필: 쓰기 기본 거절. launchd·LaunchServices·AppleScript를 거쳐 sandbox 밖에서 명령을 돌리는 실행 파일(DENY_EXEC) 실행과 Apple Event
  보내기도 거절한다. 3차 결함 H9: 네트워크 전부(network*: 로컬·외부 TCP·UDP·bind·유닉스 소켓. executor 계약에 네트워크가 필요 없다:
  모델 가중치 내려받기 같은 네트워크가 필요한 executor는 실패하며, 켜려면 별도 결정), localhost 나가기, LaunchServices 열기(lsopen),
  launchservicesd mach-lookup도 거절한다(DENY_MORE). 실제 경로(realpath)로 적는다.
- sandbox-exec가 없거나 시험 실행이 실패하면 available()이 False이고 runner는 executor를 실행하지 않는다(fail-closed).
- 결과: 자식이 마지막 줄에 JSON({"ok": true, "produced"} | {"ok": false, "kind", "error"})을 낸다. 자식이 신호로 죽으면 kind=interrupted
  (runner가 작업권을 남겨 다음 claim이 INTERRUPTED 규칙대로 다룬다), JSON이 없거나 산출물을 거절하면 deterministic.
- 한계(인계): 같은 macOS 사용자의 다른 프로세스(Codex·대화형 Claude·사용자 셸)는 막지 못한다(OS 사용자 분리 D-7 보류). sandbox는 쓰기·
  위 실행 파일·네트워크·lsopen·launchservicesd 조회만 막는다(읽기·프로세스 신호·그 밖의 mach/XPC 서비스는 막지 않는다). executor 코드가
  실행 파일 없이 launchd 자체(bootstrap)나 다른 XPC 서비스에 직접 요청을 보내는 경로는 막지 못한다(시스템 상태를 바꾸는 시험이라 하지 않았다). sandbox-exec는 Apple이 폐기 예정으로 표시한 도구다. 홈 캐시(~/.cache 등)에
  써야 하는 라이브러리는 sandbox 안에서 실패한다(TMPDIR·staging만 쓸 수 있다).
호출 깊이: sandboxed·run_one → profile·safefs.open_regular·safefs.replace_new·safefs.publish(말단) 1.
"""
import errno
import functools
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

from .dedupe import CONDITION_TYPES
from .safefs import open_regular, publish, replace_new

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = [sys.executable, "-m", "harness.sandbox_child"]
DEVICES = ("/dev/null",)  # 쓰기를 허용하는 장치 파일(이것뿐)
DENY_EXEC = ("/bin/launchctl", "/usr/bin/open", "/usr/bin/osascript")  # sandbox 밖(launchd·LaunchServices·AppleScript)에서 명령을 돌리는 도구
MAX_OUTPUT_BYTES = 1 << 30  # 산출물 파일 하나의 크기 상한(임시값 1 GiB, 3차 결함 H4: 넘으면 결정적 실패)
MAX_STDOUT_BYTES = 1 << 24  # sandbox 자식 표준 출력 상한(임시값 16 MiB, 결과 JSON 한 줄이면 충분하다)
DENY_MORE = ('(deny network*)', '(deny network-outbound (remote ip "localhost:*"))', '(deny lsopen)',
             '(deny mach-lookup (global-name "com.apple.coreservices.launchservicesd"))')  # 3차 결함 H9(이 macOS에서 문법·효과 확인)


class ChildError(Exception):
    """sandbox 안 executor의 실패. kind: transient | deterministic | interrupted(신호로 죽음)."""
    kind = "deterministic"


def profile(root, run_dir=None):
    """SBPL 문자열: 쓰기 기본 거절 + run_dir/out·run_dir/tmp·DEVICES만 허용(run_dir 자체와 그 밖 자리는 거절). run_dir은 하네스 root·저장소
    (REPO) 밖이어야 한다. 경로에 따옴표·역슬래시가 있거나 위치가 맞지 않으면 ValueError(프로필을 안전하게 적을 수 없다)."""
    base, run = os.path.realpath(root), os.path.realpath(run_dir) if run_dir else None
    if any('"' in p or "\\" in p for p in [base] + ([run] if run else []) + list(DENY_EXEC)):
        raise ValueError("sandbox 프로필에 쓸 수 없는 경로")
    if run and any(os.path.commonpath([inner, run]) == inner for inner in (base, os.path.realpath(REPO))):
        raise ValueError("실행 폴더는 하네스 root·저장소 밖이어야 한다")
    grant = ['(subpath "%s")' % os.path.join(run, sub) for sub in ("out", "tmp") if run] + ['(literal "%s")' % d for d in DEVICES]
    return "\n".join(['(version 1)', '(allow default)', '(deny file-write*)', '(allow file-write* %s)' % " ".join(grant),
                      '(deny process-exec %s)' % " ".join('(literal "%s")' % p for p in DENY_EXEC), '(deny appleevent-send)']
                     + list(DENY_MORE))


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
    """executor 하나를 sandbox 안에서 실행하고 계약 outputs를 확정 out_dir(하네스 소유)에 새 파일로 반영한다. 정상이면 출력 목록, 실패는
    ChildError(.kind). executor는 실행마다 새로 만든 실행 폴더의 out/(staging)·tmp/(TMPDIR)에만 쓸 수 있다. 실험·학습·평가면 작업 폴더
    in/(runner가 SHA를 확인해 복사한 사본)을 HARNESS_INPUT_DIR로 넘긴다. 실행 폴더는 끝나면 지운다.
    3차 결함: 확정 out/은 실행 전에 O_NOFOLLOW로 연 fd로만 반영한다(링크면 실행하지 않는다, S09). 산출물은 모두 검사해 하네스 소유 임시 폴더
    (작업 폴더의 .out-pending-*)에 연 순간의 fstat 크기까지만 복사한 뒤 한 번에 옮긴다: 하나라도 거절되면 확정 out/은 그대로다(H5).
    산출물 하나가 MAX_OUTPUT_BYTES, 표준 출력이 MAX_STDOUT_BYTES를 넘으면 결정적 실패다(H4)."""
    try:
        os.makedirs(out_dir, exist_ok=True)
        final = os.open(out_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)  # 확정 out/이 링크면 ELOOP: 실행하지 않는다
    except OSError as exc:
        raise ChildError("확정 out/이 링크이거나 폴더가 아니다: %s (%s)" % (out_dir, exc))
    run, pending = tempfile.mkdtemp(prefix="harness-exec-"), None
    stage, env = os.path.join(run, "out"), dict(os.environ, TMPDIR=os.path.join(run, "tmp"))
    if task_type in CONDITION_TYPES:
        env["HARNESS_INPUT_DIR"] = os.path.join(os.path.dirname(os.path.abspath(out_dir)), "in")
    try:
        for sub in ("out", "tmp"):
            os.mkdir(os.path.join(run, sub), 0o700)
        held = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)  # 실행 전에 연 staging: 이름이 바뀌어도 이 폴더만 읽는다
        try:
            with tempfile.TemporaryFile() as said, tempfile.TemporaryFile() as noise:
                child = subprocess.Popen([SANDBOX_EXEC, "-p", profile(root, run)] + CHILD + ["run", spec, task_type, stage], cwd=REPO,
                                         env=env, stdin=subprocess.PIPE, stdout=said, stderr=noise, start_new_session=True)
                child.communicate(json.dumps(task, ensure_ascii=False).encode("utf-8"))
                try:
                    os.killpg(child.pid, signal.SIGKILL)  # 같은 그룹에 남은 자손 정리(setsid 자손은 남는 한계)
                except (ProcessLookupError, PermissionError):
                    pass
                loud = os.fstat(said.fileno()).st_size  # 지금 크기까지만 읽는다(늦은 자손이 계속 써도 따라가지 않는다)
                said.seek(0)
                text = said.read(min(loud, MAX_STDOUT_BYTES + 1)).decode("utf-8", "replace")
                noise.seek(max(0, os.fstat(noise.fileno()).st_size - 300))
                err = noise.read(300).decode("utf-8", "replace")
            try:
                reply = json.loads(text.strip().split("\n")[-1]) if loud <= MAX_STDOUT_BYTES else None
            except ValueError:
                reply = None
            if loud > MAX_STDOUT_BYTES:
                reason, kind = "executor 표준 출력이 상한(%d바이트)을 넘었다: %d" % (MAX_STDOUT_BYTES, loud), "deterministic"
            elif isinstance(reply, dict) and reply.get("ok") is True and isinstance(reply.get("produced"), list):
                if sorted(reply["produced"]) != sorted(task["outputs"]):
                    reason = "executor가 돌려준 출력 목록이 계약의 outputs와 다르다: %r" % (reply["produced"],)
                else:
                    try:  # 계약 outputs만, 링크·하드 링크·특수 파일·폴더·상한 초과를 거절하며 임시 폴더에 모두 복사한 뒤 한 번에 옮긴다
                        pending = tempfile.mkdtemp(prefix=".out-pending-", dir=os.path.dirname(os.path.abspath(out_dir)))
                        for rel in task["outputs"]:
                            src = open_regular(held, rel)
                            try:
                                size = os.fstat(src).st_size
                                if size > MAX_OUTPUT_BYTES:
                                    raise OSError(errno.EFBIG, "산출물이 상한(%d바이트)을 넘었다: %d" % (MAX_OUTPUT_BYTES, size), rel)
                                replace_new(os.path.join(pending, rel), src, limit=size)
                            finally:
                                os.close(src)
                        publish(final, pending, task["outputs"])
                        return reply["produced"]
                    except OSError as exc:
                        reason = "산출물 거절: %s" % exc
                kind = "deterministic"
            else:
                reason = reply.get("error") if isinstance(reply, dict) else "executor 하위 프로세스 종료 코드 %r: %s" % (
                    child.returncode, err)
                kind = "interrupted" if child.returncode < 0 else reply.get("kind") if isinstance(reply, dict) \
                    and reply.get("kind") in ("transient", "deterministic") else "deterministic"
        finally:
            os.close(held)
    finally:
        shutil.rmtree(run, ignore_errors=True)
        if pending:
            shutil.rmtree(pending, ignore_errors=True)
        os.close(final)
    failure = ChildError(reason)
    failure.kind = kind
    raise failure


def sandboxed(root, spec):
    """sandbox 안에서 spec(module:ATTR)의 유형 목록을 읽어 {task_type: run_one 부분 적용} dict를 만든다. 실패는 ChildError."""
    done = subprocess.run([SANDBOX_EXEC, "-p", profile(root)] + CHILD + ["list", spec], cwd=REPO, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, errors="replace", check=False)
    try:
        names = json.loads(done.stdout.strip().split("\n")[-1])
    except ValueError:
        names = None
    if done.returncode != 0 or not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ChildError("executor 유형 목록을 읽지 못함(종료 코드 %r, 실험 executor를 다른 유형 이름으로 감싼 표 포함): %s" % (
            done.returncode, done.stderr[-300:]))
    return {name: functools.partial(run_one, root, spec, name) for name in names}

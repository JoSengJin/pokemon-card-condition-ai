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
  환경변수 HARNESS_INPUT_DIR(G6). 원본 폴더 읽기는 봉인 경로 목록(claude_perm.sealed_paths: 저장소와 runner가 넣은 HARNESS_SOURCE_ROOT
  기준 실제 경로) 아래만 거절한다(deny file-read* subpath, 2026-11-28 이 macOS에서 읽기·stat·목록·링크 경유·하드 링크 만들기 거절 실측).
  목록이 없거나 링크·형식 오류면 sealed_paths가 ValueError(available()은 False, run_one·sandboxed는 executor를 실행하지 않는다).
- 프로세스 그룹: executor 자식은 새 세션(start_new_session)으로 띄우고, 끝나면 그 그룹을 KILL한다(G7). 자식은 runner가 죽으면 0.1초 안에
  자기 그룹째 끝낸다(sandbox_child._watch). 한계: setsid로 새 세션을 만든 자손은 그룹 밖이라 남는다(pid를 모른다). 그런 자손도 sandbox를
  물려받아 그 실행 폴더 밖에는 쓰지 못하고, 확정 out/은 바꾸지 못한다. 표준 출력은 이름 없는 임시 파일로 받아(파이프 아님) 그런 자손이
  쥐고 있어도 runner가 기다리지 않는다.
- 프로필: 쓰기 기본 거절. launchd·LaunchServices·AppleScript를 거쳐 sandbox 밖에서 명령을 돌리는 실행 파일(DENY_EXEC) 실행과 Apple Event
  보내기도 거절한다. 3차 결함 H9: 네트워크 전부(network*: 로컬·외부 TCP·UDP·bind·유닉스 소켓. executor 계약에 네트워크가 필요 없다:
  모델 가중치 내려받기 같은 네트워크가 필요한 executor는 실패하며, 켜려면 별도 결정), localhost 나가기, LaunchServices 열기(lsopen),
  launchservicesd mach-lookup도 거절한다(DENY_MORE). 4차 결함 I7: mach-lookup은 기본 거절이고 MACH_ALLOW(opendirectoryd libinfo = pwd.getpwuid
  사용자 정보 조회, 없으면 KeyError)만 허용한다(DNS·URL 내려받기 데몬·클립보드·로그인 항목·백그라운드 작업 등록·LaunchServices·창 서버·TCC 등
  XPC 서비스 이름을 찾지 못한다). 이 macOS에서 정상 executor 시험·표준 라이브러리 동작(사용자·시각·로케일·임시 파일·하위 프로세스·sqlite·
  ssl 문맥·uuid1·numpy) 확인. 한계: GPU(Metal)·키체인·DNS 등 mach 서비스가 필요한 executor는 실패한다(넓히려면 사용자 결정). 실제 경로(realpath)로 적는다.
- sandbox-exec가 없거나 시험 실행이 실패하면 available()이 False이고 runner는 executor를 실행하지 않는다(fail-closed).
- 결과: 자식이 마지막 줄에 JSON({"ok": true, "produced"} | {"ok": false, "kind", "error"})을 낸다. 자식이 신호로 죽으면 kind=interrupted
  (runner가 작업권을 남겨 다음 claim이 INTERRUPTED 규칙대로 다룬다), JSON이 없거나 산출물을 거절하면 deterministic.
- 한계(인계): 같은 macOS 사용자의 다른 프로세스(Codex·대화형 Claude·사용자 셸)는 막지 못한다(OS 사용자 분리 D-7 보류). sandbox는 쓰기·
  위 실행 파일·네트워크·lsopen·mach 이름 조회(MACH_ALLOW 밖)·봉인 경로 목록 읽기만 막는다(그 밖 읽기·프로세스 신호는 막지 않는다. sandbox
  밖에서 미리 만든 하드 링크는 목록 밖 이름으로 읽힌다. 목록 완전성은 사용자 확인 전). 이미 가진 포트(bootstrap 포트 자체,
  상속받은 포트)로 보내는 요청과 MACH_ALLOW 서비스 요청은 막지 않는다(메시지를 보내는 시험은 하지 않았다). sandbox-exec는 Apple이 폐기 예정으로 표시한 도구다. 홈 캐시(~/.cache 등)에
  써야 하는 라이브러리는 sandbox 안에서 실패한다(TMPDIR·staging만 쓸 수 있다).
- 잔여물(4차 결함 I9): runner가 반영 중 kill되면 작업 폴더의 .out-pending-*와 실행 폴더 harness-exec-<task_key>-*가 남는다. 다음 runner가 그 작업의
  작업권을 잡은 뒤 sweep이 지운다(queue.claim). 산출물 합계 크기 상한은 MAX_TOTAL_OUTPUT_BYTES.
호출 깊이: available·sandboxed·run_one → profile·claude_perm.sealed_paths(말단, 호출자가 읽어 profile에 넘긴다) 1, run_one → safefs.open_regular·safefs.replace_new·safefs.publish(말단) 1, sweep 0(queue.claim에서 부른다).
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

from .claude_perm import outside_roots, sealed_paths
from .dedupe import CONDITION_TYPES
from .experiment_exec import SOURCE_ENV
from .safefs import open_regular, publish, replace_new

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHILD = [sys.executable, "-m", "harness.sandbox_child"]
DEVICES = ("/dev/null",)  # 쓰기를 허용하는 장치 파일(이것뿐)
DENY_EXEC = ("/bin/launchctl", "/usr/bin/open", "/usr/bin/osascript")  # sandbox 밖(launchd·LaunchServices·AppleScript)에서 명령을 돌리는 도구
MAX_OUTPUT_BYTES = 1 << 30  # 산출물 파일 하나의 크기 상한(임시값 1 GiB, 3차 결함 H4: 넘으면 결정적 실패)
MAX_STDOUT_BYTES = 1 << 24  # sandbox 자식 표준 출력 상한(임시값 16 MiB, 결과 JSON 한 줄이면 충분하다)
MAX_TOTAL_OUTPUT_BYTES = 1 << 32  # 한 실행의 산출물 합계 크기 상한(임시값 4 GiB, 4차 결함 I9: 넘으면 결정적 실패)
RUN_PREFIX, PENDING_PREFIX = "harness-exec-", ".out-pending-"  # 실행 폴더(시스템 임시 폴더, + task_key) / 반영 임시 폴더(작업 폴더)
REGEX_ESCAPE = {ord(c): "\\" + c for c in ".+()[]{}|^$?"}  # 봉인 경로 목록의 *가 든 항목을 SBPL regex로: 글자는 이스케이프, *는 한 폴더 이름 안(슬래시 제외)
REGEX_ESCAPE[ord("*")] = "[^/]*"
MACH_ALLOW = ("com.apple.system.opendirectoryd.libinfo",)  # 4차 I7: 기본 거절 뒤 허용하는 mach 이름(사용자 정보 조회 pwd.getpwuid, 읽기)
DENY_MORE = ('(deny network*)', '(deny network-outbound (remote ip "localhost:*"))', '(deny lsopen)',
             '(deny mach-lookup (global-name "com.apple.coreservices.launchservicesd"))',  # 3차 결함 H9(이 macOS에서 문법·효과 확인)
             '(deny mach-lookup)') + tuple('(allow mach-lookup (global-name "%s"))' % n for n in MACH_ALLOW)  # 4차 결함 I7


class ChildError(Exception):
    """sandbox 안 executor의 실패. kind: transient | deterministic | interrupted(신호로 죽음 또는 자식이 알린 결과 불명).
    status: 자식이 결과 줄로 알린 executor 상태(실험 어댑터의 not_started 등, 없으면 None)."""
    kind = "deterministic"
    status = None


def profile(root, run_dir, sealed, outside=()):
    """SBPL 문자열: 쓰기 기본 거절 + run_dir/out·run_dir/tmp·DEVICES만 허용(run_dir 자체와 그 밖 자리는 거절). run_dir은 하네스 root·저장소
    (REPO) 밖이어야 한다. 경로에 따옴표·역슬래시가 있거나 위치가 맞지 않으면 ValueError(프로필을 안전하게 적을 수 없다).
    sealed(호출자가 claude_perm.sealed_paths로 읽은 실제 경로 목록)의 읽기는 거절한다. 비어 있으면 ValueError(목록 없이 만들지 않는다).
    outside(claude_perm.outside_roots: 저장소 밖 다른 작업 폴더 루트, 사용자 D4)는 루트 전체 읽기를 거절하되 이 python의 prefix(venv 등)가 그 안에
    있으면 그 폴더만 다시 허용한다(sealed 거절은 그 뒤라 우선). 하네스 root·실행 폴더가 outside 루트 안이면 ValueError(읽을 수 없게 된다)."""
    base, run = os.path.realpath(root), os.path.realpath(run_dir) if run_dir else None
    if not sealed:
        raise ValueError("봉인 경로 목록 없이 sandbox 프로필을 만들지 않는다")
    if any('"' in p or "\\" in p for p in [base] + ([run] if run else []) + list(DENY_EXEC) + sealed + list(outside)):
        raise ValueError("sandbox 프로필에 쓸 수 없는 경로")
    if run and any(os.path.commonpath([inner, run]) == inner for inner in (base, os.path.realpath(REPO))):
        raise ValueError("실행 폴더는 하네스 root·저장소 밖이어야 한다")
    if any(os.path.commonpath([r, p]) == r for r in outside for p in [base] + ([run] if run else [])):
        raise ValueError("하네스 root·실행 폴더가 저장소 밖 봉인 루트 안에 있다")
    grant = ['(subpath "%s")' % os.path.join(run, sub) for sub in ("out", "tmp") if run] + ['(literal "%s")' % d for d in DEVICES]
    lines = ['(version 1)', '(allow default)']
    if outside:
        lines.append('(deny file-read* %s)' % " ".join('(subpath "%s")' % p for p in outside))
        keep = {os.path.realpath(p) for p in (sys.prefix, sys.exec_prefix)}  # 이 python의 환경(venv)이 막은 루트 안이면 그것만 다시 읽게 한다
        lines += ['(allow file-read* (subpath "%s"))' % p for p in sorted(keep) if any(os.path.commonpath([r, p]) == r for r in outside)]
    # *가 든 항목은 regex(그 경로 또는 그 아래): 프로필을 만든 뒤 sandbox 밖에서 새로 생긴 파일도 막는다(실행 중 실측: 생성 시점·대소문자 변형 무관)
    rules = ['(regex #"^%s(/.*)?$")' % p.translate(REGEX_ESCAPE) if "*" in p else '(subpath "%s")' % p for p in sealed]
    return "\n".join(lines + ['(deny file-read* %s)' % " ".join(rules),
                      '(deny file-write*)', '(allow file-write* %s)' % " ".join(grant),
                      '(deny process-exec %s)' % " ".join('(literal "%s")' % p for p in DENY_EXEC), '(deny appleevent-send)']
                     + list(DENY_MORE))


def available():
    """sandbox-exec로 실제 하위 프로세스를 띄워 쓰기 거절 프로필이 적용되는지 확인한다. 실패·없음은 False."""
    if not os.path.isfile(SANDBOX_EXEC):
        return False
    try:
        done = subprocess.run([SANDBOX_EXEC, "-p", profile(REPO, None, sealed_paths([REPO, os.environ.get(SOURCE_ENV)]), outside_roots([REPO, os.environ.get(SOURCE_ENV)])), "/usr/bin/true"], stdin=subprocess.DEVNULL,
                              capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError, ValueError):  # ValueError: 봉인 경로 목록 없음·링크·형식 오류(fail-closed)
        return False
    return done.returncode == 0


def run_one(root, spec, task_type, task, out_dir):
    """executor 하나를 sandbox 안에서 실행하고 계약 outputs를 확정 out_dir(하네스 소유)에 새 파일로 반영한다. 정상이면 출력 목록, 실패는
    ChildError(.kind). executor는 실행마다 새로 만든 실행 폴더의 out/(staging)·tmp/(TMPDIR)에만 쓸 수 있다. 실험·학습·평가면 작업 폴더
    in/(runner가 SHA를 확인해 복사한 사본)을 HARNESS_INPUT_DIR로 넘긴다. 실행 폴더는 끝나면 지운다.
    3차 결함: 확정 out/은 실행 전에 O_NOFOLLOW로 연 fd로만 반영한다(링크면 실행하지 않는다, S09). 산출물은 모두 검사해 하네스 소유 임시 폴더
    (작업 폴더의 .out-pending-*)에 연 순간의 fstat 크기까지만 복사한 뒤 한 번에 옮긴다: 하나라도 거절되면 확정 out/은 그대로다(H5).
    산출물 하나가 MAX_OUTPUT_BYTES, 표준 출력이 MAX_STDOUT_BYTES를 넘으면 결정적 실패다(H4)."""
    sealed = sealed_paths([REPO, os.environ.get(SOURCE_ENV)])  # 봉인 경로 목록 오류면 ValueError: 아무것도 만들거나 실행하지 않는다
    outside = outside_roots([REPO, os.environ.get(SOURCE_ENV)])  # 저장소 밖 봉인 루트(목록 파일 + git worktree list) 오류도 ValueError
    try:
        os.makedirs(out_dir, exist_ok=True)
        final = os.open(out_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)  # 확정 out/이 링크면 ELOOP: 실행하지 않는다
    except OSError as exc:
        raise ChildError("확정 out/이 링크이거나 폴더가 아니다: %s (%s)" % (out_dir, exc))
    run, pending, status = tempfile.mkdtemp(prefix="%s%s-" % (RUN_PREFIX, os.path.basename(os.path.dirname(os.path.abspath(out_dir))))), None, None
    stage, env = os.path.join(run, "out"), dict(os.environ, TMPDIR=os.path.join(run, "tmp"))
    if task_type in CONDITION_TYPES:
        env["HARNESS_INPUT_DIR"] = os.path.join(os.path.dirname(os.path.abspath(out_dir)), "in")
    try:
        for sub in ("out", "tmp"):
            os.mkdir(os.path.join(run, sub), 0o700)
        held = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)  # 실행 전에 연 staging: 이름이 바뀌어도 이 폴더만 읽는다
        try:
            with tempfile.TemporaryFile() as said, tempfile.TemporaryFile() as noise:
                child = subprocess.Popen([SANDBOX_EXEC, "-p", profile(root, run, sealed, outside)] + CHILD + ["run", spec, task_type, stage], cwd=REPO,
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
                        pending, total = tempfile.mkdtemp(prefix=PENDING_PREFIX, dir=os.path.dirname(os.path.abspath(out_dir))), 0
                        for rel in task["outputs"]:
                            src = open_regular(held, rel)
                            try:
                                size = os.fstat(src).st_size
                                total += size
                                if size > MAX_OUTPUT_BYTES:
                                    raise OSError(errno.EFBIG, "산출물이 상한(%d바이트)을 넘었다: %d" % (MAX_OUTPUT_BYTES, size), rel)
                                if total > MAX_TOTAL_OUTPUT_BYTES:  # 4차 결함 I9
                                    raise OSError(errno.EFBIG, "산출물 합계가 상한(%d바이트)을 넘었다: %d" % (MAX_TOTAL_OUTPUT_BYTES, total), rel)
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
                # 자식이 알린 interrupted(실험 결과 불명)도 받는다: executor가 스스로 신호로 죽어 얻을 수 있던 종류라 권한이 넓어지지 않는다(B5-8)
                kind = "interrupted" if child.returncode < 0 else reply.get("kind") if isinstance(reply, dict) \
                    and reply.get("kind") in ("transient", "deterministic", "interrupted") else "deterministic"
                status = reply.get("status") if isinstance(reply, dict) and isinstance(reply.get("status"), str) else None
        finally:
            os.close(held)
    finally:
        shutil.rmtree(run, ignore_errors=True)
        if pending:
            shutil.rmtree(pending, ignore_errors=True)
        os.close(final)
    failure = ChildError(reason)
    failure.kind = kind
    failure.status = status  # 자식 결과 줄(ok=false)에서만 정해진다
    raise failure


def sweep(task_dir):
    """작업 폴더 task_dir(root/tasks/<task_key>)의 이전 실행 잔여물을 지운다(4차 결함 I9): 작업 폴더의 PENDING_PREFIX* 폴더와 시스템 임시 폴더의
    RUN_PREFIX<task_key>-* 폴더. 그 작업의 작업권(잠금)을 잡고 이전 주인이 죽었다고 판정한 뒤에만 부른다(queue.claim): 그 작업을 반영 중인 runner가
    없다. 링크·폴더가 아닌 항목은 건드리지 않는다(따라가지 않는다). 지우지 못한 것은 그대로 둔다(최선 노력, 다음 claim이 다시 지운다)."""
    key = os.path.basename(os.path.normpath(task_dir))
    for folder, prefix in ((task_dir, PENDING_PREFIX), (tempfile.gettempdir(), "%s%s-" % (RUN_PREFIX, key))):
        try:
            names = [n for n in os.listdir(folder) if n.startswith(prefix)]
        except OSError:
            continue
        for name in names:
            path = os.path.join(folder, name)
            if not os.path.islink(path) and os.path.isdir(path):
                shutil.rmtree(path, ignore_errors=True)


def sandboxed(root, spec):
    """sandbox 안에서 spec(module:ATTR)의 유형 목록을 읽어 {task_type: run_one 부분 적용} dict를 만든다. 실패는 ChildError."""
    done = subprocess.run([SANDBOX_EXEC, "-p", profile(root, None, sealed_paths([REPO, os.environ.get(SOURCE_ENV)]), outside_roots([REPO, os.environ.get(SOURCE_ENV)]))] + CHILD + ["list", spec], cwd=REPO, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, errors="replace", check=False)
    try:
        names = json.loads(done.stdout.strip().split("\n")[-1])
    except ValueError:
        names = None
    if done.returncode != 0 or not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ChildError("executor 유형 목록을 읽지 못함(종료 코드 %r, 실험 executor를 다른 유형 이름으로 감싼 표 포함): %s" % (
            done.returncode, done.stderr[-300:]))
    return {name: functools.partial(run_one, root, spec, name) for name in names}

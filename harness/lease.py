"""작업권: fcntl.flock 배타 잠금 + pid·부팅 식별자·획득 시각 기록.

판단(상태 분류, 실행 여부)을 잠금 안에서 하려고 2단계로 나눈다: lock()으로 잠금을 잡고
이전 기록을 읽은 뒤, 실행하기로 정해지면 stamp()로 내 기록을 쓴다(= 명세의 acquire).

전제: 작업권(잠금 fd)을 쥔 프로세스가 끝까지 실행하고 exec하지 않는다. 잠금은 fd에 걸려 있어
(Python 기본 close-on-exec) exec하거나 fd가 닫히면 풀리고, 기록된 pid만 남는다. 이 경우를 이중 실행으로
이어지지 않게 하는 판정은 holder.py와 queue.claim(pid==os.getpid() 강제)에 있다.
"""
import collections
import errno
import fcntl
import json
import os
import re
import subprocess

Lease = collections.namedtuple("Lease", "fd path previous")


class LeaseError(Exception):
    pass


def boot_id(output=None):
    """부팅 식별자(macOS kern.boottime의 sec). 조회·해석 실패는 오류이며 추정하지 않는다."""
    if output is None:
        try:
            output = subprocess.run(["sysctl", "-n", "kern.boottime"], capture_output=True,
                                    text=True, check=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError) as exc:
            raise LeaseError("부팅 식별자 조회 실패: %s" % exc)
    found = re.search(r"sec\s*=\s*(\d+)", output)
    if not found:
        raise LeaseError("부팅 식별자 해석 실패: %r" % (output,))
    return found.group(1)


def pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def is_alive(lease, boot_id_fn=boot_id, pid_alive=pid_alive):
    """부팅 식별자가 같고 pid가 살아 있을 때만 True. 기록이 없거나 깨졌으면 False."""
    if not lease or not isinstance(lease.get("pid"), int) or isinstance(lease.get("pid"), bool):
        return False
    return lease.get("boot_id") == boot_id_fn() and pid_alive(lease["pid"])


def read(path):
    """작업권 파일 내용. 없거나 비었으면 None(작업권 없음), 깨졌으면 {}(죽은 작업권)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except FileNotFoundError:
        return None
    if not text.strip():
        return None
    try:
        record = json.loads(text)
    except ValueError:
        return {}
    return record if isinstance(record, dict) else {}


def lock(path):
    """비차단 배타 잠금. 다른 프로세스가 쥐고 있으면 None. 잡았으면 Lease(이전 기록 포함)."""
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        if exc.errno in (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES):
            return None
        raise
    try:
        same = os.path.samestat(os.fstat(fd), os.stat(path))
    except FileNotFoundError:
        same = False
    if not same:  # 잠금을 기다리는 사이 다른 쪽이 파일을 지우고 새로 만들었다: 잡은 잠금은 무효
        os.close(fd)
        return None
    return Lease(fd, path, read(path))


def stamp(handle, pid, boot, now, extra=None):
    record = {"pid": pid, "boot_id": boot, "ts": now}
    record.update(extra or {})
    data = json.dumps(record, sort_keys=True).encode("utf-8")
    os.ftruncate(handle.fd, 0)
    os.pwrite(handle.fd, data, 0)
    os.fsync(handle.fd)
    return record


def release(handle, remove=False):
    """잠금 해제. remove=True이거나 아무것도 기록하지 않은 빈 파일이면 파일도 지운다."""
    try:
        if remove or os.fstat(handle.fd).st_size == 0:
            try:
                os.unlink(handle.path)
            except FileNotFoundError:
                pass
    finally:
        os.close(handle.fd)

"""하네스 파일 쓰기·신뢰하지 않는 폴더 읽기의 기본 동작(2차 결함 G1·G2·G6: 실행기 경계). 모든 함수는 말단이다(다른 harness 함수를 부르지 않는다).

- replace_new: 같은 폴더에 tempfile.mkstemp(O_CREAT|O_EXCL, 임의 이름) 새 파일을 만들어 내용을 쓰고 fsync한 뒤 os.replace한다. 예측 가능한
  임시 이름(<대상>.tmp.<pid>)을 쓰지 않으므로 그 자리에 미리 깔린 링크를 따라 쓰지 않는다. 대상이나 대상 폴더가 심볼릭 링크면 쓰지 않는다
  (ELOOP). expect를 주면 실제로 쓴 내용의 sha256이 같을 때만 교체한다(다르면 ValueError, 대상은 그대로).
- publish: 하네스가 다 검사·복사한 임시 폴더의 산출물을 확정 폴더(fd) 아래로 옮긴다. 중간 폴더를 모두 O_NOFOLLOW로 연 뒤에야 옮긴다.
- open_regular: 신뢰하지 않는 폴더(호출자가 미리 연 fd) 아래 상대 경로를 한 조각씩 O_NOFOLLOW로 연다(중간 폴더·마지막 파일 어느 것도
  링크를 따라가지 않는다). 마지막은 일반 파일이고 링크 수가 1이어야 한다(하드 링크·FIFO·장치·소켓·폴더 거절. O_NONBLOCK이라 FIFO에서
  멈추지 않는다). 검사는 열린 fd 기준(fstat)이라 검사와 읽기 사이에 이름이 바뀌어도 연 파일만 읽는다.
한계: replace_new는 대상과 그 바로 위 폴더만 링크 검사한다. 더 위 경로는 호출자가 하네스 소유 경로(executor·Claude가 쓸 수 없는 root 아래)로 준다.
"""
import errno
import hashlib
import os
import stat
import tempfile


def replace_new(path, source, expect=None, limit=None):
    """path 자리에 새 파일을 원자적으로 만든다. source: bytes 또는 읽기 fd(현재 위치부터 끝까지, limit을 주면 그 바이트 수까지만 복사:
    3차 결함 H4, 복사 중에 커지는 파일을 따라가지 않는다). 쓴 내용의 sha256을 돌려준다."""
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    if os.path.islink(folder) or os.path.islink(path):
        raise OSError(errno.ELOOP, "링크인 대상·폴더에는 쓰지 않는다", path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=os.path.basename(path) + ".tmp.")
    digest = hashlib.sha256()
    try:
        with os.fdopen(fd, "wb") as handle:
            left = None if isinstance(source, bytes) else limit
            while left is None or left > 0:
                chunk = source if isinstance(source, bytes) else os.read(source, 1 << 20 if left is None else min(1 << 20, left))
                if not chunk:
                    break
                digest.update(chunk)
                handle.write(chunk)
                if isinstance(source, bytes):
                    break
                left = None if left is None else left - len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        if expect is not None and digest.hexdigest() != expect:
            raise ValueError("쓴 내용의 sha256이 기대와 다르다(복사 중 원본이 바뀌었거나 손상): %s" % path)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise
    return digest.hexdigest()


def open_regular(dir_fd, rel):
    """dir_fd 아래 rel("a/b.txt")을 링크를 따라가지 않고 읽기로 연 fd. 일반 파일·링크 수 1이 아니면 OSError(호출자가 fd를 닫는다)."""
    parts = rel.split("/") if isinstance(rel, str) else [""]
    if any(p in ("", ".", "..") for p in parts):
        raise OSError(errno.EINVAL, "안전한 상대 경로가 아니다", rel)
    cur = dir_fd
    try:
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur)
            if cur != dir_fd:
                os.close(cur)
            cur = nxt
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=cur)
    finally:
        if cur != dir_fd:
            os.close(cur)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise OSError(errno.EINVAL, "일반 파일(링크 수 1)이 아니다", rel)
    return fd


def publish(dir_fd, staged, rels):
    """하네스가 쓴 폴더 staged 아래 rels를 dir_fd 폴더 아래 같은 상대 경로로 옮긴다(3차 결함 H5·S09: 확정 out/ 반영은 한 번에).
    먼저 모든 중간 폴더를 O_NOFOLLOW로 열고(없으면 만든다) 대상 자리가 폴더가 아닌지 본 뒤에야 옮긴다: 링크·폴더가 하나라도 있으면
    하나도 옮기지 않고 OSError(빈 중간 폴더만 남을 수 있다). 옮기기는 같은 파일 시스템 안 os.replace(dst_dir_fd)다."""
    opened, moves = [], []
    try:
        for rel in rels:
            parts, cur = rel.split("/"), dir_fd
            for part in parts[:-1]:
                try:
                    os.mkdir(part, 0o700, dir_fd=cur)
                except FileExistsError:
                    pass
                cur = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=cur)
                opened.append(cur)
            try:
                if stat.S_ISDIR(os.lstat(parts[-1], dir_fd=cur).st_mode):
                    raise OSError(errno.EISDIR, "확정 산출물 자리가 폴더다", rel)
            except FileNotFoundError:
                pass
            moves.append((os.path.join(staged, rel), parts[-1], cur))
        for src, name, fd in moves:
            os.replace(src, name, dst_dir_fd=fd)
    finally:
        for fd in opened:
            os.close(fd)

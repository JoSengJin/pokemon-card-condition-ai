"""내용 주소 저장소(CAS). CORRUPT 복구 전용: 산출물 사본을 sha256 이름으로 보관한다.

호출 깊이 설계: sha_file·blob_path는 다른 함수를 부르지 않는 말단이고, 나머지(has·put·get·restore)는
말단(sha_file·blob_path·safefs.replace_new)만 부른다(has/put/restore 사이의 호출 없음).
쓰기(2차 결함 G1): 예측 가능한 임시 이름(<대상>.tmp.<pid>) + shutil.copyfile은 그 자리에 깔린 링크를 따라 링크 대상을 덮어쓴다
(sandbox 밖 프로세스가 executor 대신 임의 파일을 쓰게 된다). 그래서 모든 쓰기는 safefs.replace_new(mkstemp 새 파일 + os.replace,
대상·대상 폴더 링크 거절, 쓴 내용 해시 확인 뒤 교체)로 한다.
"""
import hashlib
import os

from .safefs import replace_new


class CasError(Exception):
    pass


def sha_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def blob_path(cas_root, sha):
    if not isinstance(sha, str) or len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
        raise CasError("sha256 형식이 아니다: %r" % (sha,))
    return os.path.join(cas_root, sha[:2], sha)


def has(cas_root, sha):
    """보관본이 있고 내용 해시가 이름과 같을 때만 True(손상된 보관본은 없는 것으로 본다)."""
    blob = blob_path(cas_root, sha)
    return os.path.isfile(blob) and sha_file(blob) == sha


def put(cas_root, path):
    sha = sha_file(path)
    blob = blob_path(cas_root, sha)
    if os.path.isfile(blob) and sha_file(blob) == sha:  # has()와 같은 검사(말단만 부르려고 펼침)
        return sha
    fd = os.open(path, os.O_RDONLY)
    try:
        replace_new(blob, fd, expect=sha)
    except ValueError:
        raise CasError("복사 중 원본이 바뀌었다: %s" % path)
    finally:
        os.close(fd)
    return sha


def restore(cas_root, items):
    """items: [(sha, dest)]. 보관본 해시를 확인한 뒤 dest로 원자 복사. 복구하지 못한 dest 목록을 돌려준다."""
    failed = []
    for sha, dest in items:
        try:
            blob = blob_path(cas_root, sha)
            if not os.path.isfile(blob) or sha_file(blob) != sha:
                raise CasError("보관본이 없거나 손상됨: %s" % sha)
            fd = os.open(blob, os.O_RDONLY)
            try:
                replace_new(dest, fd, expect=sha)  # 대상·대상 폴더가 링크면 OSError(복구하지 않는다)
            finally:
                os.close(fd)
        except (CasError, OSError, ValueError):
            failed.append(dest)
    return failed


def get(cas_root, sha, dest):
    """restore의 단일 파일판. 없거나 손상이면 CasError. 호출 깊이를 줄이려고 말단만 부른다(restore와 같은 검사·원자 복사)."""
    blob = blob_path(cas_root, sha)
    try:
        if not os.path.isfile(blob) or sha_file(blob) != sha:  # 읽기 실패(권한 등)도 아래에서 CasError가 된다
            raise CasError("보관본이 없거나 손상됨: %s" % sha)
        fd = os.open(blob, os.O_RDONLY)
        try:
            replace_new(dest, fd, expect=sha)
        finally:
            os.close(fd)
    except (OSError, ValueError):
        raise CasError("보관본을 꺼내지 못함: %s" % sha)

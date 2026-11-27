"""내용 주소 저장소(CAS). CORRUPT 복구 전용: 산출물 사본을 sha256 이름으로 보관한다.

호출 깊이 설계: sha_file·blob_path는 다른 함수를 부르지 않는 말단이고, 나머지(has·put·get·restore)는
말단만 부른다(has/put/restore 사이의 호출 없음).
"""
import hashlib
import os
import shutil


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
    os.makedirs(os.path.dirname(blob), exist_ok=True)
    tmp = "%s.tmp.%d" % (blob, os.getpid())
    shutil.copyfile(path, tmp)
    if sha_file(tmp) != sha:
        os.unlink(tmp)
        raise CasError("복사 중 원본이 바뀌었다: %s" % path)
    os.replace(tmp, blob)
    return sha


def restore(cas_root, items):
    """items: [(sha, dest)]. 보관본 해시를 확인한 뒤 dest로 원자 복사. 복구하지 못한 dest 목록을 돌려준다."""
    failed = []
    for sha, dest in items:
        try:
            blob = blob_path(cas_root, sha)
            if not os.path.isfile(blob) or sha_file(blob) != sha:
                raise CasError("보관본이 없거나 손상됨: %s" % sha)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            tmp = "%s.tmp.%d" % (dest, os.getpid())
            shutil.copyfile(blob, tmp)
            os.replace(tmp, dest)
        except (CasError, OSError):
            failed.append(dest)
    return failed


def get(cas_root, sha, dest):
    """restore의 단일 파일판. 없거나 손상이면 CasError. 호출 깊이를 줄이려고 말단만 부른다(restore와 같은 검사·원자 복사)."""
    blob = blob_path(cas_root, sha)
    if not os.path.isfile(blob) or sha_file(blob) != sha:
        raise CasError("보관본이 없거나 손상됨: %s" % sha)
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = "%s.tmp.%d" % (dest, os.getpid())
        shutil.copyfile(blob, tmp)
        os.replace(tmp, dest)
    except OSError:
        raise CasError("보관본을 꺼내지 못함: %s" % sha)

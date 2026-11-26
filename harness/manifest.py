"""출력 manifest: 산출물 상대 경로 -> sha256. 완료 인정은 이 해시 검증뿐이다."""
import os

from .cas import sha_file


def safe_path(out_dir, rel):
    """out_dir/rel 경로. out_dir과 rel의 중간 폴더가 심볼릭 링크이거나 실제 위치가 out_dir 밖이면 None.

    마지막 구성요소(파일)가 링크인지는 호출자가 islink로 따로 본다. 파일이 아직 없어도 경로는 돌려준다(복구 대상).
    검사와 사용 사이의 경쟁(TOCTOU)은 막지 못한다(단일 소유자 전제).
    """
    parts = rel.split("/") if isinstance(rel, str) else [""]
    if not isinstance(rel, str) or any(p in ("", ".", "..") for p in parts):
        return None  # 절대 경로("/x"는 첫 조각이 "")·상위 이동·빈 조각 거절
    cur = out_dir
    for part in [""] + parts[:-1]:
        cur = os.path.join(cur, part) if part else cur
        if os.path.islink(cur):
            return None
    real_out = os.path.realpath(out_dir)
    if os.path.commonpath([real_out, os.path.realpath(os.path.dirname(os.path.join(out_dir, rel)))]) != real_out:
        return None
    return os.path.join(out_dir, rel)


def build(out_dir, outputs):
    """모든 선언 산출물의 해시. 없거나 링크를 거치면 오류(부분 완료·root 밖 읽기 금지)."""
    result = {}
    for rel in outputs:
        path = safe_path(out_dir, rel)
        if path is None or os.path.islink(path):
            raise ValueError("산출물 경로가 out/ 밖이거나 심볼릭 링크를 거친다: %s" % rel)
        result[rel] = sha_file(path)
    return result


def mismatches(out_dir, manifest, expected):
    """manifest와 어긋난 상대 경로 목록(없음·변조·링크·선언과 키 집합 불일치). 빈 목록이어야 통과."""
    if not isinstance(manifest, dict):
        return sorted(expected)
    bad = set(manifest) ^ set(expected)
    for rel in set(manifest) & set(expected):
        path = os.path.join(out_dir, rel)
        if safe_path(out_dir, rel) is None:
            bad.add(rel)
        elif os.path.islink(path) or not os.path.isfile(path) or sha_file(path) != manifest[rel]:
            bad.add(rel)
    return sorted(bad)

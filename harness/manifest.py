"""출력 manifest: 산출물 상대 경로 -> sha256. 완료 인정은 이 해시 검증뿐이다."""
import os

from .cas import sha_file


def build(out_dir, outputs):
    """모든 선언 산출물의 해시. 하나라도 없으면 FileNotFoundError(부분 완료 금지)."""
    result = {}
    for rel in outputs:
        path = os.path.join(out_dir, rel)
        if os.path.islink(path):
            raise ValueError("산출물이 심볼릭 링크다: %s" % rel)
        result[rel] = sha_file(path)
    return result


def mismatches(out_dir, manifest, expected):
    """manifest와 어긋난 상대 경로 목록(없음·변조·심볼릭 링크·선언과 키 집합 불일치). 빈 목록이어야 통과."""
    if not isinstance(manifest, dict):
        return sorted(expected)
    bad = set(manifest) ^ set(expected)
    for rel in set(manifest) & set(expected):
        path = os.path.join(out_dir, rel)
        if os.path.islink(path) or not os.path.isfile(path) or sha_file(path) != manifest[rel]:
            bad.add(rel)
    return sorted(bad)

"""출력 manifest: 산출물 상대 경로 -> sha256. 완료 인정은 이 해시 검증뿐이다.

검증(어긋남 계산)은 states.facts가 safe_path·sha_file을 직접 불러 한다(호출 깊이 설계).
"""
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
    """모든 선언 산출물의 해시. 없거나(FileNotFoundError) 링크를 거치거나 일반 파일이 아니면(폴더·FIFO 등: 읽다가 멈추지 않게, ValueError) 오류(부분 완료·root 밖 읽기 금지)."""
    result = {}
    for rel in outputs:
        path = safe_path(out_dir, rel)
        if path is None or os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):  # 없으면 아래에서 FileNotFoundError
            raise ValueError("산출물 경로가 out/ 밖이거나 심볼릭 링크를 거치거나 일반 파일이 아니다: %s" % rel)
        result[rel] = sha_file(path)
    return result

"""JSON 원자 저장·읽기. 쓰기는 같은 폴더의 새 임시 파일(mkstemp: O_EXCL·임의 이름) + fsync + os.replace로 교체한다.

2차 결함 G1: 예측 가능한 임시 이름(<대상>.tmp.<pid>)은 그 자리에 깔린 링크를 따라 링크 대상에 쓴다. 그래서 safefs.replace_new와 같은 방식으로
쓰고, 대상이나 대상 폴더가 심볼릭 링크면 쓰지 않는다(OSError ELOOP). 호출 깊이를 늘리지 않으려고 safefs를 부르지 않고 같은 단계를 여기에
펼쳤다(write_json은 깊이 4 경로의 말단이다: runner.main → drain → queue.claim → recovery.decide → write_json). 임시 이름에 ".tmp."를 남긴다
(pointer.clean_tmp가 kill로 남은 임시 파일을 찾는 규칙).
"""
import errno
import json
import os
import tempfile


def write_json(path, obj):
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    if os.path.islink(folder) or os.path.islink(path):
        raise OSError(errno.ELOOP, "링크인 대상·폴더에는 쓰지 않는다", path)
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=os.path.basename(path) + ".tmp.")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def read_json(path, default=None, **options):
    """파일이 없으면 default. 내용이 깨졌으면 ValueError(추정하지 않는다). options는 json.load에 그대로 넘긴다(parse_int 등)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle, **options)
    except FileNotFoundError:
        return default

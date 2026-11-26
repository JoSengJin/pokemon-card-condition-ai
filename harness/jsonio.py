"""JSON 원자 저장·읽기. 쓰기는 임시 파일 + os.replace로 교체한다."""
import json
import os


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, sort_keys=True, ensure_ascii=False, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def read_json(path, default=None):
    """파일이 없으면 default. 내용이 깨졌으면 ValueError(추정하지 않는다)."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default

"""답 글 읽기와 원본 보존 (계약 C). 값은 있는 그대로 읽고, 모르는 줄·중복·빠진 머리 줄은 조용히 버리지 않고 거절한다."""
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

VALUES = ('정상', '결함', '불가', '미확인')  # 판단 불가·미확인도 값 그대로. 정상·결함으로 채우지 않는다
STAMP = re.compile(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d')


def parse(text):
    """화면이 만든 글 -> (page_id, 제출시각 문자열, {z번호: 값}). 줄 끝 공백·CRLF는 값에 영향이 없다. 어긋나면 ValueError(이유 한 줄)."""
    head, rows = {}, {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        name, equal, value = (line[1:] if line.startswith('#') else line).partition('=')
        name, value = name.strip(), value.strip()
        if line.startswith('#'):
            if name not in ('화면', '제출시각') or name in head or not equal:
                raise ValueError(f'알 수 없거나 겹친 # 줄: {line}')
            head[name] = value
            continue
        if not equal or not re.fullmatch(r'z\d+', name) or value not in VALUES or name in rows:
            raise ValueError(f'알 수 없거나 겹친 답 줄(모르는 값 포함): {line}')
        rows[name] = value
    if lost := [f'"# {k}=" 줄' for k in ('화면', '제출시각') if not head.get(k)]:
        raise ValueError(f'빠진 줄: {", ".join(lost)}. 화면이 만든 글 전체를 그대로 붙여넣어야 함')
    if not STAMP.fullmatch(head['제출시각']):
        raise ValueError(f'제출시각에 시간대(+09:00 꼴)가 없거나 형식이 다름: {head["제출시각"]}')
    datetime.fromisoformat(head['제출시각'])
    return head['화면'], head['제출시각'], rows


def keep_raw(folder, data):
    """원본 바이트를 <folder>/<sha256>.txt(0444)로 보존하고 SHA-256을 돌려준다. 같은 바이트가 있으면 그대로 둔다."""
    digest = hashlib.sha256(data).hexdigest()
    path = Path(folder) / f'{digest}.txt'
    if not path.exists():
        temp = path.with_suffix('.tmp')
        temp.write_bytes(data)  # 쓰다 끊기면 temp만 남고 원본 이름은 생기지 않는다
        os.rename(temp, path)
    elif path.read_bytes() != data:
        raise ValueError(f'보존된 원본이 같은 이름인데 바이트가 다름: {path}')
    os.chmod(path, 0o444)
    return digest

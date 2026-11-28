"""Provenance record beside a label page / import output: which criteria text and which photo crops were shown (docs/agent/QUALITY_RULES.md label-provenance)."""
import base64
import hashlib
import json
import re
from html import unescape
from pathlib import Path

SCHEMA = 1


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sidecar(path):
    return Path(f'{path}.criteria.json')


def write_page(path, text, instructions, body, screen=None):
    """Record first ('x': never overwrites, so an existing record stops the page write); a failed page write removes the new record.
    screen: optional presentation conditions (resolution, states) stored beside the hashes; pages without it keep the original record."""
    items = {unescape(i): sha(base64.b64decode(b)) for i, b in re.findall(r'<article data-id="([^"]*)".*?src="data:image/jpeg;base64,([^"]*)"', body, re.S)}
    if len(items) != body.count('<article '):  # silent-missing guard: refuse before writing anything
        raise ValueError('Page articles and crop hashes do not match')
    record = sidecar(path)
    with record.open('x', encoding='utf-8') as stream:
        json.dump(dict(schema_version=SCHEMA, page_sha256=sha(text.encode()), criteria_sha256=sha(instructions.encode()), items=items, **({'screen': screen} if screen else {})), stream, ensure_ascii=False)
    try:
        Path(path).write_text(text, encoding='utf-8')
    except BaseException:
        record.unlink()
        raise


def check(criteria_json, ids, out_jsonl):
    """Before anything is written: schema, every answer id on that page, both output paths free. Returns {id: provenance}."""
    data = json.loads(Path(criteria_json).read_text(encoding='utf-8'))
    if data.get('schema_version') != SCHEMA or not isinstance(data.get('items'), dict):
        raise ValueError('Unsupported criteria record')
    if missing := sorted(set(ids) - set(data['items'])):
        raise ValueError(f'Answer ids not on the recorded page: {missing}')
    if Path(out_jsonl).exists() or sidecar(out_jsonl).exists():
        raise FileExistsError(out_jsonl)
    shown = (data.get('screen') or {}).get('display_px_per_mm', {})
    return {i: dict(criteria_sha256=data['criteria_sha256'], crop_sha256=data['items'][i], **({'display_px_per_mm': shown[i]} if i in shown else {})) for i in ids}


def write_import(out_jsonl, provenance):
    """If the record cannot be written, remove the labels file just written so a retry stays possible."""
    try:
        with sidecar(out_jsonl).open('x', encoding='utf-8') as stream:
            json.dump(provenance, stream, ensure_ascii=False)
    except BaseException as error:
        Path(out_jsonl).unlink()
        if not isinstance(error, FileExistsError):  # an existing record is someone else's: keep it
            sidecar(out_jsonl).unlink(missing_ok=True)  # ours, maybe half-written
        raise

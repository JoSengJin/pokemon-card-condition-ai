"""Loopback-only human annotation UI; no model predictions become labels."""
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.parse import urlsplit

from .data import LABELS, load_manifest, training_readiness
from .regions import validate_annotations
from .label_drafts import draft_status, review_drafts


def atomic_write(path, content):
    fd, name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class ReviewStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.token = secrets.token_urlsafe(32)
        self.reload()

    def reload(self):
        raw = self.path.read_bytes()
        rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        if not rows or len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Empty inventory or duplicate ids")
        for row in rows:
            if not row.get("images"):
                raise ValueError("Use prepare to create an image inventory first")
            for image in row["images"]:
                image["path"] = str((self.path.parent / image["path"]).resolve())
            for side in ("front", "back"):
                if row.get(side) is not None:
                    row[side] = str((self.path.parent / row[side]).resolve())
        self.rows, self.revision = rows, hashlib.sha256(raw).hexdigest()

    def snapshot(self):
        return {"rows": copy.deepcopy(self.rows), "revision": self.revision, "token": self.token,
                "drafts": draft_status(self.rows, self.path.with_suffix('.drafts.json')),
                "readiness": self.check(), "source": str(self.path)}

    def save(self, payload, _draft_reviews=None):
        current = self.path.read_bytes()
        if (payload.get("revision") != self.revision
                or hashlib.sha256(current).hexdigest() != self.revision):
            raise FileExistsError("다른 화면/프로세스에서 수정되었습니다. 새로고침 후 다시 저장하세요.")
        incoming = payload.get("rows")
        if not isinstance(incoming, list) or len(incoming) != len(self.rows):
            raise ValueError("Invalid row count")
        updates = copy.deepcopy(self.rows)
        for old, new, update in zip(self.rows, incoming, updates):
            if not isinstance(new, dict) or new.get("id") != old["id"]:
                raise ValueError("Row identity changed")
            allowed = {image["path"] for image in old["images"]}
            for side in ("front", "back"):
                value = new.get(side)
                if value is not None and (not isinstance(value, str) or value not in allowed):
                    raise ValueError("사진은 현재 항목에 등록된 경로만 선택할 수 있습니다.")
                update[side] = value
            annotations = new.get("side_annotations", old.get("side_annotations", {}))
            update["side_annotations"] = validate_annotations(annotations, update)
            labels = new.get("labels")
            if not isinstance(labels, dict) or set(labels) != set(LABELS):
                raise ValueError("Invalid labels")
            if any(v is not None and (type(v) is not int or v not in (0, 1)) for v in labels.values()):
                raise ValueError("라벨은 0, 1, null만 허용됩니다.")
            update["labels"] = labels
            split = new.get("split")
            if split is not None and split not in ("train", "val", "test"):
                raise ValueError("Invalid split")
            update["split"] = split
            for key in ("group", "reviewed_by", "notes"):
                value = new.get(key, "")
                if not isinstance(value, str) or len(value) > 2000:
                    raise ValueError("Invalid text field")
                update[key] = value.strip()
            for key in ("excluded", "pair_verified"):
                if type(new.get(key, False)) is not bool:
                    raise ValueError("Invalid checkbox")
                update[key] = new.get(key, False)
        backup = self.path.with_name(self.path.name + f".{time.time_ns()}.bak")
        for update in updates:
            if _draft_reviews and update['id'] in _draft_reviews:
                update['ai_draft_reviews'] = _draft_reviews[update['id']]
        backup.write_bytes(current)
        content = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in updates)
        atomic_write(self.path, content)
        self.reload()
        return self.snapshot()

    def review_drafts(self, payload):
        # Existing unsaved edits must be saved first, so approval never discards or trusts an edited draft.
        rows, reviews = review_drafts(self.rows, self.path.with_suffix('.drafts.json'),
            payload.get('ids'), payload.get('decision'), payload.get('reviewed_by'))
        return self.save({**payload, 'rows':rows}, _draft_reviews=reviews)

    def check(self):
        selected = [r for r in self.rows if not r.get("excluded", False)]
        issues = []
        for row in selected:
            if not row.get("reviewed_by", "").strip():
                issues.append(f"{row['id']}: 검토자 미입력")
            if row["labels"].get("gradable") == 1 and not row.get("pair_verified", False):
                issues.append(f"{row['id']}: 동일 실물 앞·뒷면 확인 필요")
        try:
            # Paths in the inventory are absolute; temp location cannot change resolution.
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "labels.jsonl"
                path.write_text("".join(json.dumps(r) + "\n" for r in selected))
                parsed = load_manifest(path)
            plan = training_readiness(parsed)
        except (ValueError, OSError, TypeError) as exc:
            issues.append(str(exc))
            plan = {"ready_for_training": False, "issues": [], "supported": [], "counts": {}}
        return {**plan, "selected": len(selected), "exportable": not issues,
                "issues": issues + plan["issues"],
                "ready_for_training": not issues and plan["ready_for_training"]}

    def export(self, revision):
        if revision != self.revision or hashlib.sha256(self.path.read_bytes()).hexdigest() != self.revision:
            raise FileExistsError("저장 내용이 변경되었습니다. 새로고침하세요.")
        status = self.check()
        if not status["exportable"]:
            raise ValueError("내보내기 전 수정 필요: " + "; ".join(status["issues"]))
        # Partial labelled sets may be exported; readiness distinguishes executable training.
        path = self.path.with_name(f"{self.path.stem}.labels.{time.time_ns()}.jsonl")
        with path.open("x", encoding="utf-8") as stream:
            for row in self.rows:
                if not row.get("excluded", False):
                    clean = {k: row.get(k) for k in ("id", "group", "split", "front", "back", "labels", "reviewed_by", "notes", "pair_verified", "side_annotations")}
                    if row.get('ai_draft_reviews'):
                        clean['ai_draft_reviews'] = row['ai_draft_reviews']
                    stream.write(json.dumps(clean, ensure_ascii=False) + "\n")
        return {"output": str(path), "readiness": status}


class ReviewServer(ThreadingHTTPServer):
    def __init__(self, inventory, port=8766):
        self.store = ReviewStore(inventory)
        self.store_lock = threading.Lock()
        super().__init__(("127.0.0.1", port), ReviewHandler)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class ReviewHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, value, content_type="application/json; charset=utf-8"):
        body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            return self.send(403, {"error": "Invalid host"})
        path = urlsplit(self.path).path
        try:
            if path == "/":
                return self.send(200, Path(__file__).with_name("review.html").read_bytes(), "text/html; charset=utf-8")
            if path == "/api/review":
                with self.server.store_lock:
                    self.server.store.reload()
                    result = self.server.store.snapshot()
                return self.send(200, result)
            if path.startswith("/image/"):
                parts = path.split("/")
                if len(parts) != 4 or not all(p.isdigit() for p in parts[2:]):
                    return self.send(404, {"error": "Unknown image"})
                with self.server.store_lock:
                    item = self.server.store.rows[int(parts[2])]["images"][int(parts[3])]
                image = Path(item["path"])
                mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(image.suffix.lower())
                if mime is None:
                    return self.send(404, {"error": "Unsupported image"})
                return self.send(200, image.read_bytes(), mime)
            return self.send(404, {"error": "Not found"})
        except (OSError, ValueError, IndexError) as exc:
            self.send(400, {"error": str(exc)})

    def do_POST(self):
        store = self.server.store
        if (self.headers.get("Host") != self.server.origin.removeprefix("http://")
                or self.headers.get("Origin", self.server.origin) != self.server.origin
                or self.headers.get("X-Review-Token") != store.token):
            return self.send(403, {"error": "Invalid origin or token"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 2_000_000:
                return self.send(413, {"error": "Invalid request size"})
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict):
                raise ValueError("Expected object")
            with self.server.store_lock:
                if self.path == "/api/save":
                    result = store.save(payload)
                elif self.path == "/api/draft-review":
                    result = store.review_drafts(payload)
                elif self.path == "/api/export":
                    result = store.export(payload.get("revision"))
                else:
                    return self.send(404, {"error": "Not found"})
            self.send(200, result)
        except FileExistsError as exc:
            self.send(409, {"error": str(exc)})
        except (ValueError, OSError, TypeError) as exc:
            self.send(400, {"error": str(exc)})


def serve(inventory, port=8766):
    with ReviewServer(inventory, port) as server:
        print(f"라벨 검토 화면: {server.origin} (종료: Ctrl+C)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

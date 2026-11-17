"""Append-only synthetic raw receipts. No human collection or label export."""
import copy
from datetime import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
from .observation_packet import COLLECTION_STATUS, exact_keys, strict_json_loads, validate_packet
from .observation_response import validate_response

RECEIPT_KEYS = {"schema_version", "kind", "receipt_id", "receipt_sha256", "packet_id", "raw_sha256", "context", "status", "reasons", "response", "missing_entry_ids", "display_verified", "conflicts", "data_origin", "collection_status", "eligible_for_collection", "human_truth"}


def validate_context(context):
    exact_keys(context, {"data_origin", "source_type", "reviewer_id", "session_id", "received_at"}, "synthetic custody")
    if context["data_origin"] != "synthetic_fixture" or context["source_type"] not in ("synthetic_fixture", "ai", "unknown"):
        raise ValueError("actual human collection is not authorized")
    for key in ("reviewer_id", "session_id", "received_at"):
        if not isinstance(context[key], str) or not context[key].strip():
            raise ValueError("invalid custody identity/time")
    if datetime.fromisoformat(context["received_at"].replace("Z", "+00:00")).utcoffset() is None:
        raise ValueError("timezone-aware received_at required")


def receipt_digest(record, identity_only=False):
    body = ({key: record[key] for key in ("packet_id", "raw_sha256", "context")} if identity_only else
            {key: value for key, value in record.items() if key != "receipt_sha256"})
    return hashlib.sha256(json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_records(ledger):
    ledger = Path(ledger)
    if ledger.is_symlink() or (ledger.exists() and not ledger.is_dir()):
        raise ValueError("dedicated receipt directory required")
    records, incomplete = [], []
    if not ledger.exists():
        return records, incomplete
    for folder in sorted(ledger.iterdir()):
        if folder.name == ".lock":
            continue
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"[0-9a-f]{64}", folder.name):
            raise ValueError("unexpected receipt path")
        raw_path, manifest = folder / "raw.bin", folder / "receipt.json"
        if raw_path.is_symlink() or manifest.is_symlink():
            raise ValueError("receipt symlinks are not allowed")
        if not manifest.exists():
            incomplete.append(folder.name)
            continue
        record = strict_json_loads(manifest.read_bytes())
        exact_keys(record, RECEIPT_KEYS, "receipt")
        validate_context(record["context"])
        raw = raw_path.read_bytes()
        if (record["receipt_id"] != folder.name or record["raw_sha256"] != hashlib.sha256(raw).hexdigest() or
                record["receipt_id"] != receipt_digest(record, True) or record["receipt_sha256"] != receipt_digest(record)):
            raise ValueError("receipt content/hash mismatch")
        if (type(record["schema_version"]) is not int or record["schema_version"] != 1 or record["kind"] != "synthetic_observation_receipt" or
                record["data_origin"] != "synthetic_fixture" or record["collection_status"] != COLLECTION_STATUS or
                record["eligible_for_collection"] is not False or record["human_truth"] is not False or
                record["status"] not in ("synthetic_only", "pending_observation", "pending_provenance", "rejected", "conflict")):
            raise ValueError("invalid synthetic receipt guard")
        if record["response"] is None:
            if record["status"] != "rejected" or record["display_verified"] is not False or record["missing_entry_ids"] != [] or record["conflicts"] != []:
                raise ValueError("unparsed receipt must be rejected")
        elif json.dumps(strict_json_loads(raw), sort_keys=True) != json.dumps(record["response"], sort_keys=True):
            raise ValueError("stored response differs from original raw")
        records.append((record, raw))
    return records, incomplete


def load_receipts(packet, ledger):
    validate_packet(packet)
    records, incomplete = read_records(ledger)
    result = []
    for record, raw in records:
        if record["packet_id"] != packet["packet_id"]:
            continue
        if record["response"] is not None:
            checked = validate_response(packet, record["response"])
            if (record["response"]["session_id"] != record["context"]["session_id"] or record["status"] == "rejected" or
                    checked["missing_entry_ids"] != record["missing_entry_ids"] or checked["display_verified"] is not record["display_verified"]):
                raise ValueError("stored receipt observation summary mismatch")
        else:
            try:
                body = strict_json_loads(raw)
                validate_response(packet, body)
                if body["session_id"] != record["context"]["session_id"]:
                    raise ValueError("custody session mismatch")
            except (ValueError, TypeError, OverflowError, RecursionError):
                pass
            else:
                raise ValueError("valid response was stored as rejected")
        result.append(record)
    return {"receipts": result, "incomplete": incomplete}


def persist_receipt(record, raw, ledger):
    folder = Path(ledger) / record["receipt_id"]
    folder.mkdir()  # A partial previous attempt is preserved, never overwritten.
    with (folder / "raw.bin").open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    with (folder / "receipt.pending").open("xb") as stream:
        stream.write(json.dumps(record, ensure_ascii=True, sort_keys=True, indent=2).encode())
        stream.flush()
        os.fsync(stream.fileno())
    # Only the atomic, create-only manifest link marks a complete receipt.
    os.link(folder / "receipt.pending", folder / "receipt.json")


def make_receipt(packet, raw, context, response, summary, status, reasons, conflicts):
    record = dict(schema_version=1, kind="synthetic_observation_receipt", packet_id=packet["packet_id"],
                  raw_sha256=hashlib.sha256(raw).hexdigest(), context=copy.deepcopy(context), status=status,
                  reasons=list(reasons), response=response, missing_entry_ids=summary["missing_entry_ids"],
                  display_verified=summary["display_verified"], conflicts=sorted(conflicts), data_origin="synthetic_fixture",
                  collection_status=COLLECTION_STATUS, eligible_for_collection=False, human_truth=False)
    record["receipt_id"] = receipt_digest(record, True)
    record["receipt_sha256"] = receipt_digest(record)
    return record


def capture_receipt(packet, raw_bytes, custody_context, ledger):
    validate_packet(packet)
    validate_context(custody_context)
    if type(raw_bytes) is not bytes:
        raise ValueError("raw response must be immutable bytes")
    ledger = Path(ledger)
    if ledger.is_symlink():
        raise ValueError("receipt directory symlink is not allowed")
    ledger.mkdir(parents=True, exist_ok=True)
    with (ledger / ".lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records, incomplete = read_records(ledger)
        identity = receipt_digest(dict(packet_id=packet["packet_id"], raw_sha256=hashlib.sha256(raw_bytes).hexdigest(), context=custody_context), True)
        for previous, old_raw in records:
            if previous["packet_id"] != packet["packet_id"]:
                continue
            if previous["response"] is not None:
                checked = validate_response(packet, previous["response"])
                if (previous["response"]["session_id"] != previous["context"]["session_id"] or previous["status"] == "rejected" or
                        checked["missing_entry_ids"] != previous["missing_entry_ids"] or checked["display_verified"] is not previous["display_verified"]):
                    raise ValueError("stored receipt observation summary mismatch")
            else:
                try:
                    body = strict_json_loads(old_raw)
                    validate_response(packet, body)
                    if body["session_id"] != previous["context"]["session_id"]:
                        raise ValueError("custody session mismatch")
                except (ValueError, TypeError, OverflowError, RecursionError):
                    pass
                else:
                    raise ValueError("valid response was stored as rejected")
            if previous["receipt_id"] == identity:
                if old_raw != raw_bytes or previous["context"] != custody_context:
                    raise ValueError("receipt identity collision")
                return previous
        reasons, conflicts = ["collection_not_authorized"], set()
        summary = dict(missing_entry_ids=[], display_verified=False)
        try:
            response = strict_json_loads(raw_bytes)
            summary = validate_response(packet, response)
            if response["session_id"] != custody_context["session_id"]:
                raise ValueError("custody session mismatch")
        except (ValueError, TypeError, OverflowError, RecursionError) as error:
            response, status = None, "rejected"
            summary = dict(missing_entry_ids=[], display_verified=False)
            reasons.insert(0, str(error))
        else:
            status = "synthetic_only"
            if summary["missing_entry_ids"] or not summary["display_verified"]:
                status = "pending_observation"
                reasons.append("missing_or_inconsistent_observations")
            if custody_context["source_type"] != "synthetic_fixture":
                status = "pending_provenance"
                reasons.append("not_a_human_truth_source")
            if custody_context["source_type"] == "synthetic_fixture":
                states = {entry["entry_id"]: entry["state"] for entry in response["entries"] if entry["state"] != "unreviewed"}
                for previous, old_raw in records:
                    if previous["packet_id"] != packet["packet_id"] or previous["response"] is None or previous["context"]["source_type"] != "synthetic_fixture":
                        continue
                    for entry in previous["response"]["entries"]:
                        if entry["entry_id"] in states and entry["state"] != "unreviewed" and states[entry["entry_id"]] != entry["state"]:
                            conflicts.add(entry["entry_id"])
                if conflicts:
                    status = "conflict"
                    reasons.append("conflicting_original_observations_preserved")
        record = make_receipt(packet, raw_bytes, custody_context, response, summary, status, reasons, conflicts)
        persist_receipt(record, raw_bytes, ledger)
        return record

"""Append-only synthetic candidate receipts; no actual human ingestion."""
import copy
import fcntl
import hashlib
import json
from pathlib import Path
import re
from .observation_packet import COLLECTION_STATUS,exact_keys,strict_json_loads,validate_packet
from .observation_response import validate_response
from .observation_source import validate_source_context
from .observation_collection_contract import validate_collection_contract
from .observation_collection_response import validate_collection_response
from .observation_receipt import persist_receipt

RECORD_KEYS={"schema_version","kind","receipt_id","receipt_sha256","packet_id","contract_id","raw_sha256","context","response","summary","status","reasons","data_origin","collection_status","human_truth","eligible_for_collection"}


def collection_digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def read_collection_records(ledger):
    root=Path(ledger);records=[];incomplete=[]
    if root.is_symlink() or root.exists() and not root.is_dir():raise ValueError("dedicated collection ledger required")
    if not root.exists():return records,incomplete
    for folder in sorted(root.iterdir()):
        if folder.name==".lock":continue
        if folder.is_symlink() or not folder.is_dir() or not re.fullmatch(r"[0-9a-f]{64}",folder.name):raise ValueError("unexpected collection path")
        manifest=folder/"receipt.json";raw_path=folder/"raw.bin"
        if manifest.is_symlink() or raw_path.is_symlink():raise ValueError("collection symlinks forbidden")
        if not manifest.exists():incomplete.append(folder.name);continue
        record=strict_json_loads(manifest.read_bytes());exact_keys(record,RECORD_KEYS,"collection receipt");raw=raw_path.read_bytes()
        identity={k:record[k] for k in ("packet_id","contract_id","raw_sha256","context")}
        if (record["receipt_id"]!=folder.name or record["receipt_id"]!=collection_digest(identity) or
            record["receipt_sha256"]!=collection_digest({k:v for k,v in record.items() if k!="receipt_sha256"}) or record["raw_sha256"]!=hashlib.sha256(raw).hexdigest()):raise ValueError("collection receipt hash mismatch")
        if (type(record["schema_version"]) is not int or record["schema_version"]!=2 or record["kind"]!="synthetic_collection_receipt" or
            record["data_origin"]!="synthetic_fixture" or record["collection_status"]!=COLLECTION_STATUS or record["human_truth"] is not False or record["eligible_for_collection"] is not False):raise ValueError("invalid collection receipt guard")
        if not isinstance(record["context"],dict) or record["context"].get("source_type")!="synthetic_fixture":raise ValueError("actual human collection is not authorized")
        records.append((record,raw))
    return records,incomplete


def collection_classification(summary,claim,error=None):
    reasons=["collection_not_authorized"]
    if error is not None:return "rejected",[error]+reasons
    status="synthetic_only"
    if summary["missing_entry_ids"] or not summary["display_verified"]:status="pending_observation";reasons.append("missing_or_inconsistent_observations")
    if not summary["assignment_matched"] or claim!="human":status="pending_provenance";reasons.append("synthetic_actor_not_matched")
    return status,reasons


def load_collection_receipts(packet,contract,assignment,ledger):
    validate_packet(packet);validate_collection_contract(contract)
    records,incomplete=read_collection_records(ledger);result=[]
    for record,raw in records:
        if record["packet_id"]!=packet["packet_id"] or record["contract_id"]!=contract["contract_id"]:continue
        summary=dict(missing_entry_ids=[],display_verified=False,assignment_matched=False);error=None;body=None
        try:
            body=strict_json_loads(raw)
            if not isinstance(body,dict):raise ValueError("candidate response must be an object")
            base=validate_response(packet,body.get("base_response"));side=validate_collection_response(packet,contract,body)
            matched=validate_source_context(record["context"],assignment)
            if record["context"]["contract_id"]!=contract["contract_id"] or record["context"]["session_id"]!=body["base_response"]["session_id"]:raise ValueError("custody contract/session mismatch")
            if matched and (assignment["assignment_id"]!=contract["assignment_ref"] or assignment["observation_mode"]!=packet["observation_mode"]):raise ValueError("assignment contract/mode mismatch")
            summary=dict(missing_entry_ids=base["missing_entry_ids"],display_verified=base["display_verified"] and side,assignment_matched=matched)
        except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:body=None;error=str(exc)
        status,reasons=collection_classification(summary,body["claimed_actor"] if body is not None else None,error)
        expected=dict(response=body,summary=summary,status=status,reasons=reasons)
        if collection_digest({k:record[k] for k in expected})!=collection_digest(expected):raise ValueError("stored collection classification mismatch")
        result.append(record)
    return dict(receipts=result,incomplete=incomplete)


def capture_collection_receipt(packet,contract,raw_bytes,custody_context,assignment,ledger):
    validate_packet(packet);validate_collection_contract(contract)
    if contract["packet_id"]!=packet["packet_id"] or contract["display_profile"]!=packet["profile"]:raise ValueError("contract packet/profile mismatch")
    if type(raw_bytes) is not bytes:raise ValueError("immutable raw bytes required")
    if not isinstance(custody_context,dict) or custody_context.get("source_type")!="synthetic_fixture":raise ValueError("actual human collection is not authorized")
    root=Path(ledger)
    if root.is_symlink() or (root/".lock").is_symlink():raise ValueError("collection ledger symlink forbidden")
    root.mkdir(parents=True,exist_ok=True)
    with (root/".lock").open("a+b") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        records,incomplete=read_collection_records(root)
        # Validate stored semantics inline, without a wrapper around the v1 validator.
        inputs=[(old_raw,record["context"],record) for record,old_raw in records if record["packet_id"]==packet["packet_id"] and record["contract_id"]==contract["contract_id"]]
        inputs.append((raw_bytes,custody_context,None));new_record=None
        for raw,context,previous in inputs:
            summary=dict(missing_entry_ids=[],display_verified=False,assignment_matched=False);error=None;body=None
            try:
                body=strict_json_loads(raw)
                if not isinstance(body,dict):raise ValueError("candidate response must be an object")
                base=validate_response(packet,body.get("base_response"));side=validate_collection_response(packet,contract,body)
                matched=validate_source_context(context,assignment)
                if context["contract_id"]!=contract["contract_id"] or context["session_id"]!=body["base_response"]["session_id"]:raise ValueError("custody contract/session mismatch")
                if matched and (assignment["assignment_id"]!=contract["assignment_ref"] or assignment["observation_mode"]!=packet["observation_mode"]):raise ValueError("assignment contract/mode mismatch")
                summary=dict(missing_entry_ids=base["missing_entry_ids"],display_verified=base["display_verified"] and side,assignment_matched=matched)
            except (ValueError,TypeError,KeyError,OverflowError,RecursionError) as exc:body=None;error=str(exc)
            status,reasons=collection_classification(summary,body["claimed_actor"] if body is not None else None,error)
            expected=dict(response=body,summary=summary,status=status,reasons=reasons)
            if previous is not None:
                if collection_digest({k:previous[k] for k in expected})!=collection_digest(expected):raise ValueError("stored collection classification mismatch")
                continue
            identity=dict(packet_id=packet["packet_id"],contract_id=contract["contract_id"],raw_sha256=hashlib.sha256(raw).hexdigest(),context=copy.deepcopy(context))
            new_record=dict(schema_version=2,kind="synthetic_collection_receipt",**identity,**expected,data_origin="synthetic_fixture",collection_status=COLLECTION_STATUS,human_truth=False,eligible_for_collection=False)
            new_record["receipt_id"]=collection_digest(identity);new_record["receipt_sha256"]=collection_digest(new_record)
        for previous,old_raw in records:
            if previous["receipt_id"]==new_record["receipt_id"]:
                if old_raw!=raw_bytes or previous["context"]!=custody_context:raise ValueError("collection identity collision")
                return previous
        persist_receipt(new_record,raw_bytes,root)
        return new_record

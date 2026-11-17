"""Create-only synthetic custody seals and replayed policy transitions."""
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import re
from .observation_packet import COLLECTION_STATUS,exact_keys,strict_json_loads
from .observation_collection_contract import validate_collection_contract
from .observation_collection_receipt import collection_digest,read_collection_records
from .observation_access import authorize

SEAL_KEYS={"schema_version","kind","seal_id","seal_sha256","contract_id","spec_sha256","access_policy_ref","seal_policy_ref","receipt_refs","truth_status","data_origin","collection_status","human_truth","eligible_for_collection"}
EVENT_KEYS={"seq","previous_sha256","seal_id","contract_id","action","principal_id","role","policy_id","freeze_ref","at","event_sha256"}


def validate_seal_manifest(seal):
    exact_keys(seal,SEAL_KEYS,"synthetic seal")
    if (type(seal["schema_version"]) is not int or seal["schema_version"]!=2 or seal["kind"]!="synthetic_collection_seal" or
        seal["truth_status"]!="unresolved_synthetic" or seal["data_origin"]!="synthetic_fixture" or seal["collection_status"]!=COLLECTION_STATUS or seal["human_truth"] is not False or seal["eligible_for_collection"] is not False):raise ValueError("invalid synthetic seal guard")
    for key in ("seal_id","seal_sha256","contract_id","spec_sha256"):
        if not isinstance(seal[key],str) or not re.fullmatch(r"[0-9a-f]{64}",seal[key]):raise ValueError("invalid seal digest")
    if (seal["seal_id"]!=collection_digest({k:v for k,v in seal.items() if k not in ("seal_id","seal_sha256")}) or
        seal["seal_sha256"]!=collection_digest({k:v for k,v in seal.items() if k!="seal_sha256"})):raise ValueError("seal digest mismatch")
    if not isinstance(seal["receipt_refs"],list) or not seal["receipt_refs"]:raise ValueError("empty seal")
    seen=set()
    for ref in seal["receipt_refs"]:
        exact_keys(ref,{"receipt_id","receipt_sha256","raw_sha256"},"sealed receipt reference")
        if any(not isinstance(value,str) or not re.fullmatch(r"[0-9a-f]{64}",value) for value in ref.values()) or ref["receipt_id"] in seen:raise ValueError("invalid sealed receipt reference")
        seen.add(ref["receipt_id"])


def seal_receipts(contract,receipt_refs,ledger,output):
    validate_collection_contract(contract)
    root=Path(output);source=Path(ledger)
    if root.is_symlink() or source.is_symlink() or root.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(root.resolve()) or (root/".lock").is_symlink() or (source/".lock").is_symlink():raise ValueError("dedicated seal root required")
    # Lock ordering is receipt ledger -> seal ledger; capture cannot change the cohort before publication.
    with (source/".lock").open("a+b") as intake_lock:
        fcntl.flock(intake_lock,fcntl.LOCK_EX)
        records,incomplete=read_collection_records(ledger)
        selected={r["receipt_id"]:r for r,raw in records if r["contract_id"]==contract["contract_id"]}
        if incomplete or not isinstance(receipt_refs,list) or not selected or any(not isinstance(x,str) for x in receipt_refs) or len(set(receipt_refs))!=len(receipt_refs) or set(receipt_refs)!=set(selected):raise ValueError("complete cohort required for seal")
        seal=dict(schema_version=2,kind="synthetic_collection_seal",contract_id=contract["contract_id"],spec_sha256=contract["spec_sha256"],access_policy_ref=contract["access_policy_ref"],seal_policy_ref=contract["seal_policy_ref"],
                  receipt_refs=[{k:selected[key][k] for k in ("receipt_id","receipt_sha256","raw_sha256")} for key in sorted(selected)],truth_status="unresolved_synthetic",data_origin="synthetic_fixture",collection_status=COLLECTION_STATUS,human_truth=False,eligible_for_collection=False)
        seal["seal_id"]=collection_digest(seal);seal["seal_sha256"]=collection_digest(seal)
        root.mkdir(parents=True,exist_ok=True)
        with (root/".lock").open("a+b") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            folder=root/seal["seal_id"];folder.mkdir();(folder/"events").mkdir()
            with (folder/"seal.pending").open("xb") as stream:
                stream.write(json.dumps(seal,ensure_ascii=True,sort_keys=True,indent=2).encode());stream.flush();os.fsync(stream.fileno())
            os.link(folder/"seal.pending",folder/"seal.json")
    return seal


def load_seal(contract,ledger,output,seal_id):
    validate_collection_contract(contract)
    root=Path(output)
    if not isinstance(seal_id,str) or not re.fullmatch(r"[0-9a-f]{64}",seal_id) or root.is_symlink() or (root/seal_id).is_symlink() or (root/seal_id/"seal.json").is_symlink():raise ValueError("invalid seal path")
    manifest=root/seal_id/"seal.json"
    if not manifest.is_file():raise ValueError("incomplete seal")
    seal=strict_json_loads(manifest.read_bytes());validate_seal_manifest(seal)
    if seal["seal_id"]!=seal_id or seal["contract_id"]!=contract["contract_id"] or seal["spec_sha256"]!=contract["spec_sha256"] or seal["access_policy_ref"]!=contract["access_policy_ref"] or seal["seal_policy_ref"]!=contract["seal_policy_ref"]:raise ValueError("seal contract mismatch")
    records,incomplete=read_collection_records(ledger);by_id={r["receipt_id"]:r for r,raw in records}
    for ref in seal["receipt_refs"]:
        record=by_id.get(ref["receipt_id"])
        if record is None or record["contract_id"]!=contract["contract_id"] or any(record[k]!=ref[k] for k in ref):raise ValueError("sealed raw/receipt changed")
    return seal


def seal_state(seal,output,policy=None):
    validate_seal_manifest(seal)
    root=Path(output);folder=root/seal["seal_id"];events=folder/"events"
    if root.is_symlink() or folder.is_symlink() or (folder/"seal.json").is_symlink() or events.is_symlink():raise ValueError("seal symlink forbidden")
    if collection_digest(strict_json_loads((folder/"seal.json").read_bytes()))!=collection_digest(seal):raise ValueError("seal changed")
    state=dict(contract_id=seal["contract_id"],sealed=True,released=False,quarantined=False,freeze_ref=None)
    previous=seal["seal_sha256"];last_at=None
    for seq,path in enumerate(sorted(events.iterdir())):
        if path.is_symlink() or not path.is_file() or path.name!=f"{seq:08d}.json":raise ValueError("invalid seal event path")
        event=strict_json_loads(path.read_bytes());exact_keys(event,EVENT_KEYS,"seal event")
        if (type(event["seq"]) is not int or event["seq"]!=seq or event["previous_sha256"]!=previous or event["seal_id"]!=seal["seal_id"] or event["contract_id"]!=seal["contract_id"] or
            event["event_sha256"]!=collection_digest({k:v for k,v in event.items() if k!="event_sha256"})):raise ValueError("seal event chain mismatch")
        if policy is None or event["policy_id"]!=seal["access_policy_ref"] or policy["policy_id"]!=event["policy_id"]:raise ValueError("trusted synthetic policy required")
        if not isinstance(event["at"],str):raise ValueError("invalid seal time")
        at=datetime.fromisoformat(event["at"].replace("Z","+00:00"))
        if at.utcoffset() is None or last_at is not None and at<last_at:raise ValueError("invalid seal event clock")
        proposed=dict(state)
        if event["action"]=="release":proposed["freeze_ref"]=event["freeze_ref"]
        elif event["action"]!="quarantine" or event["freeze_ref"]!=state["freeze_ref"]:raise ValueError("invalid seal action")
        actor=dict(principal_id=event["principal_id"],role=event["role"],evidence_origin="synthetic_fixture")
        if not authorize(actor,event["action"],proposed,policy)["allowed"]:raise ValueError("unauthorized seal history")
        state=proposed
        if event["action"]=="release":state["released"]=True
        else:state["quarantined"]=True
        previous=event["event_sha256"];last_at=at
    return state


def transition_seal(seal,output,action,actor,policy,freeze_ref=None):
    root=Path(output)
    if root.is_symlink() or (root/".lock").is_symlink():raise ValueError("seal lock symlink forbidden")
    with (root/".lock").open("a+b") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        state=seal_state(seal,root,policy)
        if policy["policy_id"]!=seal["access_policy_ref"]:raise ValueError("seal policy mismatch")
        proposed=dict(state)
        if action=="release":proposed["freeze_ref"]=freeze_ref
        if action not in ("release","quarantine") or not authorize(actor,action,proposed,policy)["allowed"]:raise ValueError("seal transition denied")
        events=root/seal["seal_id"]/"events";paths=sorted(events.iterdir());seq=len(paths)
        previous=seal["seal_sha256"] if not paths else strict_json_loads(paths[-1].read_bytes())["event_sha256"]
        event=dict(seq=seq,previous_sha256=previous,seal_id=seal["seal_id"],contract_id=seal["contract_id"],action=action,principal_id=actor["principal_id"],role=actor["role"],policy_id=policy["policy_id"],freeze_ref=proposed["freeze_ref"],at=datetime.now(timezone.utc).isoformat())
        event["event_sha256"]=collection_digest(event)
        with (events/f"{seq:08d}.json").open("xb") as stream:
            stream.write(json.dumps(event,ensure_ascii=True,sort_keys=True,indent=2).encode());stream.flush();os.fsync(stream.fileno())
        return seal_state(seal,root,policy)

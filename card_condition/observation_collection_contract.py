"""Strict synthetic candidate contract. No real collection authorization."""
import hashlib
import json
import math
import re
from .observation_packet import COLLECTION_STATUS, exact_keys, validate_profile

CONTRACT_KEYS={"schema_version","kind","contract_id","spec_sha256","packet_id","data_origin","collection_status",
               "human_truth","eligible_for_collection","display_profile","zoom_policy","assignment_ref","seal_policy_ref","access_policy_ref"}
REFS=("assignment_ref","seal_policy_ref","access_policy_ref")


def contract_digest(contract):
    body={k:v for k,v in contract.items() if k!="contract_id"}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()).hexdigest()


def validate_collection_contract(contract):
    exact_keys(contract,CONTRACT_KEYS,"collection contract")
    if (type(contract["schema_version"]) is not int or contract["schema_version"]!=2 or
        contract["kind"]!="synthetic_collection_contract" or contract["data_origin"]!="synthetic_fixture" or
        contract["collection_status"]!=COLLECTION_STATUS or contract["human_truth"] is not False or contract["eligible_for_collection"] is not False):
        raise ValueError("synthetic collection guard")
    for key in ("contract_id","spec_sha256","packet_id"):
        if not isinstance(contract[key],str) or not re.fullmatch(r"[0-9a-f]{64}",contract[key]):raise ValueError("invalid contract hash")
    validate_profile(contract["display_profile"])
    zoom=contract["zoom_policy"]
    exact_keys(zoom,{"scale_min","scale_max","pan_x_limit","pan_y_limit"},"zoom policy")
    for key,value in zoom.items():
        if value is not None and (type(value) not in (int,float) or not math.isfinite(value) or
                                  (value<=0 if key.startswith("scale") else value<0)):
            raise ValueError("invalid zoom policy")
    if ((zoom["scale_min"] is None)!=(zoom["scale_max"] is None) or
        (zoom["scale_min"] is not None and not zoom["scale_min"]<=1<=zoom["scale_max"])):raise ValueError("invalid scale interval")
    for key in REFS:
        if contract[key] is not None and (not isinstance(contract[key],str) or not contract[key].strip()):raise ValueError("invalid contract reference")
    if contract["contract_id"]!=contract_digest(contract):raise ValueError("contract hash mismatch")


def readiness(contract):
    validate_collection_contract(contract)
    missing=["display_profile."+key for key in ("viewport_css","image_css","device_pixel_ratio") if contract["display_profile"][key] is None]
    if contract["display_profile"]["observation_mode"]=="H":
        missing.extend("zoom_policy."+key for key,value in contract["zoom_policy"].items() if value is None)
    missing.extend(key for key in REFS if contract[key] is None)
    return dict(synthetic_ready=not missing,collection_ready=False,human_truth=False,eligible_for_collection=False,
                missing=missing+["actual_collection_not_authorized"])

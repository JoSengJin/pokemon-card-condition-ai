"""Synthetic policy projections, not operating-system access enforcement."""
from .observation_packet import exact_keys


def authorize(actor,action,state,policy):
    exact_keys(policy,{"policy_id","contract_id","evidence_origin","grants"},"synthetic access policy")
    exact_keys(state,{"contract_id","sealed","released","quarantined","freeze_ref"},"synthetic access state")
    if policy["evidence_origin"]!="synthetic_fixture" or not isinstance(policy["policy_id"],str) or not policy["policy_id"].strip() or not isinstance(policy["grants"],dict):raise ValueError("invalid synthetic policy")
    if any(type(state[k]) is not bool for k in ("sealed","released","quarantined")) or state["freeze_ref"] is not None and (not isinstance(state["freeze_ref"],str) or not state["freeze_ref"].strip()):raise ValueError("invalid access state")
    result=dict(allowed=False,reason="untrusted_or_out_of_scope_actor",actual_access_verified=False)
    if not isinstance(actor,dict) or set(actor)!={"principal_id","role","evidence_origin"}:return result
    if actor["evidence_origin"]!="synthetic_fixture" or not isinstance(actor["principal_id"],str) or actor["role"] not in ("custodian","developer","evaluator","rater"):return result
    if policy["contract_id"]!=state["contract_id"] or policy["grants"].get(actor["principal_id"])!=actor["role"]:return result
    role=actor["role"]
    allowed=(action=="view_aggregate" and role in ("custodian","developer","evaluator") or
             action=="read_raw" and role=="custodian" or
             action=="read_packet" and role=="rater" and not state["sealed"] and not state["quarantined"] or
             action=="release" and role=="custodian" and state["sealed"] and not state["released"] and not state["quarantined"] and state["freeze_ref"] is not None or
             action=="quarantine" and role=="custodian" and state["sealed"] and not state["quarantined"] or
             action=="read_evaluation" and role=="evaluator" and state["sealed"] and state["released"] and not state["quarantined"] and state["freeze_ref"] is not None)
    return dict(allowed=bool(allowed),reason="synthetic_policy_only" if allowed else "action_or_state_denied",actual_access_verified=False)


def aggregate_projection(actor,state,policy,receipts):
    if not authorize(actor,"view_aggregate",state,policy)["allowed"]:raise ValueError("aggregate access denied")
    counts={}
    for record in receipts:counts[record["status"]]=counts.get(record["status"],0)+1
    return dict(receipt_count=len(receipts),status_counts=counts,quarantined=state["quarantined"])

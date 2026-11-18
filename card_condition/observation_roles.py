"""Synthetic R2 role/channel contract and sentinel records. Records intent and evidence; enforces nothing."""
from .observation_evidence import check_header, COMMON_KEYS
from .observation_packet import exact_keys

ROLES = ("human_rater", "custodian", "developer", "evaluator", "automation", "enforcer")
CHANNELS = ("files", "tools", "conversation", "memory", "reply")
PAYLOADS = ("approved_aggregate", "packet", "frozen_plan", "final_eval_item", "lineage_map", "raw_response", "memo")
DEVELOPER_SAFE = {"approved_aggregate"}
ENFORCEMENT_KINDS = (None, "same_privilege_subagent", "mock_denial", "distinct_os_identity", "external_enforcer")
ACTUAL_KINDS = ("distinct_os_identity", "external_enforcer")
ROLE_KEYS = {"principals", "channels", "receives", "sends_to_developer", "creates_human_truth"}
SENTINEL_SCENARIOS = ("allowed_access", "forbidden_direct_file", "tool_bypass",
                      "conversation_leak", "memory_leak", "reply_leak")
PHASES = ("before_release", "after_release", "after_quarantine")
SENTINEL_KEYS = COMMON_KEYS | {"scenario", "phase", "mode", "access_path", "expected", "actual", "evidence_ref",
                               "same_os_user_as_protected", "marker"}


def validate_role_contract(contract):
    exact_keys(contract, {"schema_version", "kind", "data_origin", "actual_access_verified", "enforcement", "roles"}, "role contract")
    if (contract["schema_version"] != 1 or contract["kind"] != "synthetic_role_contract" or
            contract["data_origin"] != "synthetic_fixture" or contract["actual_access_verified"] is not False):
        raise ValueError("synthetic role contract guard")
    exact_keys(contract["enforcement"], {"kind", "mechanism"}, "enforcement")
    mechanism = contract["enforcement"]["mechanism"]
    if contract["enforcement"]["kind"] not in ENFORCEMENT_KINDS or (mechanism is not None and not (isinstance(mechanism, str) and mechanism.strip())):
        raise ValueError("invalid enforcement declaration")
    exact_keys(contract["roles"], set(ROLES), "roles")
    for role in contract["roles"].values():
        exact_keys(role, ROLE_KEYS, "role")
        exact_keys(role["channels"], set(CHANNELS), "channels")
        who = role["principals"]
        if who is not None and (not isinstance(who, list) or len(set(who)) != len(who) or
                                not all(isinstance(p, str) and p.strip() for p in who)):
            raise ValueError("invalid principals")
        if any(v not in ("allow", "deny", None) for v in role["channels"].values()) or role["creates_human_truth"] is not False:
            raise ValueError("invalid channel or human truth claim")
        for key in ("receives", "sends_to_developer"):
            if role[key] is not None and (not isinstance(role[key], list) or any(p not in PAYLOADS for p in role[key])):
                raise ValueError("unknown payload kind")
        if role["sends_to_developer"] is not None and not set(role["sends_to_developer"]) <= DEVELOPER_SAFE:
            raise ValueError("only approved aggregates may reach development")
    received = contract["roles"]["developer"]["receives"]
    if received is not None and not set(received) <= DEVELOPER_SAFE:
        raise ValueError("developer may receive only approved aggregates")


def overlap_findings(contract):
    """One principal in development and protected roles: an account split does not remove learned knowledge."""
    validate_role_contract(contract)
    held = {}
    for name, role in contract["roles"].items():
        for principal in role["principals"] or []:
            held.setdefault(principal, []).append(name)
    return [dict(principal=p, roles=r, independent=False, note="knowledge_not_removed_by_account_split")
            for p, r in held.items() if "developer" in r and set(r) & {"custodian", "evaluator", "human_rater"}]


def validate_sentinel_record(record):
    check_header(record, SENTINEL_KEYS)
    if record["scenario"] not in SENTINEL_SCENARIOS or record["phase"] not in PHASES:
        raise ValueError("unknown sentinel scenario or phase")
    expected_type = {"mock": "synthetic_mock", "actual_identity": "real_permission_env"}.get(record["mode"])
    if expected_type is None or record["evidence_type"] != expected_type:
        raise ValueError("mode and evidence type disagree")
    if not (isinstance(record["marker"], str) and record["marker"].startswith("SYNTH-SENTINEL-")):
        raise ValueError("only synthetic sentinel markers are accepted")
    if record["expected"] not in ("allow", "deny") or record["actual"] not in ("allow", "deny", None):
        raise ValueError("invalid access outcome")
    if record["actual"] is None and record["null_reason"] is None:
        raise ValueError("unobserved outcome requires a reason")
    if record["same_os_user_as_protected"] not in (True, False, None):
        raise ValueError("invalid same-user declaration")


def sentinel_verdict(record):
    validate_sentinel_record(record)
    expected, actual = record["expected"], record["actual"]
    if actual is None:
        return "unverified"
    if expected == "deny" and actual == "allow":
        return "fail"
    if record["mode"] == "mock":
        return "mock_pass" if expected == actual else "mock_fail"
    if record["run_identity"] is None or record["same_os_user_as_protected"] is not False:
        return "unverified"
    return "pass" if expected == actual else "fail"


def sentinel_status(records, contract):
    """Aggregate sentinel evidence; cannot return verified, only blocked/failed/ready for human review."""
    validate_role_contract(contract)
    verdicts = {}
    for record in records:
        verdicts.setdefault((record["scenario"], record["phase"]), []).append(sentinel_verdict(record))
    flat = [v for vs in verdicts.values() for v in vs]
    missing = [s + "@" + p for s in SENTINEL_SCENARIOS for p in PHASES if "pass" not in verdicts.get((s, p), [])]
    kind = contract["enforcement"]["kind"]
    reasons = [] if kind in ACTUAL_KINDS and contract["enforcement"]["mechanism"] else ["enforcement_not_actual:" + str(kind)]
    status = "failed" if any(v in ("fail", "mock_fail") for v in flat) else (
        "blocked_unverified" if missing or reasons else "evidence_ready_for_review")
    return dict(status=status, actual_access_verified=False, missing=missing, reasons=reasons,
                overlaps=overlap_findings(contract), independent_evaluation_claim=False,
                verdict_counts={v: flat.count(v) for v in sorted(set(flat))}, collection_ready=False)

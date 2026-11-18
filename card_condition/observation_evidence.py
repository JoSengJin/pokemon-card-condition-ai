"""Synthetic R1 evidence records. Never promotes mock/desktop evidence to a real-phone result."""
import hashlib
from .observation_collection_contract import readiness
from .observation_packet import exact_keys

EVIDENCE_TYPES = ("synthetic_mock", "desktop_browser", "real_phone", "real_permission_env")
R1_SCENARIOS = ("default_display", "address_bar", "rotation", "keyboard", "touch",
                "h_zoom_app_log", "h_zoom_external", "a_separation", "export_receive")
HEADER_KEYS = {"task_id", "run_identity", "role", "assignment_id", "contract_sha256", "profile_version"}
COMMON_KEYS = HEADER_KEYS | {"evidence_type", "data_origin", "observed_at", "null_reason"}
R1_KEYS = COMMON_KEYS | {"scenario", "observed", "source"}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def check_header(record, keys):
    """Shared strict header; undecided identity/assignment values stay null, never defaulted."""
    exact_keys(record, keys, "evidence record")
    if record["data_origin"] != "synthetic_fixture":
        raise ValueError("only synthetic fixture evidence is accepted")
    if record["evidence_type"] not in EVIDENCE_TYPES:
        raise ValueError("unknown evidence type")
    for key in HEADER_KEYS | {"observed_at", "null_reason"}:
        if record[key] is not None and not _text(record[key]):
            raise ValueError("invalid evidence field: " + key)


def validate_r1_record(record):
    check_header(record, R1_KEYS)
    if record["scenario"] not in R1_SCENARIOS:
        raise ValueError("unknown R1 scenario")
    observed = record["observed"]
    if observed is None:
        if record["null_reason"] is None:
            raise ValueError("null observation requires a reason")
        return
    if (not isinstance(observed, dict) or not observed or record["null_reason"] is not None or
            not _text(record["observed_at"]) or not _text(record["source"])):
        raise ValueError("observation needs values, time and source and no null reason")
    if observed.get("source_type") == "human":
        raise ValueError("real human input cannot be recorded as synthetic evidence")
    if record["scenario"] == "h_zoom_external" and record["source"] == "app_zoom_log":
        raise ValueError("app zoom log is not an external zoom observation")


def raw_matches(raw, sha256):
    """Exact bytes comparison: str, stripped or re-serialized text never matches."""
    return type(raw) is bytes and isinstance(sha256, str) and hashlib.sha256(raw).hexdigest() == sha256


def r1_status(records, contract):
    """Report R1 evidence gaps. Cannot return a completed R1; the best state awaits human review."""
    by_scenario = {name: "unverified" for name in R1_SCENARIOS}
    for record in records:
        validate_r1_record(record)
        name, current = record["scenario"], by_scenario[record["scenario"]]
        if record["observed"] is None:
            by_scenario[name] = "observed_null" if current == "unverified" else current
        elif record["evidence_type"] == "real_phone":
            by_scenario[name] = "real_phone"
        elif current != "real_phone":
            by_scenario[name] = "desktop_or_mock_only"
    gaps = ["scenario." + n + ":" + s for n, s in by_scenario.items() if s != "real_phone"]
    ready = readiness(contract)
    gaps += [m for m in ready["missing"] if m.startswith(("display_profile.", "zoom_policy."))]
    return dict(r1_complete=False, status="blocked_unverified" if gaps else "evidence_ready_for_review",
                scenarios=by_scenario, gaps=gaps, collection_ready=False, human_truth=False,
                eligible_for_collection=False)

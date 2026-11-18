"""Memory-only fixtures for R1/R2 readiness tests; invented identifiers, no real data."""
from card_condition.observation_evidence import R1_SCENARIOS
from card_condition.observation_roles import CHANNELS, PHASES, ROLES, SENTINEL_SCENARIOS


def record(scenario, evidence_type="desktop_browser", observed=None, **over):
    base = dict(task_id=None, run_identity=None, role=None, assignment_id=None, contract_sha256=None, profile_version=None,
                evidence_type=evidence_type, data_origin="synthetic_fixture", observed_at=None, null_reason="not observed",
                scenario=scenario, observed=observed, source=None)
    if observed is not None:
        base.update(observed_at="2026-11-18T00:00:00Z", null_reason=None, source="fixture-source")
    base.update(over)
    return base


def full(evidence_type):
    return [record(s, evidence_type, {"value": 1}) for s in R1_SCENARIOS]


def role_contract(kind=None, mechanism=None):
    roles = {r: dict(principals=None, channels={c: None for c in CHANNELS}, receives=None, sends_to_developer=None,
                     creates_human_truth=False) for r in ROLES}
    roles["developer"].update(principals=["dev-fixture"], receives=["approved_aggregate"])
    roles["evaluator"].update(principals=["eval-fixture"])
    return dict(schema_version=1, kind="synthetic_role_contract", data_origin="synthetic_fixture", actual_access_verified=False,
                enforcement=dict(kind=kind, mechanism=mechanism), roles=roles)


def rec(scenario, phase, mode="mock", expected="deny", actual="deny", **over):
    base = dict(task_id=None, run_identity=None, role=None, assignment_id=None, contract_sha256=None, profile_version=None,
                evidence_type="synthetic_mock" if mode == "mock" else "real_permission_env", data_origin="synthetic_fixture",
                observed_at=None, null_reason=None if actual else "not run", scenario=scenario, phase=phase, mode=mode,
                access_path="fixture-path", expected=expected, actual=actual, evidence_ref=None,
                same_os_user_as_protected=None, marker="SYNTH-SENTINEL-0001")
    base.update(over)
    return base


def matrix(**kw):
    return [rec(s, p, **kw) for s in SENTINEL_SCENARIOS for p in PHASES]

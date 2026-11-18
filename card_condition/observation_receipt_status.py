"""Shared classification of synthetic receipts; no human truth or approval."""


def receipt_classification(source_type, summary, conflicts, error=None):
    if source_type not in ("synthetic_fixture", "ai", "unknown"):
        raise ValueError("unsupported synthetic receipt source")
    if (not isinstance(summary["missing_entry_ids"], list) or
            any(not isinstance(value, str) for value in summary["missing_entry_ids"]) or
            len(set(summary["missing_entry_ids"])) != len(summary["missing_entry_ids"]) or
            type(summary["display_verified"]) is not bool or not isinstance(conflicts, list) or
            any(not isinstance(value, str) for value in conflicts) or len(set(conflicts)) != len(conflicts)):
        raise ValueError("invalid receipt classification inputs")
    if error is not None:
        if not isinstance(error, str) or summary["missing_entry_ids"] or summary["display_verified"] or conflicts:
            raise ValueError("invalid rejected receipt classification")
        return "rejected", [error, "collection_not_authorized"]
    status, reasons = "synthetic_only", ["collection_not_authorized"]
    if summary["missing_entry_ids"] or not summary["display_verified"]:
        status = "pending_observation"
        reasons.append("missing_or_inconsistent_observations")
    if source_type != "synthetic_fixture":
        if conflicts:
            raise ValueError("only fixture observations may declare conflicts")
        status = "pending_provenance"
        reasons.append("not_a_human_truth_source")
    elif conflicts:
        status = "conflict"
        reasons.append("conflicting_original_observations_preserved")
    return status, reasons

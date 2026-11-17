"""Invented assignment checks only; never human authentication."""
from datetime import datetime
from .observation_packet import exact_keys


def validate_source_context(context,assignment):
    exact_keys(context,{"source_type","assignment_id","contract_id","session_id","rater_id","received_at"},"synthetic custody")
    if context["source_type"]!="synthetic_fixture":raise ValueError("actual human collection is not authorized")
    for key in ("contract_id","session_id","rater_id","received_at"):
        if not isinstance(context[key],str) or not context[key].strip():raise ValueError("invalid custody field")
    if datetime.fromisoformat(context["received_at"].replace("Z","+00:00")).utcoffset() is None:raise ValueError("timezone-aware received_at required")
    if assignment is None:
        if context["assignment_id"] is not None:raise ValueError("missing assignment")
        return False
    exact_keys(assignment,{"assignment_id","contract_id","session_id","rater_id","observation_mode","evidence_origin"},"synthetic assignment")
    if assignment["evidence_origin"]!="synthetic_fixture" or assignment["observation_mode"] not in ("H","A"):raise ValueError("invalid synthetic assignment")
    for key in ("assignment_id","contract_id","session_id","rater_id"):
        if not isinstance(assignment[key],str) or not assignment[key].strip() or assignment[key]!=context[key]:raise ValueError("assignment/custody mismatch")
    return True

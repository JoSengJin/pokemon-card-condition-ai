"""Structural checks of synthetic self-reports; never human ground truth."""
from datetime import datetime
import math
import re
from .observation_packet import COLLECTION_STATUS, exact_keys, validate_packet, validate_profile

STATES = ("unreviewed", "normal", "defect", "unassessable")
RESPONSE_KEYS = {"schema_version", "kind", "packet_id", "scope", "observation_mode", "session_id", "data_origin", "collection_status", "entries", "observations"}
EVENT_KEYS = {"event", "at", "utc_offset_minutes", "viewport_css", "device_pixel_ratio", "visibility", "visual_viewport_scale", "entry_id", "state", "image_sizes"}


def validate_event(event, entry_ids, elements):
    exact_keys(event, EVENT_KEYS, "observation event")
    if event["event"] not in ("ready", "presented", "change", "export", "resize", "visibility", "scroll", "invalidate"):
        raise ValueError("unknown observation event")
    if not isinstance(event["at"], str) or datetime.fromisoformat(event["at"].replace("Z", "+00:00")).utcoffset() is None:
        raise ValueError("timezone-aware browser time required")
    if type(event["utc_offset_minutes"]) is not int or not -840 <= event["utc_offset_minutes"] <= 840:
        raise ValueError("invalid UTC offset")
    if event["visibility"] not in ("visible", "hidden", "unknown"):
        raise ValueError("invalid visibility")
    for key in ("device_pixel_ratio", "visual_viewport_scale"):
        value = event[key]
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value <= 0):
            raise ValueError("invalid observation ratio")
    size = event["viewport_css"]
    if not isinstance(size, list) or len(size) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or n < 0 for n in size):
        raise ValueError("invalid viewport")
    if event["entry_id"] is not None and (not isinstance(event["entry_id"], str) or event["entry_id"] not in entry_ids):
        raise ValueError("unknown event entry")
    if event["event"] == "change":
        if event["entry_id"] not in entry_ids or event["state"] not in STATES:
            raise ValueError("invalid state change event")
    elif event["state"] is not None:
        raise ValueError("state on non-change event")
    if not isinstance(event["image_sizes"], list):
        raise ValueError("image observations must be a list")
    seen = set()
    for image in event["image_sizes"]:
        exact_keys(image, {"ref", "element_id", "css_size", "natural_size", "current_src_matches"}, "observed image")
        element = image["element_id"]
        if not isinstance(element, str) or element not in elements or element in seen or image["ref"] != elements[element]["ref"]:
            raise ValueError("unknown/duplicate image binding")
        seen.add(element)
        if type(image["current_src_matches"]) is not bool:
            raise ValueError("invalid image binding status")
        for key in ("css_size", "natural_size"):
            size = image[key]
            if not isinstance(size, list) or len(size) != 2 or any(type(n) not in (int, float) or not math.isfinite(n) or n < 0 for n in size):
                raise ValueError("invalid displayed dimensions")


def validate_entries(packet, entries):
    if not isinstance(entries, list):
        raise ValueError("response entries must be a list")
    expected = {entry["entry_id"]: entry for entry in packet["entries"]}
    seen = set()
    for entry in entries:
        exact_keys(entry, {"entry_id", "photo_sha256", "state", "note"}, "response entry")
        identifier = entry["entry_id"]
        if not isinstance(identifier, str) or identifier not in expected or identifier in seen:
            raise ValueError("unknown/duplicate response entry")
        seen.add(identifier)
        if entry["photo_sha256"] != expected[identifier]["photo_sha256"] or entry["state"] not in STATES or not isinstance(entry["note"], str):
            raise ValueError("invalid response identity/state/note")
    return sorted(set(expected) - seen)


def validate_observations(packet, observations):
    exact_keys(observations, {"profile", "instructions_sha256", "renderer_version", "clock_source", "assets", "events", "limitations"}, "observations")
    validate_profile(observations["profile"])
    if (observations["profile"] != packet["profile"] or observations["instructions_sha256"] != packet["instructions_sha256"] or
            observations["renderer_version"] != "synthetic-observation-v1" or observations["renderer_version"] != packet["profile"]["renderer_version"] or
            observations["clock_source"] != "browser_self_report"):
        raise ValueError("observation profile/version mismatch")
    if not isinstance(observations["limitations"], list) or any(not isinstance(s, str) for s in observations["limitations"]):
        raise ValueError("invalid observation limitations")
    expected, elements = {}, {}
    for entry in packet["entries"]:
        for asset in entry["assets"]:
            expected[asset["ref"]] = asset
            elements[entry["entry_id"] + "-" + asset["kind"]] = asset
    if not isinstance(observations["assets"], list) or not isinstance(observations["events"], list):
        raise ValueError("invalid observation lists")
    seen, verified = set(), True
    for proof in observations["assets"]:
        exact_keys(proof, {"ref", "expected_sha256", "measured_sha256", "verified", "decoded", "element_ids"}, "asset proof")
        ref = proof["ref"]
        if not isinstance(ref, str) or ref not in expected or ref in seen:
            raise ValueError("unknown/duplicate asset proof")
        seen.add(ref)
        if proof["expected_sha256"] != expected[ref]["sha256"] or type(proof["verified"]) is not bool or type(proof["decoded"]) is not bool:
            raise ValueError("invalid expected asset proof")
        measured = proof["measured_sha256"]
        if measured is not None and (not isinstance(measured, str) or not re.fullmatch(r"[0-9a-f]{64}", measured)):
            raise ValueError("invalid measured SHA")
        ids = proof["element_ids"]
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids) or any(x not in elements or elements[x]["ref"] != ref for x in ids):
            raise ValueError("invalid asset element identity")
        required_ids = {key for key, value in elements.items() if value["ref"] == ref}
        if proof["verified"] and (measured != proof["expected_sha256"] or not proof["decoded"] or set(ids) != required_ids):
            raise ValueError("inconsistent verified asset proof")
        verified = verified and proof["verified"] and proof["decoded"]
    previous = None
    for event in observations["events"]:
        validate_event(event, {e["entry_id"] for e in packet["entries"]}, elements)
        at = datetime.fromisoformat(event["at"].replace("Z", "+00:00"))
        if previous is not None and at < previous:
            raise ValueError("browser clock moved backward")
        previous = at
        if event["event"] == "invalidate":
            verified = False
        if not packet["profile"]["zoom_allowed"] and event["visual_viewport_scale"] is not None and event["visual_viewport_scale"] != 1:
            verified = False
    if not observations["events"] or observations["events"][-1]["event"] != "export":
        return False
    last = observations["events"][-1]
    images = {image["element_id"]: image for image in last["image_sizes"]}
    for key, asset in elements.items():
        image = images.get(key)
        if image is None or not image["current_src_matches"] or image["natural_size"] != asset["size"] or any(n <= 0 for n in image["css_size"]):
            verified = False
    return bool(verified and seen == set(expected))


def validate_response(packet, body):
    validate_packet(packet)
    exact_keys(body, RESPONSE_KEYS, "response")
    if (type(body["schema_version"]) is not int or body["schema_version"] != 1 or body["kind"] != "whole_surface_region_observation_response" or
            body["packet_id"] != packet["packet_id"] or body["scope"] != "whole_surface_region" or body["observation_mode"] != packet["observation_mode"] or
            body["data_origin"] != "synthetic_fixture" or body["collection_status"] != COLLECTION_STATUS or
            not isinstance(body["session_id"], str) or not body["session_id"].strip()):
        raise ValueError("invalid synthetic response scope/identity")
    missing = validate_entries(packet, body["entries"])
    verified = validate_observations(packet, body["observations"])
    last_states = {entry["entry_id"]: "unreviewed" for entry in packet["entries"]}
    for event in body["observations"]["events"]:
        if event["event"] == "change":
            last_states[event["entry_id"]] = event["state"]
    if any(entry["state"] != last_states[entry["entry_id"]] for entry in body["entries"]):
        verified = False
    return {"missing_entry_ids": missing, "display_verified": verified}

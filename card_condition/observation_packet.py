"""Blind whole-region packet metadata for synthetic fixtures only.

No image/file access, collection approval, model imports or human truth creation.
Call strict_json_loads on JSON bytes BEFORE schema validation: a dict has already
lost duplicate keys. SHA binds declared metadata, not actual displayed bytes.
"""
import copy
import hashlib
import json
import math
import re

COLLECTION_STATUS = "not_executable_pending_collection_contract_approval"
PACKET_KEYS = {
    "schema_version", "kind", "packet_id", "scope", "observation_mode", "profile",
    "instructions", "instructions_sha256", "entries", "data_origin", "collection_status",
}
PROFILE_KEYS = {
    "profile_id", "renderer_version", "instructions_version", "observation_mode",
    "viewport_css", "image_css", "device_pixel_ratio", "zoom_allowed", "resize",
    "interpolation", "approval_status",
}
ENTRY_KEYS = {
    "entry_id", "photo_id", "photo_sha256", "source_size", "normalized_box", "pixel_box", "assets",
}
ASSET_KEYS = {"asset_id", "kind", "sha256", "size", "ref"}


def exact_keys(value, expected, location):
    """Reject unknown fields instead of silently projecting leaked metadata away."""
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("unexpected or missing fields: " + location)


def packet_digest(packet):
    """Canonical SHA-256 of public content, excluding its own digest field."""
    body = {key: value for key, value in packet.items() if key != "packet_id"}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_profile(profile):
    """Null display values remain unresolved; this never approves collection."""
    exact_keys(profile, PROFILE_KEYS, "profile")
    if profile["approval_status"] != "synthetic_fixture":
        raise ValueError("only synthetic fixture profiles are accepted")
    for key in ("profile_id", "renderer_version", "instructions_version"):
        if not isinstance(profile[key], str) or not profile[key].strip():
            raise ValueError("invalid profile version or identifier")
    mode, zoom = profile["observation_mode"], profile["zoom_allowed"]
    if mode not in ("H", "A") or type(zoom) is not bool or (mode == "A" and zoom):
        raise ValueError("invalid H/A observation mode or zoom permission")
    for key in ("viewport_css", "image_css"):
        size = profile[key]
        if size is not None and (not isinstance(size, list) or len(size) != 2 or
                                 any(type(n) is not int or n <= 0 for n in size)):
            raise ValueError("invalid profile dimensions")
    ratio = profile["device_pixel_ratio"]
    if ratio is not None and (type(ratio) not in (int, float) or
                              not math.isfinite(ratio) or ratio <= 0):
        raise ValueError("invalid device pixel ratio")
    for key in ("resize", "interpolation"):
        if profile[key] is not None and (not isinstance(profile[key], str) or not profile[key].strip()):
            raise ValueError("invalid display transform declaration")


def validate_packet(packet):
    """Validate declared public identity, geometry and hashes; no asset bytes read."""
    exact_keys(packet, PACKET_KEYS, "packet")
    if (type(packet["schema_version"]) is not int or packet["schema_version"] != 1 or
            packet["kind"] != "blind_surface_observation_packet" or
            packet["scope"] != "whole_surface_region" or
            packet["data_origin"] != "synthetic_fixture" or
            packet["collection_status"] != COLLECTION_STATUS):
        raise ValueError("invalid packet scope or synthetic-only collection guard")
    validate_profile(packet["profile"])
    if packet["observation_mode"] != packet["profile"]["observation_mode"]:
        raise ValueError("packet and profile observation mode differ")
    instructions = packet["instructions"]
    if not isinstance(instructions, str) or not instructions.strip():
        raise ValueError("instructions must be a nonempty string")
    if packet["instructions_sha256"] != hashlib.sha256(instructions.encode("utf-8")).hexdigest():
        raise ValueError("instructions SHA mismatch")
    entries = packet["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("entries must be a nonempty list")
    entry_ids, photo_ids, photo_hashes, asset_ids = set(), {}, {}, {}
    for entry in entries:
        exact_keys(entry, ENTRY_KEYS, "entry")
        for key, pattern in (("entry_id", r"r[0-9]+"), ("photo_id", r"p[0-9]+"),
                             ("photo_sha256", r"[0-9a-f]{64}")):
            if not isinstance(entry[key], str) or not re.fullmatch(pattern, entry[key]):
                raise ValueError("invalid anonymous identity or photo SHA")
        if entry["entry_id"] in entry_ids:
            raise ValueError("duplicate entry ID")
        entry_ids.add(entry["entry_id"])
        size = entry["source_size"]
        if (not isinstance(size, list) or len(size) != 2 or
                any(type(n) is not int or n <= 0 for n in size)):
            raise ValueError("invalid source dimensions")
        identity = (entry["photo_sha256"], tuple(size))
        if photo_ids.setdefault(entry["photo_id"], identity) != identity:
            raise ValueError("photo ID identity conflict")
        if photo_hashes.setdefault(entry["photo_sha256"], (entry["photo_id"], tuple(size))) != (entry["photo_id"], tuple(size)):
            raise ValueError("photo SHA identity conflict")
        box = entry["normalized_box"]
        if (not isinstance(box, list) or len(box) != 4 or
                any(type(n) not in (int, float) or not math.isfinite(n) or not 0 <= n <= 1 for n in box) or
                not (box[0] < box[2] and box[1] < box[3])):
            raise ValueError("invalid normalized whole-region box")
        pixels = entry["pixel_box"]
        expected = [math.floor(box[0] * size[0]), math.floor(box[1] * size[1]),
                    math.ceil(box[2] * size[0]), math.ceil(box[3] * size[1])]
        if (not isinstance(pixels, list) or len(pixels) != 4 or
                any(type(n) is not int for n in pixels) or pixels != expected):
            raise ValueError("pixel box does not match normalized region")
        assets = entry["assets"]
        if not isinstance(assets, list) or len(assets) != 2:
            raise ValueError("context and region assets are required")
        kinds = set()
        for asset in assets:
            exact_keys(asset, ASSET_KEYS, "asset")
            asset_id, kind, sha, ref = (asset[key] for key in ("asset_id", "kind", "sha256", "ref"))
            if not isinstance(asset_id, str) or not re.fullmatch(r"a[0-9]+", asset_id):
                raise ValueError("invalid anonymous asset ID")
            if not isinstance(kind, str) or kind not in ("context", "region") or kind in kinds:
                raise ValueError("invalid or duplicate asset kind")
            kinds.add(kind)
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
                raise ValueError("invalid asset SHA")
            if not isinstance(ref, str) or not re.fullmatch(r"assets/" + asset_id + r"\.(png|jpg|jpeg)", ref):
                raise ValueError("invalid anonymous relative asset reference")
            if (not isinstance(asset["size"], list) or len(asset["size"]) != 2 or
                    any(type(n) is not int or n <= 0 for n in asset["size"])):
                raise ValueError("invalid asset dimensions")
            binding = (entry["photo_id"], kind, sha, tuple(asset["size"]), ref,
                       tuple(pixels) if kind == "region" else None)
            if asset_ids.setdefault(asset_id, binding) != binding:
                raise ValueError("asset ID identity conflict")
    if packet["packet_id"] != packet_digest(packet):
        raise ValueError("packet SHA mismatch")


def build_packet(manifest, profile, instructions):
    """Build a detached synthetic packet; caller supplies trusted synthetic prose."""
    exact_keys(manifest, {"data_origin", "entries"}, "manifest")
    if manifest["data_origin"] != "synthetic_fixture":
        raise ValueError("only synthetic manifests are accepted")
    if not isinstance(manifest["entries"], list) or not manifest["entries"]:
        raise ValueError("entries must be a nonempty list")
    entries = []
    for entry in manifest["entries"]:
        exact_keys(entry, ENTRY_KEYS | {"completed"}, "manifest entry")
        if entry["completed"] is not False:
            raise ValueError("completed or unconfirmed completion state is not accepted")
        entries.append({key: copy.deepcopy(value) for key, value in entry.items() if key != "completed"})
    validate_profile(profile)
    if not isinstance(instructions, str):
        raise ValueError("instructions must be a string")
    packet = {
        "schema_version": 1, "kind": "blind_surface_observation_packet", "packet_id": "",
        "scope": "whole_surface_region", "observation_mode": profile["observation_mode"],
        "profile": copy.deepcopy(profile), "instructions": instructions,
        "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
        "entries": entries, "data_origin": "synthetic_fixture", "collection_status": COLLECTION_STATUS,
    }
    packet["packet_id"] = packet_digest(packet)
    validate_packet(packet)
    return packet


def unique_object_pairs(pairs):
    """json object_pairs_hook: reject duplicates at every object nesting level."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def strict_json_loads(raw_bytes):
    """Parse UTF-8 bytes without replacing them; durable custody is a receipt task."""
    if not isinstance(raw_bytes, bytes):
        raise ValueError("JSON input must be raw UTF-8 bytes")
    body = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=unique_object_pairs)
    json.dumps(body, allow_nan=False)  # Also reject NaN/Infinity and numeric overflow.
    return body

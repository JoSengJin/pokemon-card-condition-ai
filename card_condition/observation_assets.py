"""Verify in-memory synthetic display assets; never read source image paths.

A returned byte object is exactly the one hashed and decoded. This is not proof
of browser display, synthetic provenance, human observation or collection approval.
"""
import hashlib
from io import BytesIO

from PIL import Image

from .observation_packet import validate_packet


def decoded_size(raw, expected_format):
    """Check both container integrity and pixels using the same immutable bytes."""
    try:
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG"]) as image:
            actual_format = image.format
            frame_count = getattr(image, "n_frames", 1)
            image.verify()
        # verify invalidates the decoder; reopen the checked bytes, never a path.
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG"]) as image:
            image.load()
            size = image.size
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("asset image decode failed") from exc
    if frame_count != 1:
        raise ValueError("asset image must be single-frame")
    if actual_format != expected_format:
        raise ValueError("asset image format mismatch")
    return size


def verify_assets(packet, assets):
    """Return a detached ref→same-bytes mapping only after every asset passes.

    JSON callers must first use observation_packet.strict_json_loads. The packet
    validator retains synthetic-only declarations and the non-executable status.
    """
    validate_packet(packet)
    if not isinstance(assets, dict):
        raise ValueError("assets must be a ref-to-bytes dict")
    supplied = dict(assets)
    expected = {asset["ref"]: asset for entry in packet["entries"] for asset in entry["assets"]}
    if set(supplied) != set(expected):
        raise ValueError("missing or extra display assets")
    verified = {}
    for ref, asset in expected.items():
        raw = supplied[ref]
        if type(raw) is not bytes:
            raise ValueError("asset value must be immutable bytes")
        if hashlib.sha256(raw).hexdigest() != asset["sha256"]:
            raise ValueError("asset SHA mismatch")
        expected_format = "PNG" if ref.endswith(".png") else "JPEG"
        if decoded_size(raw, expected_format) != tuple(asset["size"]):
            raise ValueError("asset size mismatch")
        verified[ref] = raw
    return verified

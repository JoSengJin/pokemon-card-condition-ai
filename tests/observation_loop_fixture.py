"""Generated images and fake identities only; never read a dataset."""
import hashlib
from io import BytesIO
from PIL import Image
from card_condition.observation_packet import build_packet


def fixture(mode="H", instructions="합성 시험 전용 안내"):
    assets, metadata = {}, []
    for asset_id, kind, size, color in (("a1", "context", (8, 8), "red"), ("a2", "region", (4, 4), "blue")):
        with BytesIO() as stream:
            with Image.new("RGB", size, color) as image:
                image.save(stream, "PNG")
            raw = stream.getvalue()
        ref = "assets/" + asset_id + ".png"
        assets[ref] = raw
        metadata.append(dict(asset_id=asset_id, kind=kind, size=list(size), ref=ref, sha256=hashlib.sha256(raw).hexdigest()))
    profile = dict(profile_id="synthetic", renderer_version="synthetic-observation-v1", instructions_version="fixture-v1",
                   observation_mode=mode, viewport_css=None, image_css=None, device_pixel_ratio=None,
                   zoom_allowed=mode == "H", resize=None, interpolation=None, approval_status="synthetic_fixture")
    manifest = dict(data_origin="synthetic_fixture", entries=[dict(entry_id="r1", photo_id="p1", photo_sha256="a" * 64,
                    source_size=[8, 8], normalized_box=[0.25, 0.25, 0.75, 0.75], pixel_box=[2, 2, 6, 6], assets=metadata, completed=False)])
    return build_packet(manifest, profile, instructions), assets


def response_fixture(packet):
    proofs, images = [], []
    for entry in packet["entries"]:
        for asset in entry["assets"]:
            element_id = entry["entry_id"] + "-" + asset["kind"]
            proofs.append(dict(ref=asset["ref"], expected_sha256=asset["sha256"], measured_sha256=asset["sha256"],
                               verified=True, decoded=True, element_ids=[element_id]))
            images.append(dict(ref=asset["ref"], element_id=element_id, css_size=asset["size"], natural_size=asset["size"], current_src_matches=True))
    event = dict(event="export", at="2026-11-17T00:00:00.000Z", utc_offset_minutes=0, viewport_css=[800, 600],
                 device_pixel_ratio=1, visibility="visible", visual_viewport_scale=None, entry_id=None, state=None, image_sizes=images)
    return dict(schema_version=1, kind="whole_surface_region_observation_response", packet_id=packet["packet_id"],
                scope="whole_surface_region", observation_mode=packet["observation_mode"], session_id="synthetic-session",
                data_origin="synthetic_fixture", collection_status=packet["collection_status"],
                entries=[dict(entry_id=e["entry_id"], photo_sha256=e["photo_sha256"], state="unreviewed", note="") for e in packet["entries"]],
                observations=dict(profile=packet["profile"], instructions_sha256=packet["instructions_sha256"], renderer_version="synthetic-observation-v1",
                    clock_source="browser_self_report", assets=proofs, events=[event], limitations=["browser_self_report", "attention_unverified"]))

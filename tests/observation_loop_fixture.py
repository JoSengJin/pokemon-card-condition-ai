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

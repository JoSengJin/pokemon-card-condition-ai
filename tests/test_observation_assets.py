"""All images are generated in memory; no photos, labels or model imports."""
import copy
import hashlib
import importlib
import importlib.util
from io import BytesIO
import struct
import unittest
import zlib

from PIL import Image
from card_condition.observation_packet import build_packet, packet_digest


class ObservationAssetsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_assets"),
                             "asset byte verifier is missing")
        self.api = importlib.import_module("card_condition.observation_assets")
        self.profile = {
            "profile_id": "synthetic", "renderer_version": "fixture-v1",
            "instructions_version": "fixture-v1", "observation_mode": "H",
            "viewport_css": None, "image_css": None, "device_pixel_ratio": None,
            "zoom_allowed": True, "resize": None, "interpolation": None,
            "approval_status": "synthetic_fixture",
        }
        self.assets = {}
        metadata = []
        for asset_id, kind, size, color in (("a1", "context", (8, 8), "red"),
                                             ("a2", "region", (4, 4), "blue")):
            with BytesIO() as stream:
                with Image.new("RGB", size, color) as image:
                    image.save(stream, format="PNG")
                raw = stream.getvalue()
            ref = "assets/" + asset_id + ".png"
            self.assets[ref] = raw
            metadata.append({"asset_id": asset_id, "kind": kind, "size": list(size),
                             "sha256": hashlib.sha256(raw).hexdigest(), "ref": ref})
        self.manifest = {"data_origin": "synthetic_fixture", "entries": [{
            "entry_id": "r1", "photo_id": "p1", "photo_sha256": "a" * 64,
            "source_size": [8, 8], "normalized_box": [0.25, 0.25, 0.75, 0.75],
            "pixel_box": [2, 2, 6, 6], "assets": metadata, "completed": False,
        }]}
        self.packet = build_packet(self.manifest, self.profile, "Synthetic fixture instructions")

    def test_returns_same_immutable_bytes_for_png_jpeg_and_both_modes(self):
        for mode, image_format, suffix in (("H", "PNG", "png"), ("A", "JPEG", "jpg"),
                                           ("H", "JPEG", "jpeg")):
            with self.subTest(mode=mode, image_format=image_format, suffix=suffix):
                manifest, profile = copy.deepcopy(self.manifest), copy.deepcopy(self.profile)
                profile.update(observation_mode=mode, zoom_allowed=(mode == "H"))
                assets = {}
                for asset in manifest["entries"][0]["assets"]:
                    with BytesIO() as stream:
                        with Image.new("RGB", tuple(asset["size"]), "green") as image:
                            image.save(stream, format=image_format)
                        raw = stream.getvalue()
                    asset.update(ref="assets/" + asset["asset_id"] + "." + suffix,
                                 sha256=hashlib.sha256(raw).hexdigest())
                    assets[asset["ref"]] = raw
                packet = build_packet(manifest, profile, "Synthetic fixture")
                before_packet, before_assets = copy.deepcopy(packet), dict(assets)
                verified = self.api.verify_assets(packet, assets)
                self.assertIsNot(verified, assets)
                self.assertEqual(set(verified), set(assets))
                for ref in assets:
                    self.assertIs(verified[ref], assets[ref])
                self.assertEqual(packet, before_packet)
                self.assertEqual(assets, before_assets)
                self.assertEqual(packet["collection_status"],
                                 "not_executable_pending_collection_contract_approval")
                self.assertIsNone(packet["profile"]["image_css"])
                ref = next(iter(assets))
                assets[ref] = b"replaced after verification"
                self.assertIs(verified[ref], before_assets[ref])

    def test_rejects_sha_mismatch_and_nonbytes_without_mutating_inputs(self):
        ref = "assets/a1.png"
        raw = self.assets[ref]
        flipped = raw[:20] + bytes([raw[20] ^ 1]) + raw[21:]
        for value in (flipped, b"", bytearray(raw), memoryview(raw), "assets/a1.png", BytesIO(raw)):
            with self.subTest(value_type=type(value).__name__):
                assets = dict(self.assets)
                assets[ref] = value
                before_packet = copy.deepcopy(self.packet)
                with self.assertRaises(ValueError):
                    self.api.verify_assets(self.packet, assets)
                self.assertIs(assets[ref], value)
                self.assertEqual(self.packet, before_packet)
        changed = copy.deepcopy(self.packet)
        changed["entries"][0]["assets"][0]["sha256"] = "0" * 64
        changed["packet_id"] = packet_digest(changed)
        with self.assertRaisesRegex(ValueError, "SHA"):
            self.api.verify_assets(changed, self.assets)

    def test_rejects_hash_matching_damaged_images_including_short_pixel_data(self):
        raw = self.assets["assets/a1.png"]
        # Valid PNG chunks/CRC but decoded pixels are too short: verify alone is insufficient.
        chunks, offset = [raw[:8]], 8
        while offset < len(raw):
            length = struct.unpack(">I", raw[offset:offset + 4])[0]
            chunk_type = raw[offset + 4:offset + 8]
            chunk = raw[offset:offset + 12 + length]
            if chunk_type == b"IDAT":
                payload = zlib.compress(b"\x00")
                chunk = (struct.pack(">I", len(payload)) + chunk_type + payload +
                         struct.pack(">I", zlib.crc32(chunk_type + payload)))
            chunks.append(chunk)
            offset += 12 + length
        short_pixels = b"".join(chunks)
        for damaged in (b"not an image", raw[:48], short_pixels):
            with self.subTest(length=len(damaged)):
                packet, assets = copy.deepcopy(self.packet), dict(self.assets)
                assets["assets/a1.png"] = damaged
                packet["entries"][0]["assets"][0]["sha256"] = hashlib.sha256(damaged).hexdigest()
                packet["packet_id"] = packet_digest(packet)
                with self.assertRaisesRegex(ValueError, "decode"):
                    self.api.verify_assets(packet, assets)

    def test_rejects_wrong_dimensions_and_image_format(self):
        packet = copy.deepcopy(self.packet)
        packet["entries"][0]["assets"][0]["size"] = [9, 8]
        packet["packet_id"] = packet_digest(packet)
        with self.assertRaisesRegex(ValueError, "size"):
            self.api.verify_assets(packet, self.assets)
        with BytesIO() as stream:
            with Image.new("RGB", (8, 8), "red") as image:
                image.save(stream, format="JPEG")
            jpeg = stream.getvalue()
        packet, assets = copy.deepcopy(self.packet), dict(self.assets)
        assets["assets/a1.png"] = jpeg
        packet["entries"][0]["assets"][0]["sha256"] = hashlib.sha256(jpeg).hexdigest()
        packet["packet_id"] = packet_digest(packet)
        with self.assertRaisesRegex(ValueError, "format"):
            self.api.verify_assets(packet, assets)
        # A static display verifier must not accept unexamined later PNG frames.
        with BytesIO() as stream:
            with Image.new("RGB", (8, 8), "red") as first, Image.new("RGB", (8, 8), "blue") as second:
                first.save(stream, format="PNG", save_all=True, append_images=[second], duration=100, loop=0)
            animated = stream.getvalue()
        packet, assets = copy.deepcopy(self.packet), dict(self.assets)
        assets["assets/a1.png"] = animated
        packet["entries"][0]["assets"][0]["sha256"] = hashlib.sha256(animated).hexdigest()
        packet["packet_id"] = packet_digest(packet)
        with self.assertRaisesRegex(ValueError, "single-frame"):
            self.api.verify_assets(packet, assets)

    def test_requires_exact_asset_set_and_allows_shared_context(self):
        for assets in ({}, {"assets/a1.png": self.assets["assets/a1.png"]},
                       dict(self.assets, **{"assets/a3.png": self.assets["assets/a1.png"]}),
                       list(self.assets.items())):
            with self.subTest(asset_type=type(assets).__name__, length=len(assets)):
                with self.assertRaises(ValueError):
                    self.api.verify_assets(self.packet, assets)
        manifest, assets = copy.deepcopy(self.manifest), dict(self.assets)
        second = copy.deepcopy(manifest["entries"][0])
        second.update(entry_id="r2", normalized_box=[0, 0, 0.5, 0.5], pixel_box=[0, 0, 4, 4])
        second["assets"][1].update(asset_id="a3", ref="assets/a3.png")
        assets["assets/a3.png"] = assets["assets/a2.png"]
        manifest["entries"].append(second)
        packet = build_packet(manifest, self.profile, "Synthetic shared context")
        result = self.api.verify_assets(packet, assets)
        self.assertEqual(len(result), 3)
        self.assertIs(result["assets/a1.png"], assets["assets/a1.png"])

    def test_reuses_packet_guards_before_accepting_assets(self):
        for key, value in (("collection_status", "executable"), ("data_origin", "real"),
                           ("scope", "candidate_box"), ("score", 0.9),
                           ("region_target", 1), ("candidate_box", [0, 0, 1, 1])):
            with self.subTest(key=key):
                packet = copy.deepcopy(self.packet)
                packet[key] = value
                packet["packet_id"] = packet_digest(packet)
                with self.assertRaises(ValueError):
                    self.api.verify_assets(packet, self.assets)
        packet = copy.deepcopy(self.packet)
        packet["profile"]["approval_status"] = "approved"
        packet["packet_id"] = packet_digest(packet)
        with self.assertRaises(ValueError):
            self.api.verify_assets(packet, self.assets)
        packet = copy.deepcopy(self.packet)
        packet["packet_id"] = "0" * 64
        with self.assertRaises(ValueError):
            self.api.verify_assets(packet, self.assets)

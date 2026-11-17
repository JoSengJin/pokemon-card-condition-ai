"""Synthetic metadata only: no photos, labels, model imports or collection."""
import copy
import hashlib
import importlib
import importlib.util
import json
import unittest

PROFILE = {
    "profile_id": "synthetic-profile", "renderer_version": "fixture-v1",
    "instructions_version": "fixture-v1", "observation_mode": "H",
    "viewport_css": None, "image_css": None, "device_pixel_ratio": None,
    "zoom_allowed": True, "resize": None, "interpolation": None,
    "approval_status": "synthetic_fixture",
}
MANIFEST = {"data_origin": "synthetic_fixture", "entries": [{
    "entry_id": "r1", "photo_id": "p1", "photo_sha256": "a" * 64,
    "source_size": [100, 80], "normalized_box": [0.1, 0.25, 0.9, 0.75],
    "pixel_box": [10, 20, 90, 60], "completed": False,
    "assets": [
        {"asset_id": "a1", "kind": "context", "sha256": "b" * 64,
         "size": [100, 80], "ref": "assets/a1.png"},
        {"asset_id": "a2", "kind": "region", "sha256": "c" * 64,
         "size": [80, 40], "ref": "assets/a2.png"},
    ],
}]}


class ObservationPacketTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_packet"),
                             "blind packet implementation is missing")
        self.api = importlib.import_module("card_condition.observation_packet")
        self.manifest = copy.deepcopy(MANIFEST)
        self.profile = copy.deepcopy(PROFILE)

    def test_builds_detached_blind_packet_with_collection_blocked(self):
        for mode in ("H", "A"):
            with self.subTest(mode=mode):
                self.profile.update(observation_mode=mode, zoom_allowed=(mode == "H"))
                before = copy.deepcopy((self.manifest, self.profile))
                packet = self.api.build_packet(self.manifest, self.profile, "Synthetic instructions")
                self.assertEqual((self.manifest, self.profile), before)
                self.assertEqual(packet["scope"], "whole_surface_region")
                self.assertEqual(packet["observation_mode"], mode)
                self.assertEqual(packet["data_origin"], "synthetic_fixture")
                self.assertEqual(packet["collection_status"],
                                 "not_executable_pending_collection_contract_approval")
                self.assertNotIn("completed", packet["entries"][0])
                self.assertIsNone(packet["profile"]["viewport_css"])
                self.api.validate_packet(packet)
                encoded = json.dumps(packet, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode("utf-8")
                self.assertEqual(self.api.strict_json_loads(encoded), packet)
                packet["entries"][0]["pixel_box"][0] = 999
                self.assertEqual(self.manifest, before[0])

    def test_rejects_forbidden_or_unknown_fields_at_every_schema_level(self):
        for field in ("score", "target", "region_target", "previous_label", "rank",
                      "candidate_token", "candidate_box", "heatmap", "metadata"):
            for level in ("manifest", "entry", "profile", "asset", "packet"):
                with self.subTest(field=field, level=level):
                    manifest, profile = copy.deepcopy(MANIFEST), copy.deepcopy(PROFILE)
                    packet = self.api.build_packet(manifest, profile, "Synthetic instructions")
                    destination = {"manifest": manifest, "entry": manifest["entries"][0],
                                   "profile": profile, "asset": manifest["entries"][0]["assets"][0],
                                   "packet": packet}[level]
                    destination[field] = {"nested": "forbidden synthetic metadata"}
                    with self.assertRaises(ValueError):
                        if level == "packet":
                            packet["packet_id"] = self.api.packet_digest(packet)
                            self.api.validate_packet(packet)
                        else:
                            self.api.build_packet(manifest, profile, "Synthetic instructions")

    def test_strict_json_rejects_duplicates_without_changing_raw_bytes(self):
        for raw in (b'{"x":1,"x":1}', b'{"x":{"state":"a","state":"b"}}',
                    b'{"x":[{"packet_id":1,"packet_id":2}]}',
                    b'{"state":1,"\\u0073tate":2}'):
            with self.subTest(raw=raw):
                before = bytes(raw)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.api.strict_json_loads(raw)
                self.assertEqual(raw, before)
        self.assertEqual(self.api.strict_json_loads(b'{"x":[{"a":1},{"a":2}]}'),
                         {"x": [{"a": 1}, {"a": 2}]})
        for raw in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e400}', b'[] trailing', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.api.strict_json_loads(raw)
        with self.assertRaises(ValueError):
            self.api.strict_json_loads('{"x":1}')

    def test_rejects_invalid_geometry_hashes_paths_and_identity(self):
        bad_entries = (
            ("source_size", [True, 80]), ("source_size", [0, 80]),
            ("normalized_box", [0, 0, float("nan"), 1]),
            ("normalized_box", [0, 0, 1.1, 1]), ("normalized_box", [1, 0, 0, 1]),
            ("pixel_box", [0, 0, 90, 60]), ("pixel_box", [10, 20, 90.0, 60]),
            ("photo_sha256", "A" * 64), ("entry_id", "score-0.9"),
            ("completed", True), ("completed", 0),
        )
        for key, value in bad_entries:
            with self.subTest(key=key, value=value):
                manifest = copy.deepcopy(MANIFEST)
                manifest["entries"][0][key] = value
                with self.assertRaises(ValueError):
                    self.api.build_packet(manifest, PROFILE, "Synthetic")
        for key, value in (("ref", "../source.png"), ("ref", "assets/a1.png?score=1"),
                           ("ref", "https://example.com/a1.png"), ("ref", "assets/a2.png"),
                           ("size", [0, 1]), ("sha256", "bad"), ("kind", "candidate")):
            with self.subTest(asset_key=key, value=value):
                manifest = copy.deepcopy(MANIFEST)
                manifest["entries"][0]["assets"][0][key] = value
                with self.assertRaises(ValueError):
                    self.api.build_packet(manifest, PROFILE, "Synthetic")
        for variant in ("duplicate", "photo_conflict", "asset_conflict", "missing_context"):
            with self.subTest(identity=variant):
                manifest = copy.deepcopy(MANIFEST)
                second = copy.deepcopy(manifest["entries"][0])
                if variant != "duplicate":
                    second["entry_id"] = "r2"
                if variant == "photo_conflict":
                    second["photo_sha256"] = "d" * 64
                if variant == "asset_conflict":
                    second["assets"][0]["sha256"] = "d" * 64
                if variant == "missing_context":
                    second["assets"] = second["assets"][1:]
                manifest["entries"].append(second)
                with self.assertRaises(ValueError):
                    self.api.build_packet(manifest, PROFILE, "Synthetic")
        manifest = copy.deepcopy(MANIFEST)
        second = copy.deepcopy(manifest["entries"][0])
        second.update(entry_id="r2", normalized_box=[0, 0, 1, 1], pixel_box=[0, 0, 100, 80])
        second["assets"][1].update(asset_id="a3", ref="assets/a3.png", size=[100, 80])
        manifest["entries"].append(second)
        self.assertEqual(len(self.api.build_packet(manifest, PROFILE, "Synthetic")["entries"]), 2)

    def test_hash_binds_public_content_and_tampering_is_rejected(self):
        packet = self.api.build_packet(MANIFEST, PROFILE, "  합성 안내\n")
        body = {key: value for key, value in packet.items() if key != "packet_id"}
        expected = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        self.assertEqual(packet["packet_id"], expected)
        self.assertEqual(packet["instructions"], "  합성 안내\n")
        self.assertEqual(packet["instructions_sha256"], hashlib.sha256("  합성 안내\n".encode()).hexdigest())
        self.assertEqual(self.api.packet_digest(dict(reversed(list(packet.items())))), expected)
        for key, value in (("instructions", "changed"), ("packet_id", "0" * 64)):
            with self.subTest(key=key):
                changed = copy.deepcopy(packet)
                changed[key] = value
                with self.assertRaises(ValueError):
                    self.api.validate_packet(changed)
        packet["instructions_sha256"] = "0" * 64
        packet["packet_id"] = self.api.packet_digest(packet)
        with self.assertRaises(ValueError):
            self.api.validate_packet(packet)

    def test_synthetic_guards_and_unresolved_profile_remain_blocked(self):
        for key, value in (("approval_status", "approved"), ("observation_mode", "other"),
                           ("viewport_css", [True, 20]), ("device_pixel_ratio", float("inf")),
                           ("device_pixel_ratio", 0), ("zoom_allowed", 1)):
            with self.subTest(profile_key=key):
                profile = copy.deepcopy(PROFILE)
                profile[key] = value
                with self.assertRaises(ValueError):
                    self.api.build_packet(MANIFEST, profile, "Synthetic")
        profile = copy.deepcopy(PROFILE)
        profile.update(observation_mode="A", zoom_allowed=True)
        with self.assertRaises(ValueError):
            self.api.build_packet(MANIFEST, profile, "Synthetic")
        manifest = copy.deepcopy(MANIFEST)
        manifest["data_origin"] = "real"
        with self.assertRaises(ValueError):
            self.api.build_packet(manifest, PROFILE, "Synthetic")
        for key, value in (("collection_status", "executable"), ("data_origin", "real"),
                           ("scope", "candidate_box"), ("kind", "crop_packet"),
                           ("observation_mode", "A"), ("schema_version", True)):
            with self.subTest(packet_key=key):
                packet = self.api.build_packet(MANIFEST, PROFILE, "Synthetic")
                packet[key] = value
                packet["packet_id"] = self.api.packet_digest(packet)
                with self.assertRaises(ValueError):
                    self.api.validate_packet(packet)
        for manifest in ({"data_origin": "synthetic_fixture", "entries": []}, None):
            with self.assertRaises(ValueError):
                self.api.build_packet(manifest, PROFILE, "Synthetic")

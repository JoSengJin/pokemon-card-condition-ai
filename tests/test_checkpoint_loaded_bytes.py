import hashlib
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import Mock, patch

import torch
from card_condition import region_model, side_model
from card_condition.data import LABELS
from card_condition.regions import REGION_LABELS


def checkpoint_fixture(root, architecture, labels):
    path = root / 'fixture.pt'
    meta = dict(architecture=architecture, labels=list(labels), supported=list(labels),
                backbone={}, head={}, crop=True, image_size=224)
    torch.save(meta, path)
    return path, path.read_bytes(), meta


def components():
    backbone, head = Mock(), Mock()
    backbone.to.return_value = backbone
    head.to.return_value = head
    head.eval.return_value = head
    return backbone, head


class LoadedBytesTest(unittest.TestCase):
    def test_region_and_side_report_sha_of_deserialized_bytes_despite_path_replacement(self):
        for module, constructor, architecture, labels in (
                (region_model, region_model.RegionAnalyzer, 'mobilenet_v3_small_region_v1', REGION_LABELS),
                (side_model, side_model.SideAnalyzer, 'mobilenet_v3_small_single_side_v1', LABELS)):
            with self.subTest(architecture=architecture), tempfile.TemporaryDirectory() as directory:
                path, original, meta = checkpoint_fixture(Path(directory), architecture, labels)
                backbone, head = components()
                def replaced(*args, **kwargs):
                    path.write_bytes(b'replaced after metadata was deserialized')
                backbone.load_state_dict.side_effect = replaced
                with patch.object(module, 'backbone_for', return_value=(backbone, 1)), \
                     patch.object(module.nn, 'Linear', return_value=head):
                    analyzer = constructor(path, 'cpu')
                self.assertEqual(meta, analyzer.meta)
                self.assertEqual(hashlib.sha256(original).hexdigest(), analyzer.model_sha256)
                self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), analyzer.model_sha256)
                backbone.load_state_dict.assert_called_once_with(meta['backbone'], strict=True)
                head.load_state_dict.assert_called_once_with(meta['head'], strict=True)

    def test_point_delegate_receives_the_same_snapshot_not_a_reopened_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path, original, meta = checkpoint_fixture(Path(directory), 'mobilenet_v3_small_point_grid_v1', REGION_LABELS)
            backbone, head = components()
            received = []
            def probe(snapshot, device):
                received.append(snapshot.getvalue())
                path.write_bytes(b'replaced during point loading')
                return meta, backbone, head, False
            with patch.object(region_model, 'load_probe_model', side_effect=probe):
                analyzer = region_model.RegionAnalyzer(path, 'cpu')
            self.assertEqual([original], received)
            self.assertEqual(hashlib.sha256(original).hexdigest(), analyzer.model_sha256)
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), analyzer.model_sha256)

    def test_invalid_snapshots_fail_before_backbone_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'invalid.pt'
            path.write_bytes(b'not a valid checkpoint')
            for module, constructor in ((region_model, region_model.RegionAnalyzer), (side_model, side_model.SideAnalyzer)):
                with self.subTest(module=module.__name__), patch.object(module, 'backbone_for') as backbone:
                    with self.assertRaises(pickle.UnpicklingError):
                        constructor(path, 'cpu')
                    backbone.assert_not_called()

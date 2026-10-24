"""Shared photo guards through point_probe, with all model computation mocked."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image

from card_condition import point_probe as probe
from test_evaluation_inputs import evaluation_fixture
from test_evaluation_consistency_contract import Rewrite


def prepare(root):
    manifest, history, checkpoint, rows, _ = evaluation_fixture(root, 'region')
    manifest.write_text('\n'.join(json.dumps(row) for row in rows[:4]))
    history.write_text('\n'.join(json.dumps(row) for row in rows[:2]))
    return manifest, history, checkpoint, rows


class PointProbeCompatibilityTest(unittest.TestCase):
    def test_probe_keeps_shared_guard_with_model_execution_mocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, history, checkpoint, rows = prepare(root)
            output = root / 'probe.json'
            before = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
            with patch.object(probe, 'probe_model', return_value={'mock_only': True}) as model:
                result = probe.point_probe(manifest, [checkpoint], output, [rows[2]['id'], rows[3]['id']], [history])
            model.assert_called_once()
            self.assertEqual([{'mock_only': True}], result['reports'])
            self.assertFalse(result['training_performed'])
            self.assertFalse(result['production_ready'])
            self.assertEqual(result, json.loads(output.read_text()))
            self.assertTrue(all(p.read_bytes() == content for p, content in before.items()))

    def test_probe_refuses_photo_replaced_before_hash_recording(self):
        from card_condition import evaluation_inputs
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, history, checkpoint, rows = prepare(root)
            replacement = root / 'replacement.png'
            Image.new('RGB', (90, 130), (9, 8, 7)).save(replacement)
            rewrite = Rewrite(rows[2]['front'], replacement.read_bytes(), evaluation_inputs.track_photos)
            output = root / 'probe.json'
            with patch.object(evaluation_inputs, 'track_photos', rewrite), patch.object(probe, 'probe_model') as model:
                with self.assertRaisesRegex(ValueError, 'photo changed'):
                    probe.point_probe(manifest, [checkpoint], output, [rows[2]['id']], [history])
            model.assert_not_called()
            self.assertFalse(output.exists())

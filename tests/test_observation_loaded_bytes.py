import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch
from card_condition import visibility_model, observation_fitting, observation_side_diagnostics
from test_checkpoint_loaded_bytes import components


class ObservationLoadedBytesTest(unittest.TestCase):
    def test_loaded_snapshot_sha_survives_path_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.pt'
            meta = dict(architecture='mobilenet_v3_small_visibility_v1', target='observation_limited',
                        image_size=224, backbone={}, head={})
            torch.save(meta, path)
            original = path.read_bytes()
            backbone, head = components()
            def replaced(*args, **kwargs):
                path.write_bytes(b'replaced after deserialize')
            backbone.load_state_dict.side_effect = replaced
            with patch.object(visibility_model, 'backbone_for', return_value=(backbone, 1)), \
                 patch.object(visibility_model.nn, 'Linear', return_value=head):
                analyzer = visibility_model.VisibilityAnalyzer(path, 'cpu')
            self.assertEqual(hashlib.sha256(original).hexdigest(), analyzer.model_sha256)
            self.assertNotEqual(hashlib.sha256(path.read_bytes()).hexdigest(), analyzer.model_sha256)
            backbone.load_state_dict.assert_called_once_with(meta['backbone'], strict=True)
            head.load_state_dict.assert_called_once_with(meta['head'], strict=True)

    def test_existing_public_names_and_training_globals_remain_compatible(self):
        self.assertEqual('observation_limited', visibility_model.TARGET)
        for name in ('class_group_weights', 'fit_centroid', 'fit_side_centroids'):
            self.assertIs(getattr(visibility_model, name), getattr(observation_fitting, name))
            self.assertIs(visibility_model.experiment.__globals__[name], getattr(observation_fitting, name))
        self.assertIs(visibility_model.side_diagnostics, observation_side_diagnostics.side_diagnostics)
        self.assertEqual('card_condition.visibility_model', visibility_model.VisibilityAnalyzer.__module__)
        self.assertEqual('card_condition.visibility_model', visibility_model.observation_features.__module__)

    def test_existing_feature_patch_namespace_and_input_coordinates_remain(self):
        row = dict(image='never-opened', box=[.1, .2, .9, .8])
        with patch('card_condition.visibility_model.patch_features') as extract:
            visibility_model.observation_features(None, row, 'cpu', interior=True)
        for found, expected in zip(extract.call_args.args[1]['box'], [.14, .23, .86, .77]):
            self.assertAlmostEqual(expected, found)
        self.assertEqual([.1, .2, .9, .8], row['box'])

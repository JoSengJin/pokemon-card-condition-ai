import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
import torch
from torch import nn

from card_condition.point_probe import point_probe, load_probe_model
from card_condition.regions import REGION_LABELS
from card_condition.side_model import backbone_for
from test_pipeline import fixture


class PointProbeTest(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.manifest, self.rows = fixture(self.root)
        for i in (2, 3):
            row = self.rows[i]
            row['labels']['gradable'] = None
            annotation = dict(image=str(self.root/row['front']), box=[0, 0, 1, 1], labels=dict(row['labels']))
            if i == 2:
                annotation['region_labels'] = {'center': dict(corner_defect=None, edge_defect=None, surface_defect=0)}
            else:
                annotation['defect_points'] = [dict(label='surface_defect', x=.5, y=.5)]
            row['side_annotations'] = {'front': annotation}
        # Final-test images must never be opened by a development probe.
        for row in self.rows[4:]: row['front'] = 'unread-test.png'
        self.write()
        self.history = self.root/'history.jsonl'
        self.history.write_text('\n'.join(json.dumps(r) for r in self.rows[:2]))
        backbone, dimension = backbone_for('mobilenet_v3_small')
        head = nn.Linear(dimension, len(REGION_LABELS))
        head.weight.data.zero_(); head.bias.data.fill_(-2)
        self.meta = dict(architecture='mobilenet_v3_small_region_v1', backbone_name='mobilenet_v3_small',
            labels=list(REGION_LABELS), supported=['surface_defect'], backbone=backbone.state_dict(),
            head=head.state_dict(), development_ids=['0'], development_groups=['0'],
            development_image_hashes=['0'*64])
        self.checkpoint = self.root/'model.pt'
        torch.save(self.meta, self.checkpoint)

    def tearDown(self):
        self.temp.cleanup()

    def write(self):
        self.manifest.write_text('\n'.join(json.dumps(r) for r in self.rows))

    def run_probe(self, output='probe.json', cards=('2', '3'), history=None):
        return point_probe(self.manifest, [self.checkpoint], self.root/output,
                           list(cards), [self.history] if history is None else history)

    def test_frozen_comparison_unknowns_and_input_preservation(self):
        candidate = copy.deepcopy(self.meta)
        candidate['architecture'] = 'mobilenet_v3_small_point_grid_v1'
        candidate['head']['bias'].fill_(2)
        path = self.root/'candidate.pt'; torch.save(candidate, path)
        before = {p: p.read_bytes() for p in (self.manifest, self.checkpoint, path, self.history)}
        report = point_probe(self.manifest, [self.checkpoint, path], self.root/'probe.json',
                             ['2', '3'], [self.history])
        self.assertEqual(2, report['groups']); self.assertEqual(2, report['regions'])
        self.assertEqual(dict(tp=0, tn=1, fp=0, fn=1), report['reports'][0]['metrics']['surface_defect'])
        self.assertEqual(dict(tp=1, tn=0, fp=1, fn=0), report['reports'][1]['metrics']['surface_defect'])
        self.assertIsNone(report['reports'][0]['predictions'][0]['probabilities']['corner_defect'])
        self.assertFalse(report['training_performed']); self.assertFalse(report['production_ready'])
        self.assertTrue(report['requires_gemini'])
        for p, content in before.items(): self.assertEqual(content, p.read_bytes())
        with self.assertRaisesRegex(ValueError, 'exists'): self.run_probe()

    def test_development_overlap_and_incomplete_metadata_blocked(self):
        for key, value in (('development_ids', ['2']), ('development_groups', ['2'])):
            meta = dict(self.meta, **{key: value}); torch.save(meta, self.checkpoint)
            with self.assertRaisesRegex(ValueError, 'Development'): self.run_probe()
            self.assertFalse((self.root/'probe.json').exists())
        torch.save(self.meta, self.checkpoint)
        older = copy.deepcopy(self.rows[2]); older['id'] = 'older'; older['group'] = 'older'
        self.history.write_text(json.dumps(older))
        with self.assertRaisesRegex(ValueError, 'Development'): self.run_probe()
        for key in ('development_ids', 'development_groups', 'development_image_hashes'):
            meta = dict(self.meta); del meta[key]; torch.save(meta, self.checkpoint)
            with self.assertRaisesRegex(ValueError, 'provenance'): self.run_probe()

    def test_train_test_unknown_and_limited_normal_not_scored(self):
        for cards in (['0'], ['4'], ['missing']):
            with self.assertRaisesRegex(ValueError, 'val'): self.run_probe(cards=cards)
        with self.assertRaisesRegex(ValueError, 'history'): self.run_probe(history=[])
        annotation = self.rows[2]['side_annotations']['front']
        annotation.update(visibility_issues=['glare'], glare_areas=['center'])
        self.write()
        with self.assertRaisesRegex(ValueError, 'observable'): self.run_probe()
        self.assertFalse((self.root/'probe.json').exists())

    def test_nonfinite_output_does_not_save_report(self):
        self.meta['head']['bias'].fill_(float('nan')); torch.save(self.meta, self.checkpoint)
        with self.assertRaisesRegex(ValueError, 'Non-finite'): self.run_probe()
        self.assertFalse((self.root/'probe.json').exists())

    def test_changed_photos_do_not_save_report(self):
        from card_condition.point_probe import probe_model
        for name in ('2-front.png', '0-front.png'):
            with self.subTest(photo=name):
                photo = self.root/name
                original = photo.read_bytes()
                def mutate(checkpoint, rows, previous):
                    result = probe_model(checkpoint, rows, previous)
                    photo.write_bytes(original+b'changed')
                    return result
                try:
                    with patch('card_condition.point_probe.probe_model', side_effect=mutate):
                        with self.assertRaisesRegex(ValueError, 'inputs changed'):
                            self.run_probe()
                    self.assertFalse((self.root/'probe.json').exists())
                finally:
                    photo.write_bytes(original)
                    (self.root/'probe.json').unlink(missing_ok=True)

    def test_invalid_provenance_rejected_before_model_creation(self):
        for key in ('development_ids', 'development_groups', 'development_image_hashes'):
            values = [[], [''], ['  '], [None], 'invalid']
            if key == 'development_image_hashes':
                values += [['short'], ['g'*64]]
            for value in values:
                with self.subTest(key=key, value=value):
                    torch.save(dict(self.meta, **{key: value}), self.checkpoint)
                    with patch('card_condition.point_probe.backbone_for') as create:
                        with self.assertRaisesRegex(ValueError, 'provenance|metadata'):
                            load_probe_model(self.checkpoint)
                        create.assert_not_called()

    def test_unsupported_truth_is_not_a_scored_probe(self):
        torch.save(dict(self.meta, supported=['edge_defect']), self.checkpoint)
        with self.assertRaisesRegex(ValueError, 'No scored supported'):
            self.run_probe()
        self.assertFalse((self.root/'probe.json').exists())

    def test_copied_pixels_cannot_count_as_two_new_cards(self):
        with Image.open(self.root/'2-front.png') as image:
            image.save(self.root/'3-front.png', compress_level=0)
        self.assertNotEqual((self.root/'2-front.png').read_bytes(),
                            (self.root/'3-front.png').read_bytes())
        with self.assertRaisesRegex(ValueError, 'different physical groups'):
            self.run_probe()
        self.assertFalse((self.root/'probe.json').exists())

    def test_same_physical_group_is_kept_together(self):
        self.rows[3]['group'] = self.rows[2]['group']
        self.write()
        result = self.run_probe()
        self.assertEqual(1, result['groups'])
        self.assertEqual(2, result['regions'])

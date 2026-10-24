"""Development-history contamination is refused before any analyzer is built; mock analyzers only."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image, ImageOps
import torch
from card_condition import region_evaluation, side_evaluation
from test_evaluation_inputs import evaluate, evaluation_fixture

KINDS = (('region', region_evaluation, 'RegionAnalyzer', 'appear in test'),
         ('side', side_evaluation, 'SideAnalyzer', '평가 자료'))


def decoded(path):
    """Independent decoded-pixel identity (size plus RGB bytes), as load_manifest defines it."""
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()


class ProvenanceContractTest(unittest.TestCase):
    def refuse(self, meta=None, history=None):
        """Alter the checkpoint metadata (field, attribute, test row index) or the history card, expect refusal.

        history is (id_of, group_of, pixels_of): each None or the index of the test row whose
        id / group / re-encoded front photo the otherwise unrelated history card takes over.
        """
        for kind, module, constructor, message in KINDS:
            with self.subTest(kind=kind, meta=meta, history=history), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history_path, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                if meta:
                    field, attribute, index = meta
                    value = decoded(rows[index]['front']) if attribute == 'decoded' else rows[index][attribute]
                    saved = torch.load(checkpoint, weights_only=True)
                    saved[field] = saved[field] + [value]
                    saved['training_groups'] = saved['training_groups'] + ([value] if field == 'development_groups' else [])
                    torch.save(saved, checkpoint)
                if history:
                    id_of, group_of, pixels_of = history
                    old = copy.deepcopy(rows[0]); old.update(id='old-card', group='old-group')
                    old['id'] = rows[id_of]['id'] if id_of is not None else old['id']
                    old['group'] = rows[group_of]['group'] if group_of is not None else old['group']
                    if pixels_of is not None:
                        Image.open(rows[pixels_of]['front']).save(root / 'copy.bmp')
                        old['front'] = str(root / 'copy.bmp')
                    history_path.write_text(json.dumps(old))
                with patch.object(module, constructor, return_value=analyzer) as loader:
                    with self.assertRaisesRegex(ValueError, message):
                        evaluate(kind, module, manifest, history_path, checkpoint, root / 'out.json')
                    loader.assert_not_called()
                analyzer.analyze.assert_not_called(); analyzer.predict.assert_not_called()
                self.assertFalse((root / 'out.json').exists())

    def test_checkpoint_metadata_overlap_by_id_group_or_decoded_pixels(self):
        self.refuse(meta=('development_ids', 'id', 4))
        self.refuse(meta=('development_groups', 'group', 4))
        self.refuse(meta=('development_image_hashes', 'decoded', 4))

    def test_history_overlap_by_id_group_or_pixels_under_another_identity(self):
        self.refuse(history=(4, None, None))
        self.refuse(history=(None, 4, None))
        # A re-encoded (different bytes) copy of a test photo under a new id and group is still the same image.
        self.refuse(history=(None, None, 4))

    def test_final_requires_history_and_valid_development_metadata(self):
        for kind, module, constructor, _ in KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                saved = torch.load(checkpoint, weights_only=True)
                with patch.object(module, constructor, return_value=analyzer) as loader:
                    with self.assertRaisesRegex(ValueError, '--history'):
                        if kind == 'region':
                            module.evaluate_regions(manifest, checkpoint, root / 'a.json', [], 'cpu')
                        else:
                            module.evaluate_sides(manifest, checkpoint, root / 'a.json', 'final', (), 'cpu')
                    for field, value in (('development_ids', []), ('development_ids', 'x'), ('development_ids', ['', 'a']),
                                         ('development_image_hashes', ['G' * 64]), ('development_image_hashes', ['a' * 63]),
                                         ('development_image_hashes', None), ('development_groups', [' '])):
                        broken = dict(saved, **{field: value})
                        if field == 'development_groups':
                            broken['training_groups'] = value
                        torch.save(broken, checkpoint)
                        with self.assertRaisesRegex(ValueError, 'development provenance'):
                            evaluate(kind, module, manifest, history, checkpoint, root / 'b.json')
                    loader.assert_not_called()
                self.assertEqual([], [p.name for p in root.glob('?.json')])

    def test_mixed_split_manifest_is_refused_before_the_analyzer(self):
        for kind, module, constructor, _ in KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                manifest.write_text('\n'.join(json.dumps(r) for r in rows[3:]))
                with patch.object(module, constructor, return_value=analyzer) as loader:
                    with self.assertRaisesRegex(ValueError, 'test'):
                        evaluate(kind, module, manifest, history, checkpoint, root / 'out.json')
                    loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()

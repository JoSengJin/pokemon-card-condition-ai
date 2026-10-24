"""What is read must be what is recorded: inputs changed between reading stages; mock analyzers only."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
import torch
from card_condition import region_evaluation, side_evaluation
from test_evaluation_inputs import evaluate, evaluation_fixture

KINDS = (('region', region_evaluation, 'RegionAnalyzer'), ('side', side_evaluation, 'SideAnalyzer'))


class Rewrite:
    """Stand-in for a loader: first replaces one input file with other bytes, then runs the real loader."""

    def __init__(self, path, data, real):
        self.path, self.data, self.real = Path(path), data, real

    def __call__(self, *args, **kwargs):
        self.path.write_bytes(self.data)
        return self.real(*args, **kwargs)


class ConsistencyContractTest(unittest.TestCase):
    def evaluation(self, kind, module, constructor, target, patched, data):
        """Run one evaluation whose `target` input is rewritten right before `patched` runs; return (error, loader)."""
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
            path = {'photo': Path(rows[4]['front']), 'manifest': manifest, 'history': history, 'checkpoint': checkpoint}[target]
            if data == 'bytes':
                data = path.read_bytes() + b' '
            elif data == 'photo':
                buffer = io.BytesIO(); Image.new('RGB', (90, 130), (1, 2, 3)).save(buffer, 'PNG'); data = buffer.getvalue()
            elif data == 'checkpoint':
                buffer = io.BytesIO(); torch.save(dict(torch.load(checkpoint, weights_only=True), note='b'), buffer); data = buffer.getvalue()
            owner, name = (module.torch, 'load') if patched == 'torch.load' else (module, patched)
            with patch.object(owner, name, Rewrite(path, data, getattr(owner, name))), \
                    patch.object(module, constructor, return_value=analyzer) as loader:
                try:
                    evaluate(kind, module, manifest, history, checkpoint, root / 'out.json')
                    error = None
                except ValueError as raised:
                    error = raised
            return error, loader, (root / 'out.json').exists()

    def test_inputs_changed_after_the_first_hash_but_before_being_read_never_save(self):
        for kind, module, constructor in KINDS:
            for target, patched, data in (('manifest', 'load_manifest', 'bytes'), ('history', 'load_manifest', 'bytes'),
                                          ('checkpoint', 'torch.load', 'checkpoint')):
                with self.subTest(kind=kind, target=target):
                    error, loader, saved = self.evaluation(kind, module, constructor, target, patched, data)
                    self.assertRegex(str(error), 'inputs changed')
                    self.assertFalse(saved)

    def test_photo_changed_between_decoding_and_hash_recording_is_not_recorded_as_read(self):
        # The manifest loader decoded the original photo (identity checks use those pixels); the byte SHA
        # recorded afterwards belongs to the replacement. A report must not join the two.
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind):
                error, loader, saved = self.evaluation(kind, module, constructor, 'photo', 'track_photos', 'photo')
                self.assertRegex(str(error), 'changed')
                self.assertFalse(saved)

    def test_analyzer_that_read_another_checkpoint_than_the_recorded_one_is_refused(self):
        for kind, module, constructor in KINDS:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                analyzer.model_sha256 = 'f' * 64
                with patch.object(module, constructor, return_value=analyzer):
                    with self.assertRaisesRegex(ValueError, 'checkpoint'):
                        evaluate(kind, module, manifest, history, checkpoint, root / 'out.json')
                self.assertFalse((root / 'out.json').exists())


if __name__ == '__main__':
    unittest.main()

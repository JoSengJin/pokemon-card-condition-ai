"""Photo identity: decoded pixels decide duplication, file bytes only guard against change; mock analyzers only."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from test_evaluation_inputs import evaluate, evaluation_fixture
from test_evaluation_provenance_contract import KINDS, decoded


def swap(row, side, path):
    """Point one photo of a card at a new file, keeping the side annotation's image in step."""
    row[side] = row['side_annotations'][side]['image'] = str(path)


class IdentityContractTest(unittest.TestCase):
    def run_kind(self, change):
        """Optionally apply change(root, rows) to the test cards of each evaluator; yield each evaluation outcome."""
        for kind, module, constructor, _ in KINDS:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder).resolve()
                manifest, history, checkpoint, rows, analyzer = evaluation_fixture(root, kind)
                if change:
                    change(root, rows)
                manifest.write_text('\n'.join(json.dumps(r) for r in rows[4:]))
                with patch.object(module, constructor, return_value=analyzer) as loader:
                    try:
                        outcome = evaluate(kind, module, manifest, history, checkpoint, root / 'out.json')
                    except ValueError as error:
                        outcome = error
                yield kind, outcome, rows, loader

    def test_copied_pixels_under_two_groups_are_refused_even_when_reencoded(self):
        def copy_photo(root, rows):
            Image.open(rows[4]['front']).save(root / 'again.bmp')
            swap(rows[5], 'front', root / 'again.bmp')
        seen = []
        for kind, outcome, rows, loader in self.run_kind(copy_photo):
            seen.append(kind)
            self.assertIsInstance(outcome, ValueError, kind)
            self.assertRegex(str(outcome), 'different physical groups')
            self.assertEqual(decoded(rows[4]['front']), decoded(rows[5]['front']))
            self.assertNotEqual(Path(rows[4]['front']).read_bytes(), Path(rows[5]['front']).read_bytes())
            loader.assert_not_called()
        self.assertEqual(['region', 'side'], seen)

    def test_same_card_may_reuse_pixels_and_byte_hashes_stay_distinct(self):
        def reuse(root, rows):
            Image.open(rows[4]['front']).save(root / 'back.bmp')
            swap(rows[4], 'back', root / 'back.bmp')
        for kind, outcome, rows, loader in self.run_kind(reuse):
            self.assertIsInstance(outcome, dict, (kind, outcome))
            loader.assert_called_once()
            front, back = rows[4]['front'], rows[4]['back']
            self.assertEqual(decoded(front), decoded(back))
            hashes = outcome['input_hashes']
            self.assertEqual(hashlib.sha256(Path(back).read_bytes()).hexdigest(), hashes[back])
            self.assertNotEqual(hashes[front], hashes[back])
            self.assertNotIn(decoded(front), hashes.values())

    def test_distinct_groups_with_distinct_pixels_are_not_excluded(self):
        for kind, outcome, rows, loader in self.run_kind(None):
            self.assertIsInstance(outcome, dict, (kind, outcome))
            self.assertEqual((2, False, 0), (outcome['n_cards'], outcome['production_ready'], outcome['actual_calls_saved']))
            self.assertEqual(4, outcome['rates_at_05']['corner_defect']['scored'])


if __name__ == '__main__':
    unittest.main()

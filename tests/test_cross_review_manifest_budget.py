"""Source-reference compression must retain every file integrity check."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path

from card_condition.cross_review_auto_sources import verify_sources
from card_condition.cross_review_evidence_manifest import compact_manifest, expand_manifest
from card_condition.cross_review_manual import review_identity


class ManifestBudgetTest(unittest.TestCase):
    def test_references_round_trip_and_changed_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / 'first.json'; first.write_text('one')
            second = root / 'second.json'; second.write_text('two')
            manifest = [{'path': file.name, 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
                        for file in (first, second)]
            evidence = {'latest_result': dict(manifest[0], summary={'fn': 2})}
            packet = {'evidence': evidence, 'latest_sources': compact_manifest(manifest, evidence)}
            self.assertEqual(packet['latest_sources'][0], {'evidence_id': 'latest_result'})
            self.assertEqual(expand_manifest(packet), manifest)
            verify_sources(root, packet)
            first.write_text('changed')
            with self.assertRaisesRegex(ValueError, 'Review evidence changed'):
                verify_sources(root, packet)

    def test_identity_is_stable_across_source_encoding_but_not_hash_change(self):
        source = {'path': 'result.json', 'sha256': 'frozen'}
        packet = {'evidence': {'latest_result': dict(source, summary={'fn': 2})},
                  'latest_sources': [source]}
        compressed = copy.deepcopy(packet)
        compressed['latest_sources'] = compact_manifest(compressed['latest_sources'], compressed['evidence'])
        config = {'model': 'free-model', 'prompt_version': 'same'}
        self.assertEqual(review_identity(packet, config), review_identity(compressed, config))
        compressed['evidence']['latest_result']['sha256'] = 'changed'
        self.assertNotEqual(review_identity(packet, config), review_identity(compressed, config))


if __name__ == '__main__':
    unittest.main()

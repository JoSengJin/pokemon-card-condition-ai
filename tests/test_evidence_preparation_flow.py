"""End to end: snapshot audit -> not_reviewed scaffold -> existing side-evidence validator, via the CLIs."""
import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from card_condition import evidence_snapshot_cli, side_evidence_cli, side_evidence_prepare
from test_evidence_snapshot import Snapshot

INVENTORY = 'sources/artifacts/intake/inventory.json'


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Snapshot(self.temp.name)
        self.out = self.s.folder / 'runs'
        self.out.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def call(self, module, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as stderr:
            return module.main([str(a) for a in argv]), stderr.getvalue()

    def audit(self, name='audit.json'):
        return self.call(evidence_snapshot_cli, '--index', self.s.index, '--evidence-root', self.s.root, '--output', self.out / name)

    def prepare(self, name='sidecar.json'):
        return self.call(side_evidence_prepare, '--inventory', INVENTORY, '--evidence-root', self.s.root,
                         '--rows-pointer', '/latest', '--search-index', 'index.json', '--output', self.out / name)

    def validate(self, sidecar='sidecar.json', name='validation.json'):
        return self.call(side_evidence_cli, '--sidecar', self.out / sidecar, '--evidence-root', self.s.root,
                         '--output', self.out / name)

    def inputs(self):
        return {k: v for k, v in self.s.snapshot().items() if not k.startswith(str(self.out))}

    def test_chain_accepts_and_keeps_every_row_not_reviewed(self):
        before = self.inputs()
        self.assertEqual([0, 0, 0], [self.audit()[0], self.prepare()[0], self.validate()[0]])
        self.assertEqual(before, self.inputs())
        audit = json.loads((self.out / 'audit.json').read_text())
        validation = json.loads((self.out / 'validation.json').read_text())
        self.assertEqual(3, audit['entries_verified'])
        self.assertEqual(({'not_reviewed': 2}, False), (validation['side_basis_counts'], validation['semantic_verification']))
        # The index the scaffold cites is the same file the audit verified.
        self.assertEqual(audit['index']['sha256'], validation['search_scope']['sha256'])

    def test_changed_payload_stops_at_the_audit(self):
        (self.s.root / INVENTORY).write_text('{"latest": []}')
        code, stderr = self.audit()
        self.assertEqual(1, code)
        self.assertIn('rejected: S:', stderr)

    def test_inventory_changed_after_preparation_is_refused_by_the_validator(self):
        self.assertEqual(0, self.prepare()[0])
        path = self.s.root / INVENTORY
        rows = json.loads(path.read_text()); rows['latest'][0]['side'] = 'back'
        path.write_text(json.dumps(rows))
        code, stderr = self.validate()
        self.assertEqual(1, code)
        self.assertIn('rejected: R1:', stderr)

    def test_index_changed_after_preparation_is_refused_by_the_validator(self):
        self.assertEqual(0, self.prepare()[0])
        self.s.write_index(entries=[self.s.entry(n) for n in self.s.payloads], note='rewritten')
        code, stderr = self.validate()
        self.assertEqual(1, code)
        self.assertIn('rejected: R11:', stderr)

    def test_hand_edited_promotions_are_declarations_not_review(self):
        self.assertEqual(0, self.prepare()[0])
        doc = json.loads((self.out / 'sidecar.json').read_text())
        doc['rows'][0]['review']['status'] = 'reviewed'
        doc['rows'][0]['summary']['side_basis'] = 'no_human_statement'
        (self.out / 'empty.json').write_text(json.dumps(doc))
        code, stderr = self.validate('empty.json', 'empty-validation.json')
        self.assertEqual(1, code)
        self.assertIn('rejected: R5:', stderr)
        # A declared statement that cites any real value passes structure and bytes, yet means nothing about the side.
        data = (self.s.root / INVENTORY).read_bytes()
        cite = dict(path=INVENTORY, sha256=hashlib.sha256(data).hexdigest(), row_id=None, pointer='/latest/0/id')
        doc['rows'][0]['evidence'] = [dict(type='human_statement', claim='side', value='front', asserts_side=True,
                                           source=cite, origin=cite)]
        doc['rows'][0]['summary'] = dict(human_side_origins=1, side_basis='human_statement_matches_claim')
        (self.out / 'declared.json').write_text(json.dumps(doc))
        self.assertEqual(0, self.validate('declared.json', 'declared-validation.json')[0])
        report = json.loads((self.out / 'declared-validation.json').read_text())
        self.assertFalse(report['semantic_verification'])


if __name__ == '__main__':
    unittest.main()

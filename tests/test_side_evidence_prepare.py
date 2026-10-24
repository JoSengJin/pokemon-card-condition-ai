"""All not_reviewed sidecar scaffolds and their CLI; synthetic inventories only."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from card_condition import side_evidence_prepare as prepare
from card_condition.side_evidence import check_structure, validate_sidecar
from test_evidence_snapshot import Snapshot, digest

INVENTORY = 'sources/artifacts/intake/inventory.json'


class PrepareTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Snapshot(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def inventory(self, rows, name=INVENTORY):
        (self.s.root / name).write_text(json.dumps(dict(latest=rows)))

    def rejects(self, code, *args):
        with self.assertRaisesRegex(ValueError, f'^{code}:'):
            prepare.prepare_sidecar(*(args or (INVENTORY, self.s.root, '/latest')))

    def test_every_row_is_not_reviewed_and_bound_to_the_inventory(self):
        before = self.s.snapshot()
        doc = prepare.prepare_sidecar(INVENTORY, self.s.root, '/latest', 'index.json')
        self.assertEqual(before, self.s.snapshot())
        self.assertEqual(dict(path=INVENTORY, sha256=digest(self.s.root / INVENTORY), rows_pointer='/latest'), doc['inventory'])
        self.assertEqual(dict(path='index.json', sha256=digest(self.s.index)), doc['search_scope'])
        self.assertEqual(['syn/photo-3', 'syn/photo-1'], [r['row_id'] for r in doc['rows']])
        for row in doc['rows']:
            self.assertEqual((dict(status='not_reviewed'), [], [], False, dict(human_side_origins=0, side_basis='not_reviewed')),
                             (row['review'], row['evidence'], row['missing_sources'], row['searched_no_side_evidence'], row['summary']))
        self.assertEqual([dict(human_side_origins=0, side_basis='not_reviewed')] * 2, check_structure(doc))

    def test_existing_side_and_human_evidence_do_not_promote_rows(self):
        doc = prepare.prepare_sidecar(INVENTORY, self.s.root, '/latest')
        self.assertEqual(['front', 'front'], [r['side_claim'] for r in doc['rows']])
        text = json.dumps(doc)
        for field in ('target', 'box', 'human_evidence', 'synthetic reply', 'user_quote'):
            self.assertNotIn(field, text)
        self.assertNotIn('search_scope', doc)

    def test_absent_or_null_side_becomes_null_claim(self):
        self.inventory([dict(id='syn/a', image_sha256='a'*64), dict(id='syn/b', image_sha256='b'*64, side=None)])
        self.assertEqual([None, None], [r['side_claim'] for r in prepare.prepare_sidecar(INVENTORY, self.s.root, '/latest')['rows']])

    def test_scaffold_passes_the_existing_validator(self):
        doc = prepare.prepare_sidecar(INVENTORY, self.s.root, '/latest', 'index.json')
        path = self.s.folder / 'sidecar.json'; path.write_text(json.dumps(doc))
        report = validate_sidecar(path, self.s.root)
        self.assertEqual({'not_reviewed': 2}, report['side_basis_counts'])
        self.assertFalse(report['semantic_verification'])

    def test_invalid_inventory_rows(self):
        for rows, code in (([dict(id='syn/a', image_sha256='a'*64)] * 2, 'R2'),
                           ([dict(id='syn/a', image_sha256='A'*64)], 'F'), ([dict(id='syn/a')], 'F'),
                           ([dict(id='syn/a', image_sha256='a'*64, side='Front')], 'F'),
                           ([dict(image_sha256='a'*64)], 'F'), ([dict(id='', image_sha256='a'*64)], 'F'),
                           (['syn/a'], 'F'), ([], 'F')):
            self.inventory(rows)
            self.rejects(code)
        (self.s.root / INVENTORY).write_text(json.dumps(dict(latest={'syn/a': {}})))
        self.rejects('F')

    def test_pointer_path_and_format_rules(self):
        self.rejects('R1', INVENTORY, self.s.root, '/absent')
        self.rejects('J', INVENTORY, self.s.root, 'latest')
        self.rejects('J', 'sources/artifacts/intake/rows.jsonl', self.s.root, '')
        self.rejects('J', 'sources/artifacts/intake/REPORT.md', self.s.root, '')
        for path in ('../inventory.json', '/abs/inventory.json', 'sources/./artifacts/intake/inventory.json'):
            self.rejects('P', path, self.s.root, '/latest')
        self.rejects('R1', 'sources/none.json', self.s.root, '/latest')
        self.rejects('R11', INVENTORY, self.s.root, '/latest', 'sources/none.json')
        self.rejects('P', INVENTORY, self.s.root, '/latest', '../index.json')
        (self.s.root / INVENTORY).write_text('{"latest": [], "latest": []}')
        self.rejects('J')

    def test_root_level_list_with_empty_pointer(self):
        (self.s.root / INVENTORY).write_text(json.dumps([dict(id='syn/a', image_sha256='a'*64)]))
        self.assertEqual('', prepare.prepare_sidecar(INVENTORY, self.s.root, '')['inventory']['rows_pointer'])


class PrepareCliTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Snapshot(self.temp.name)
        self.output = self.s.folder / 'sidecar.json'

    def tearDown(self):
        self.temp.cleanup()

    def run_main(self, *extra):
        argv = ['--inventory', INVENTORY, '--evidence-root', str(self.s.root), '--rows-pointer', '/latest',
                '--output', str(self.output), *extra]
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = prepare.main(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_writes_the_api_result(self):
        before = self.s.snapshot()
        code, stdout, stderr = self.run_main('--search-index', 'index.json')
        self.assertEqual((0, 'side-evidence-prepare: wrote 2 not_reviewed rows\n', ''), (code, stdout, stderr))
        self.assertEqual(prepare.prepare_sidecar(INVENTORY, self.s.root, '/latest', 'index.json'), json.loads(self.output.read_text()))
        self.assertEqual(before, {k: v for k, v in self.s.snapshot().items() if k != str(self.output)})
        self.assertEqual([], [p.name for p in self.s.folder.iterdir() if p.name.startswith('.sidecar.json.')])

    def test_rejection_usage_and_existing_output(self):
        (self.s.root / INVENTORY).write_text(json.dumps(dict(latest=[])))
        code, _, stderr = self.run_main()
        self.assertEqual(1, code)
        self.assertRegex(stderr, r'^side-evidence-prepare: rejected: F: [^\n]*\n$')
        self.assertFalse(self.output.exists())
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            prepare.main(['--inventory', INVENTORY])
        self.assertEqual(2, raised.exception.code)
        self.output.write_text('keep')
        code, _, stderr = self.run_main()
        self.assertEqual((3, 'keep'), (code, self.output.read_text()))
        self.assertNotIn(str(self.s.folder), stderr)

    def test_missing_root_is_a_file_error(self):
        argv = ['--inventory', INVENTORY, '--evidence-root', str(self.s.folder / 'nowhere'), '--rows-pointer', '/latest',
                '--output', str(self.output)]
        with contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(3, prepare.main(argv))
        self.assertIn('NotADirectoryError', stderr.getvalue())
        self.assertFalse(os.path.lexists(self.output))


if __name__ == '__main__':
    unittest.main()

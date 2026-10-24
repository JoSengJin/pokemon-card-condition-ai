"""Byte-integrity rules of audit_snapshot on synthetic snapshot files."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from card_condition.evidence_snapshot import audit_snapshot


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Snapshot:
    """A synthetic evidence root shaped like the provided snapshot: index.json plus sources/ payloads."""

    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.root = self.folder / 'evidence'
        (self.root / 'sources/artifacts/intake').mkdir(parents=True)
        self.payloads = {
            'sources/artifacts/intake/inventory.json': json.dumps(dict(latest=[
                dict(id='syn/photo-3', image_sha256='3'*64, side='front', target=1, box=[0, 0, 1, 1]),
                dict(id='syn/photo-1', image_sha256='1'*64, side='front', human_evidence=dict(user_quote='synthetic reply'))])),
            'sources/artifacts/intake/rows.jsonl': '{"id": "syn/a", "statement": "synthetic"}\n',
            'sources/artifacts/intake/REPORT.md': '# synthetic report\n',
        }
        for name, content in self.payloads.items():
            (self.root / name).write_text(content)
        self.index = self.root / 'index.json'
        self.write_index()

    def entry(self, name, kind='previous_snapshot'):
        return dict(original_relative_path=name.removeprefix('sources/'), snapshot_path=name,
                    sha256=digest(self.root / name), kind=kind)

    def write_index(self, entries=None, **extra):
        entries = [self.entry(n) for n in self.payloads] if entries is None else entries
        self.index.write_text(json.dumps(dict(dict(task_id='syn-task', missing=[], photos_copied=0), entries=entries, **extra)))

    def snapshot(self):
        return {str(p): digest(p) for p in sorted(self.folder.rglob('*')) if p.is_file() and not p.is_symlink()}


class AuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.s = Snapshot(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rejects(self, code):
        with self.assertRaisesRegex(ValueError, f'^{code}:'):
            audit_snapshot(self.s.index, self.s.root)

    def entries(self):
        return [self.s.entry(n) for n in self.s.payloads]

    def test_valid_snapshot_reports_counts_without_content(self):
        before = self.s.snapshot()
        report = audit_snapshot(self.s.index, self.s.root)
        self.assertEqual(before, self.s.snapshot())
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertEqual((3, 3, digest(self.s.index)), (report['index']['entries'], report['entries_verified'], report['index']['sha256']))
        self.assertEqual({'.json': 1, '.jsonl': 1, '.md': 1}, report['suffixes'])
        self.assertEqual({'previous_snapshot': 3}, report['kinds'])
        self.assertEqual(['photos_copied', 'task_id'], report['ignored_metadata_keys'])
        self.assertEqual(dict(count=0, resolved=False), report['declared_missing'])
        self.assertEqual((True, False, False, False), (report['integrity_only'], report['payload_parsed'],
                         report['semantic_verification'], report['independence_verified']))
        text = json.dumps(report)
        for leaked in ('synthetic reply', 'synthetic report', str(self.s.folder)):
            self.assertNotIn(leaked, text)

    def test_declared_missing_is_reported_separately_not_resolved(self):
        self.s.write_index(entries=self.entries(), missing=['artifacts/absent/human-response.json'])
        report = audit_snapshot(self.s.index, self.s.root)
        self.assertEqual((3, dict(count=1, resolved=False)), (report['entries_verified'], report['declared_missing']))
        self.assertNotIn('absent', json.dumps(report))
        self.s.write_index(entries=self.entries(), missing='none')
        self.rejects('F')

    def test_missing_payload(self):
        os.remove(self.s.root / 'sources/artifacts/intake/REPORT.md')
        self.rejects('M')

    def test_stale_index_or_changed_payload(self):
        entries = self.entries(); entries[0]['sha256'] = 'e'*64
        self.s.write_index(entries=entries)
        self.rejects('S')
        self.s.write_index()
        (self.s.root / 'sources/artifacts/intake/rows.jsonl').write_text('{"id": "syn/a", "statement": "changed"}\n')
        self.rejects('S')

    def test_payload_content_is_hashed_not_parsed(self):
        # Broken JSON passes when its bytes match: this is an integrity check, not format validation.
        (self.s.root / 'sources/artifacts/intake/inventory.json').write_text('{"latest": ')
        self.s.write_index()
        self.assertFalse(audit_snapshot(self.s.index, self.s.root)['payload_parsed'])

    def test_repeated_entries_are_refused_not_collapsed(self):
        entries = self.entries()
        self.s.write_index(entries=entries + [dict(entries[0])])
        self.rejects('D')
        other = dict(entries[1], original_relative_path='artifacts/other/rows.jsonl', snapshot_path=entries[0]['snapshot_path'],
                     sha256=entries[0]['sha256'])
        self.s.write_index(entries=entries + [other])
        self.rejects('D')
        renamed = dict(entries[1], snapshot_path='sources/artifacts/intake/other.jsonl')
        self.s.write_index(entries=entries + [renamed])
        self.rejects('D')

    def test_symlink_hardlink_and_format_aliases(self):
        intake = self.s.root / 'sources/artifacts/intake'
        os.symlink(intake / 'inventory.json', intake / 'alias.json')
        os.symlink(intake / 'inventory.json', intake / 'inventory.jsonl')
        os.link(intake / 'rows.jsonl', intake / 'hard.jsonl')
        for name in ('alias.json', 'inventory.jsonl', 'hard.jsonl'):
            path = f'sources/artifacts/intake/{name}'
            extra = dict(self.s.entry(path), original_relative_path=f'artifacts/copy/{name}')
            self.s.write_index(entries=self.entries() + [extra])
            self.rejects('A')

    def test_index_listed_as_its_own_payload(self):
        os.link(self.s.index, self.s.root / 'sources/index-copy.json')
        for path in ('index.json', 'sources/index-copy.json'):
            entry = dict(original_relative_path='artifacts/index.json', snapshot_path=path, sha256='e'*64, kind='x')
            self.s.write_index(entries=self.entries() + [entry])
            self.rejects('A')

    def test_identical_bytes_in_separate_files_are_allowed_but_not_independent(self):
        intake = self.s.root / 'sources/artifacts/intake'
        (intake / 'copy.md').write_bytes((intake / 'REPORT.md').read_bytes())
        self.s.write_index(entries=self.entries() + [dict(self.s.entry('sources/artifacts/intake/copy.md'),
                                                          original_relative_path='artifacts/other/REPORT.md')])
        self.assertFalse(audit_snapshot(self.s.index, self.s.root)['independence_verified'])

    def test_paths_cannot_leave_the_root(self):
        outside = self.s.folder / 'outside.json'; outside.write_text('{}')
        os.symlink(outside, self.s.root / 'sources/escape.json')
        os.symlink(self.s.folder, self.s.root / 'sources/up')
        for path in ('sources/escape.json', 'sources/up/outside.json'):
            self.s.write_index(entries=self.entries() + [dict(original_relative_path='artifacts/x.json', snapshot_path=path,
                                                              sha256=digest(outside), kind='x')])
            self.rejects('P')
        for field, path in (('snapshot_path', '../outside.json'), ('snapshot_path', str(outside)),
                            ('snapshot_path', 'sources/./x.json'), ('original_relative_path', '/abs/artifacts/x.json'),
                            ('original_relative_path', 'artifacts/../x.json'), ('original_relative_path', 'a\\x.json')):
            entry = dict(original_relative_path='artifacts/x.json', snapshot_path='sources/x.json', sha256='e'*64, kind='x')
            entry[field] = path
            self.s.write_index(entries=self.entries() + [entry])
            self.rejects('P')

    def test_special_files_are_not_read(self):
        (self.s.root / 'sources/folder.json').mkdir()
        os.mkfifo(self.s.root / 'sources/pipe.jsonl')
        for path in ('sources/folder.json', 'sources/pipe.jsonl'):
            self.s.write_index(entries=self.entries() + [dict(original_relative_path='artifacts/x', snapshot_path=path,
                                                              sha256='e'*64, kind='x')])
            self.rejects('P')

    def test_unsupported_payloads_are_refused_before_reading(self):
        # The FIFO would block if opened; refusal by suffix proves no read happens.
        os.mkfifo(self.s.root / 'sources/photo.jpg')
        for path in ('sources/photo.jpg', 'sources/model.pt', 'sources/key.pem', 'sources/noext'):
            self.s.write_index(entries=self.entries() + [dict(original_relative_path='artifacts/x', snapshot_path=path,
                                                              sha256='e'*64, kind='x')])
            self.rejects('U')

    def test_index_format(self):
        for content in ('[]', '{}', '{"entries": []}', '{"entries": {}}', '{"entries": [], "entries": []}', '{"entries": [NaN]}'):
            self.s.index.write_text(content)
            with self.assertRaisesRegex(ValueError, '^(F|J):'):
                audit_snapshot(self.s.index, self.s.root)
        for change in (dict(extra=1), dict(sha256='E'*64), dict(kind=''), dict(kind=None)):
            entry = dict(self.entries()[0], **change)
            self.s.write_index(entries=[entry])
            self.rejects('F')
        entry = self.entries()[0]; del entry['kind']
        self.s.write_index(entries=[entry])
        self.rejects('F')

    def test_missing_index_or_root_are_os_errors(self):
        with self.assertRaises(OSError):
            audit_snapshot(self.s.root / 'none.json', self.s.root)
        with self.assertRaises(OSError):
            audit_snapshot(self.s.index, self.s.folder / 'nowhere')


if __name__ == '__main__':
    unittest.main()

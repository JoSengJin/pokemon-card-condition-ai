"""File, SHA, reference and path rules of validate_sidecar on real synthetic files."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from card_condition.side_evidence import compute_summary, validate_sidecar

PHOTO3, PHOTO4, CORNER = ('3'*64, '4'*64, '5'*64)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Fixture:
    """A small evidence root shaped like the audited cases, with synthetic values only."""

    def __init__(self, folder):
        self.folder = Path(folder).resolve()
        self.root = self.folder / 'evidence'
        (self.root / 'intake').mkdir(parents=True)
        self.write('inventory.json', dict(latest=[
            dict(id='syn/photo-3', image_sha256=PHOTO3, side='front', target=1),
            dict(id='syn/photo-4', image_sha256=PHOTO4),
            dict(id='syn/corner-1', image_sha256=CORNER, side=None, target=0)]))
        self.write('intake/reply.json', dict(statement='synthetic statement naming photo 4 as back',
                                             observations=[dict(id='syn/photo-4')]))
        self.lines('intake/derived.jsonl', [dict(id='syn/photo-4', human_evidence=dict(user_quote='synthetic copy'))])
        self.lines('review.jsonl', [dict(id='syn/review-3', front='photo-3.jpg', back=None)])
        self.write('anchor.json', {'full_back_eligibility': dict(single_card=True), 'a/b': {'~': 'escaped'}})
        self.write('pending.json', dict(human_response='artifacts/absent/human-response.json',
                                        legacy='/data/old/artifacts/absent/legacy.json', count=3))
        self.write('index.json', dict(files=['intake/reply.json']))

    def write(self, name, value):
        (self.root / name).write_text(json.dumps(value))

    def lines(self, name, rows):
        (self.root / name).write_text(''.join(json.dumps(r) + '\n' for r in rows))

    def ref(self, name, pointer, row_id=None):
        return dict(path=name, sha256=digest(self.root / name), row_id=row_id, pointer=pointer)

    def human(self, source=None, value='back'):
        return dict(type='human_statement', claim='side', value=value, asserts_side=True,
                    source=source or self.ref('intake/reply.json', '/statement'),
                    origin=self.ref('intake/reply.json', '/statement'))

    def anchor(self):
        anchor = self.ref('anchor.json', '/full_back_eligibility')
        return dict(type='codex_anchor_eligibility', claim='side', value='back', asserts_side=True, source=anchor, origin=anchor)

    def slot(self):
        slot = self.ref('review.jsonl', '/front', 'syn/review-3')
        return dict(type='review_slot', claim='side', value='front', asserts_side=False, source=slot, origin=slot)

    def missing(self, path='artifacts/absent/human-response.json', pointer='/human_response'):
        return dict(path=path, referenced_by=self.ref('pending.json', pointer))

    def row(self, row_id, image, claim, status='reviewed', evidence=(), missing=(), searched=False):
        row = dict(row_id=row_id, image_sha256=image, side_claim=claim, review=dict(status=status),
                   evidence=list(evidence), missing_sources=list(missing), searched_no_side_evidence=searched)
        row['summary'] = compute_summary(row)
        return row

    def rows(self):
        return [self.row('syn/photo-3', PHOTO3, 'front', evidence=[self.slot()], missing=[self.missing()]),
                self.row('syn/photo-4', PHOTO4, None, evidence=[self.human(), self.anchor()]),
                self.row('syn/corner-1', CORNER, None, status='not_reviewed')]

    def sidecar(self, rows=None, scope=True):
        doc = dict(schema='side_evidence_sidecar/v0.1', rows=rows if rows is not None else self.rows(),
                   inventory=dict(path='inventory.json', sha256=digest(self.root / 'inventory.json'), rows_pointer='/latest'))
        if scope:
            doc['search_scope'] = dict(path='index.json', sha256=digest(self.root / 'index.json'))
        return doc

    def save(self, doc):
        path = self.folder / 'sidecar.json'
        path.write_text(json.dumps(doc))
        return path

    def snapshot(self):
        return {str(p): digest(p) for p in sorted(self.folder.rglob('*')) if p.is_file() and not p.is_symlink()}


class SourcesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.f = Fixture(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def validate(self, doc=None):
        return validate_sidecar(self.f.save(doc or self.f.sidecar()), self.f.root)

    def rejects(self, code, doc=None):
        with self.assertRaisesRegex(ValueError, f'^{code}:'):
            self.validate(doc)

    def edit(self, change):
        doc = self.f.sidecar(); change(doc)
        for row in doc['rows']:
            row['summary'] = compute_summary(row)
        return doc

    def test_a1_valid_sidecar_reports_without_touching_any_file(self):
        doc = self.f.sidecar(); path = self.f.save(doc); before = self.f.snapshot()
        report = validate_sidecar(path, self.f.root)
        self.assertEqual(before, self.f.snapshot())
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertEqual((False, False), (report['semantic_verification'], report['modifies_sources']))
        self.assertEqual((3, 3), (report['inventory']['rows_total'], report['inventory']['rows_described']))
        self.assertEqual(['no_human_statement', 'human_statement_without_claim', 'not_reviewed'],
                         [r['side_basis'] for r in report['rows']])
        self.assertFalse(report['search_scope']['completeness_verified'])
        self.assertNotIn('synthetic statement', json.dumps(report))
        self.assertNotIn(str(self.f.folder), json.dumps(report))

    def test_a2_derived_copy_counts_one_declared_origin(self):
        copy = self.f.ref('intake/derived.jsonl', '/human_evidence/user_quote', 'syn/photo-4')
        report = self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(copy))))
        self.assertEqual(1, report['rows'][1]['human_side_origins'])

    def test_a3_human_statement_and_anchor_coexist(self):
        self.assertEqual(['codex_anchor_eligibility', 'human_statement'], self.validate()['rows'][1]['evidence_types'])

    def test_r1_inventory_version_mismatch(self):
        doc = self.f.sidecar()
        self.f.write('inventory.json', dict(latest=[dict(id='syn/photo-4', image_sha256=PHOTO4)]))
        self.rejects('R1', doc)
        self.rejects('R1', self.edit(lambda d: d['inventory'].update(rows_pointer='/other')))
        os.remove(self.f.root / 'inventory.json')
        self.rejects('R1', doc)

    def test_r2_rows_must_bind_to_the_same_inventory_row(self):
        self.rejects('R2', self.edit(lambda d: d['rows'][1].update(row_id='syn/photo-9')))
        # Another row's image or side must not be attached to this id.
        self.rejects('R2', self.edit(lambda d: d['rows'][1].update(image_sha256=PHOTO3)))
        self.rejects('R2', self.edit(lambda d: d['rows'][0].update(side_claim=None)))
        self.rejects('R2', self.edit(lambda d: d['rows'][1].update(side_claim='back')))
        self.f.write('inventory.json', dict(latest=[dict(id='syn/photo-4', image_sha256=PHOTO4)] * 2))
        self.rejects('R2', self.f.sidecar(rows=[self.f.row('syn/photo-4', PHOTO4, None, searched=True)]))

    def test_inventory_rows_need_ids_and_valid_sides(self):
        self.f.write('inventory.json', dict(latest=[dict(image_sha256=PHOTO4)]))
        self.rejects('F', self.f.sidecar(rows=[self.f.row('syn/photo-4', PHOTO4, None, searched=True)]))
        self.f.write('inventory.json', dict(latest=[dict(id='syn/photo-4', image_sha256=PHOTO4, side='Back')]))
        self.rejects('F', self.f.sidecar(rows=[self.f.row('syn/photo-4', PHOTO4, None, searched=True)]))
        self.f.write('inventory.json', dict(latest={'syn/photo-4': {}}))
        self.rejects('F', self.f.sidecar(rows=[self.f.row('syn/photo-4', PHOTO4, None, searched=True)]))

    def test_partial_sidecar_is_allowed(self):
        report = self.validate(self.f.sidecar(rows=[self.f.row('syn/photo-4', PHOTO4, None, evidence=[self.f.anchor()])]))
        self.assertEqual((3, 1), (report['inventory']['rows_total'], report['inventory']['rows_described']))

    def test_structure_rules_also_hold_end_to_end(self):
        self.rejects('R3', self.edit(lambda d: d['rows'].append(d['rows'][1])))
        self.rejects('R4', self.edit(lambda d: d['rows'][2].update(searched_no_side_evidence=True)))
        self.rejects('R5', self.edit(lambda d: d['rows'][1].update(evidence=[])))
        self.rejects('R6', self.edit(lambda d: d['rows'][1].update(target=1)))
        self.rejects('R7', self.edit(lambda d: d['rows'][0]['evidence'][0].update(asserts_side=True)))
        doc = self.f.sidecar(); doc['rows'][1]['summary']['human_side_origins'] = 2
        self.rejects('R8', doc)
        self.rejects('R12', self.edit(lambda d: d.update(schema='side_evidence_sidecar/v0-draft')))

    def test_r9_source_and_origin_are_both_verified(self):
        def wrong(field, key, value):
            return self.edit(lambda d: d['rows'][1]['evidence'][0][field].update({key: value}))
        self.rejects('R9', wrong('source', 'sha256', 'e'*64))
        # A correct source does not excuse a wrong or missing origin.
        self.rejects('R9', wrong('origin', 'sha256', 'e'*64))
        self.rejects('R9', wrong('origin', 'pointer', '/missing'))
        self.rejects('R9', wrong('origin', 'path', 'intake/gone.json'))
        self.rejects('R9', self.edit(lambda d: d['rows'][0]['evidence'][0]['source'].update(row_id='syn/review-9')))
        self.rejects('R9', self.edit(lambda d: d['rows'][0]['evidence'][0]['source'].update(pointer='/back')))

    def test_pointer_escapes_and_indexes_on_files(self):
        anchor = self.f.ref('anchor.json', '/a~1b/~0')
        item = dict(type='codex_anchor_eligibility', claim='side', value='back', asserts_side=True, source=anchor, origin=anchor)
        self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(item)))
        source = self.f.ref('intake/reply.json', '/observations/0/id')
        self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))
        for pointer in ('/observations/1/id', '/observations/00/id', '/observations/-/id'):
            source = self.f.ref('intake/reply.json', pointer)
            self.rejects('R9', self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))

    def test_r10_missing_sources_must_be_referenced_and_absent(self):
        self.validate(self.edit(lambda d: d['rows'][0]['missing_sources'].append(
            self.f.missing('artifacts/absent/legacy.json', '/legacy'))))
        self.rejects('R10', self.edit(lambda d: d['rows'][0]['missing_sources'].append(self.f.missing('artifacts/other.json'))))
        self.rejects('R10', self.edit(lambda d: d['rows'][0]['missing_sources'].append(self.f.missing('absent/legacy.json', '/human_response'))))
        self.rejects('R10', self.edit(lambda d: d['rows'][0]['missing_sources'].append(self.f.missing('artifacts/absent/x.json', '/count'))))
        self.rejects('R10', self.edit(lambda d: d['rows'][0]['missing_sources'][0]['referenced_by'].update(sha256='e'*64)))
        # A source that exists below the root cannot be declared missing.
        target = self.f.root / 'artifacts/absent/human-response.json'
        target.parent.mkdir(parents=True); target.write_text('{}')
        self.rejects('R10')

    def test_missing_sources_never_count_as_evidence(self):
        report = self.validate(self.f.sidecar(rows=[self.f.row('syn/photo-3', PHOTO3, 'front', missing=[self.f.missing()])]))
        self.assertEqual((0, 'no_human_statement', 1), (report['rows'][0]['human_side_origins'],
                         report['rows'][0]['side_basis'], report['rows'][0]['missing_sources']))
        doc = self.f.sidecar(rows=[self.f.row('syn/photo-3', PHOTO3, 'front', evidence=[self.f.human(
            dict(path='artifacts/absent/human-response.json', sha256='e'*64, row_id=None, pointer='/statement'))],
            missing=[self.f.missing()])])
        self.rejects('R9', doc)

    def test_r11_stale_or_missing_search_index(self):
        doc = self.f.sidecar(rows=[self.f.row('syn/photo-3', PHOTO3, 'front', searched=True)])
        self.validate(doc)
        self.f.write('index.json', dict(files=['intake/reply.json', 'new.json']))
        self.rejects('R11', doc)
        os.remove(self.f.root / 'index.json')
        self.rejects('R11', doc)

    def test_paths_cannot_leave_the_root(self):
        outside = self.f.folder / 'outside.json'; outside.write_text('{"statement": "x"}')
        os.symlink(outside, self.f.root / 'escape.json')
        os.symlink(self.f.folder, self.f.root / 'parent')
        for path in ('escape.json', 'parent/outside.json'):
            source = dict(path=path, sha256=digest(outside), row_id=None, pointer='/statement')
            self.rejects('P', self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))
        for path in ('../outside.json', str(outside)):
            source = dict(path=path, sha256=digest(outside), row_id=None, pointer='/statement')
            self.rejects('P', self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))
        self.rejects('P', self.edit(lambda d: d['rows'][0]['missing_sources'].append(self.f.missing('parent/x.json'))))

    def test_symlink_inside_the_root_is_followed(self):
        os.symlink(self.f.root / 'intake/reply.json', self.f.root / 'alias.json')
        source = self.f.ref('alias.json', '/statement')
        self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))

    def test_special_files_are_not_read(self):
        (self.f.root / 'folder.json').mkdir()
        os.mkfifo(self.f.root / 'pipe.json')
        for path in ('folder.json', 'pipe.json'):
            source = dict(path=path, sha256='e'*64, row_id=None, pointer='/statement')
            self.rejects('P', self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))

    def test_malformed_reference_files(self):
        cases = {'dup.jsonl': '{"id": "syn/a"}\n{"id": "syn/a"}\n', 'noid.jsonl': '{"name": "x"}\n',
                 'bad.json': '{"statement": ', 'keys.json': '{"statement": "a", "statement": "b"}',
                 'nan.json': '{"statement": NaN}'}
        for name, content in cases.items():
            (self.f.root / name).write_text(content)
        (self.f.root / 'latin.json').write_bytes('{"statement": "caf\xe9"}'.encode('latin-1'))
        for name in [*cases, 'latin.json']:
            row_id = 'syn/a' if name.endswith('.jsonl') else None
            source = self.f.ref(name, '/statement', row_id)
            self.rejects('J', self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))

    def test_jsonl_line_separator_inside_string_is_one_row(self):
        self.f.lines('sep.jsonl', [dict(id='syn/a', statement='before after')])
        text = (self.f.root / 'sep.jsonl').read_text()
        (self.f.root / 'sep.jsonl').write_text(text.replace('\\u2028', ' '))
        source = self.f.ref('sep.jsonl', '/statement', 'syn/a')
        self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(self.f.human(source))))

    def test_matching_sha_is_not_semantic_verification(self):
        # Both items are accepted although neither states a side; byte agreement is not meaning.
        unrelated = self.f.ref('pending.json', '/human_response')
        false_origin = dict(self.f.human(unrelated), origin=self.f.ref('anchor.json', '/full_back_eligibility'))
        report = self.validate(self.edit(lambda d: d['rows'][1]['evidence'].append(false_origin)))
        self.assertEqual(2, report['rows'][1]['human_side_origins'])
        self.assertFalse(report['semantic_verification'])

    def test_missing_evidence_root_and_sidecar_are_os_errors(self):
        path = self.f.save(self.f.sidecar())
        with self.assertRaises(OSError):
            validate_sidecar(path, self.f.folder / 'nowhere')
        with self.assertRaises(OSError):
            validate_sidecar(self.f.folder / 'none.json', self.f.root)


if __name__ == '__main__':
    unittest.main()

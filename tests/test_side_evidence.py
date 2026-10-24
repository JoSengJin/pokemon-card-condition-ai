"""Structure and summary rules of the side-evidence sidecar; synthetic dicts only."""
import copy
import unittest
from card_condition.side_evidence import check_structure, compute_summary, parse_pointer, resolve

A, B, C, D = ('a'*64, 'b'*64, 'c'*64, 'd'*64)


def ref(path='reply.json', digest=A, row_id=None, pointer='/statement'):
    return dict(path=path, sha256=digest, row_id=row_id, pointer=pointer)


def evidence(kind='human_statement', value='back', source=None, origin=None):
    return dict(type=kind, claim='side', value=value, asserts_side=kind != 'review_slot',
                source=source or ref(), origin=origin or ref())


def row(row_id='syn/1', claim=None, status='reviewed', items=(), missing=(), searched=False):
    item = dict(row_id=row_id, image_sha256=B, side_claim=claim, review=dict(status=status),
                evidence=list(items), missing_sources=list(missing), searched_no_side_evidence=searched)
    item['summary'] = compute_summary(item)
    return item


def sidecar(*rows, scope=True):
    doc = dict(schema='side_evidence_sidecar/v0.1',
               inventory=dict(path='inventory.json', sha256=C, rows_pointer='/rows'), rows=list(rows))
    if scope:
        doc['search_scope'] = dict(path='index.json', sha256=D)
    return doc


class StructureTest(unittest.TestCase):
    def rejects(self, code, doc):
        with self.assertRaisesRegex(ValueError, f'^{code}:'):
            check_structure(doc)

    def test_mixed_types_are_not_exclusive(self):
        # A3: a human statement and an anchor judgment may describe the same row.
        doc = sidecar(row(items=[evidence(), evidence('codex_anchor_eligibility', origin=ref('anchor.json'))]))
        self.assertEqual([dict(human_side_origins=1, side_basis='human_statement_without_claim')], check_structure(doc))

    def test_derived_copy_keeps_one_declared_origin(self):
        # A2: a copy in another file with the same declared origin is not a second origin.
        copy_source = ref('derived.jsonl', row_id='syn/1', pointer='/human_evidence/user_quote')
        doc = sidecar(row(items=[evidence(), evidence(source=copy_source)]))
        self.assertEqual(1, check_structure(doc)[0]['human_side_origins'])
        doc['rows'][0]['summary']['human_side_origins'] = 2
        self.rejects('R8', doc)

    def test_conflicts_and_disagreement_are_reported_not_resolved(self):
        doc = sidecar(row('syn/1', 'front', items=[evidence(value='back')]),
                      row('syn/2', 'front', items=[evidence(value='front')]),
                      row('syn/3', 'back', items=[evidence(value='back'), evidence(value='front', origin=ref('other.json'))]))
        self.assertEqual(['human_statement_conflicts_claim', 'human_statement_matches_claim', 'human_statements_disagree'],
                         [s['side_basis'] for s in check_structure(doc)])
        self.assertEqual([2], [s['human_side_origins'] for s in check_structure(doc)[2:]])

    def test_slot_and_anchor_are_not_human_statements(self):
        doc = sidecar(row(claim='front', items=[evidence('review_slot', 'front'), evidence('codex_anchor_eligibility')]))
        self.assertEqual(dict(human_side_origins=0, side_basis='no_human_statement'), check_structure(doc)[0])

    def test_not_reviewed_is_separate_from_missing_and_empty_search(self):
        self.assertEqual('not_reviewed', check_structure(sidecar(row(status='not_reviewed')))[0]['side_basis'])
        missing = dict(path='gone.json', referenced_by=ref('pending.json', pointer='/human_response'))
        for change in (dict(items=[evidence()]), dict(missing=[missing]), dict(searched=True)):
            # R4: an uninvestigated row cannot carry findings of any kind.
            self.rejects('R4', sidecar(row(status='not_reviewed', **change)))
        self.rejects('R5', sidecar(row()))
        check_structure(sidecar(row(missing=[missing])))
        check_structure(sidecar(row(searched=True)))

    def test_empty_search_needs_scope_and_no_asserting_evidence(self):
        self.rejects('S2', sidecar(row(searched=True), scope=False))
        self.rejects('S1', sidecar(row(searched=True, items=[evidence()])))
        check_structure(sidecar(row(searched=True, items=[evidence('review_slot', 'front')])))

    def test_duplicate_rows_rejected(self):
        self.rejects('R3', sidecar(row(searched=True), row(searched=True)))

    def test_truth_and_non_side_claims_rejected(self):
        # R6: the sidecar never carries or changes defect truth, points, boxes or sides.
        for field in ('side', 'target', 'box', 'point', 'labels'):
            item = row(searched=True); item[field] = 1
            self.rejects('R6', sidecar(item))
        for claim in ('target', 'point', 'region', 'model_eval'):
            item = evidence(); item['claim'] = claim
            self.rejects('R6', sidecar(row(items=[item])))

    def test_review_slot_cannot_assert_side(self):
        item = evidence('review_slot', 'front'); item['asserts_side'] = True
        self.rejects('R7', sidecar(row(items=[item])))
        item = evidence(); item['asserts_side'] = False
        self.rejects('F', sidecar(row(items=[item])))

    def test_unsupported_schema_type_status_and_basis(self):
        draft = sidecar(row(searched=True)); draft['schema'] = 'side_evidence_sidecar/v0-draft'
        self.rejects('R12', draft)
        for kind in ('missing_source', ['human_statement'], None):
            item = evidence(); item['type'] = kind
            self.rejects('R12', sidecar(row(items=[item])))
        item = row(searched=True); item['review']['status'] = 'skipped'
        self.rejects('R12', sidecar(item))
        item = row(searched=True); item['summary']['side_basis'] = 'confirmed'
        self.rejects('R12', sidecar(item))

    def test_strict_types_do_not_confuse_bool_and_int(self):
        item = row(items=[evidence()]); item['summary']['human_side_origins'] = True
        self.rejects('F', sidecar(item))
        item = evidence(); item['asserts_side'] = 1
        self.rejects('F', sidecar(row(items=[item])))
        item = row(searched=True); item['searched_no_side_evidence'] = 1
        self.rejects('F', sidecar(item))

    def test_null_empty_and_bad_values(self):
        for field, value in (('row_id', ''), ('row_id', None), ('side_claim', 'Front'), ('image_sha256', 'A'*64),
                             ('evidence', None), ('missing_sources', {})):
            item = row(searched=True); item[field] = value
            self.rejects('F', sidecar(item))
        for value in (None, 'unknown', ''):
            item = evidence(); item['value'] = value
            self.rejects('F', sidecar(row(items=[item])))
        self.rejects('F', sidecar())

    def test_unknown_keys_rejected(self):
        item = row(searched=True); item['decoded_sha256'] = B
        self.rejects('F', sidecar(item))
        item = evidence(); item['source']['decoded_sha256'] = B
        self.rejects('F', sidecar(row(items=[item])))

    def test_reference_forms(self):
        self.rejects('J', sidecar(row(items=[evidence(source=ref('notes.md'))])))
        self.rejects('J', sidecar(row(items=[evidence(source=ref('rows.jsonl'))])))
        self.rejects('J', sidecar(row(items=[evidence(source=ref(row_id='syn/1'))])))
        self.rejects('J', sidecar(row(items=[evidence(origin=ref(pointer=''))])))
        for path in ('/abs/reply.json', '../reply.json', 'a/../reply.json', 'a\\reply.json', ''):
            self.rejects('P', sidecar(row(items=[evidence(source=ref(path))])))

    def test_json_pointer_tokens(self):
        self.assertEqual([], parse_pointer(''))
        self.assertEqual(['a/b', 'm~n', '0'], parse_pointer('/a~1b/m~0n/0'))
        self.assertEqual(['~1'], parse_pointer('/~01'))
        for bad in ('a', '/x~', '/x~2', '/~'):
            with self.assertRaisesRegex(ValueError, '^J:'):
                parse_pointer(bad)
        document = {'a/b': [10, {'m~n': 'v'}], '': 'blank'}
        self.assertEqual('v', resolve(document, parse_pointer('/a~1b/1/m~0n')))
        self.assertEqual('blank', resolve(document, parse_pointer('/')))
        self.assertIs(document, resolve(document, parse_pointer('')))
        for bad in ('/a~1b/2', '/a~1b/01', '/a~1b/-', '/a~1b/0/x', '/missing'):
            with self.assertRaises(LookupError):
                resolve(document, parse_pointer(bad))

    def test_structure_check_does_not_modify_input(self):
        doc = sidecar(row(items=[evidence()]), row('syn/2', status='not_reviewed'))
        before = copy.deepcopy(doc)
        check_structure(doc)
        self.assertEqual(before, doc)


if __name__ == '__main__':
    unittest.main()

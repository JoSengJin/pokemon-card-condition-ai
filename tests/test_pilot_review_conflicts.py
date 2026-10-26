import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout,redirect_stderr
from unittest.mock import patch
from card_condition.pilot_summary import summarize
from test_pilot_summary import entry,write


def review(root,name='review.json',**changes):
    record=dict(report_sha256='sha-0',review_completed=True,counts=dict(confirmed=40,corrected_defect=2,corrected_normal=0,undecidable=0))
    record.update(changes)
    path=root/name
    path.write_text(json.dumps(record))
    return path


class PilotReviewConflictsTest(unittest.TestCase):
    def test_identical_completed_reviews_count_once(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            a,b=review(root),review(root,'copy.json')
            result=summarize(log,[a,b,a])
            self.assertEqual(dict(reviewed_requests=1,requests_corrected=1,corrected_cells=2),result['releases'][0]['human_review'])
            self.assertEqual(0,result['unmatched_review_records'])
            self.assertFalse(result['pilot_certified'])

    def test_conflicting_completed_counts_rejected_in_both_orders(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            a=review(root)
            b=review(root,'different.json',counts=dict(confirmed=42,corrected_defect=0,corrected_normal=0,undecidable=0))
            for paths in ([a,b],[b,a]):
                with self.subTest(paths=paths),self.assertRaisesRegex(ValueError,'Conflicting completed reviews'):
                    summarize(log,paths)
            # Even matching correction totals do not establish identical completed counts.
            b=review(root,'same-total.json',counts=dict(confirmed=39,corrected_defect=2,corrected_normal=0,undecidable=1))
            with self.assertRaisesRegex(ValueError,'Conflicting completed reviews'):
                summarize(log,[a,b])

    def test_incomplete_review_cannot_override_completed_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            a=review(root);b=review(root,'draft.json',review_completed=False,counts=dict(corrected_defect=0,corrected_normal=0))
            for paths in ([a,b],[b,a]):
                result=summarize(log,paths)
                self.assertEqual(1,result['incomplete_review_records'])
                self.assertEqual(2,result['releases'][0]['human_review']['corrected_cells'])

    def test_invalid_counts_or_missing_correction_truth_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            for counts in [dict(corrected_defect=v,corrected_normal=0) for v in (-1,True,1.5,'2',None)]+[{},dict(corrected_defect=0),dict(corrected_defect=0,corrected_normal=0,confirmed=-1)]:
                with self.subTest(counts=counts),self.assertRaisesRegex(ValueError,'non-negative integer counts'):
                    summarize(log,[review(root,counts=counts)])

    def test_invalid_record_identity_or_completion_flag_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            for changes in [dict(report_sha256=v) for v in ('',' ',None,1)]+[dict(review_completed=v) for v in (1,None,'true')]:
                with self.subTest(changes=changes),self.assertRaisesRegex(ValueError,'listing review record'):
                    summarize(log,[review(root,**changes)])
            path=root/'array.json';path.write_text('[]')
            with self.assertRaisesRegex(ValueError,'listing review record'):
                summarize(log,[path])

    def test_cli_rejects_conflict_without_numeric_success_output(self):
        from card_condition.cli import main
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);log=write(root,[entry(0)])
            a=review(root);b=review(root,'different.json',counts=dict(corrected_defect=0,corrected_normal=0))
            out,err=io.StringIO(),io.StringIO()
            with patch('sys.argv',['card-condition','pilot-summary',str(log),'--reviews',str(a),str(b)]),redirect_stdout(out),redirect_stderr(err),self.assertRaises(SystemExit) as caught:
                main()
            self.assertEqual(1,caught.exception.code)
            self.assertEqual('',out.getvalue())
            self.assertIn('Conflicting completed reviews',err.getvalue())

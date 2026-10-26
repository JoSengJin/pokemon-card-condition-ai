import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from card_condition.evaluation_suite_inputs import matched_reports
from card_condition.evaluation_suite import assess_suite
from test_evaluation_suite import saved_suite


class FrozenReportLoadedBytesTest(unittest.TestCase):
    def test_pinned_report_uses_the_hashed_snapshot_instead_of_reopened_text(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();args,reports=saved_suite(root,2)
            manifest,seal,seal_sha,candidate,candidate_sha=args
            path=Path(reports['region_final']['path']);original=json.loads(path.read_bytes())
            read=Path.read_text
            def swapped(path_arg,*a,**kw):
                return json.dumps(dict(original,race_marker='alternate bytes')) if path_arg==path else read(path_arg,*a,**kw)
            with patch.object(Path,'read_text',swapped):
                found=matched_reports(candidate,candidate_sha,seal,seal_sha,manifest,reports)[2]
            self.assertEqual(original,found['region_final'])
            self.assertNotIn('race_marker',found['region_final'])

    def test_candidate_reports_and_receipts_are_never_reopened_as_text(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();args,reports=saved_suite(root,2)
            targets={Path(args[3]),*(Path(r['path']) for r in reports.values())}
            targets.update(Path(json.loads(Path(r['path']).read_bytes())['test_seal']['receipt']) for r in reports.values())
            read=Path.read_text
            def forbidden_reopen(path,*a,**kw):
                if path in targets:
                    raise AssertionError('Pinned JSON must be parsed from the hashed snapshot')
                return read(path,*a,**kw)
            with patch.object(Path,'read_text',forbidden_reopen):
                result=assess_suite(*args,reports,root/'assessment.json')
            self.assertEqual([],result['missing_roles'])
            self.assertFalse(result['production_ready'])

    def test_changed_report_bytes_are_rejected_without_writing_assessment(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d).resolve();args,reports=saved_suite(root,2)
            path=Path(reports['region_final']['path']);path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaisesRegex(ValueError,'report SHA256 mismatch'):
                assess_suite(*args,reports,root/'assessment.json')
            self.assertFalse((root/'assessment.json').exists())

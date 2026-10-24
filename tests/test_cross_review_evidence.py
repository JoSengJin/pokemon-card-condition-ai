import json
import os
from pathlib import Path
import tempfile
import unittest

from card_condition.cross_review_evidence import latest_packet
from card_condition.regression_audit import compare_predictions


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.code = self.root / 'card_condition/model.py'
        self.code.parent.mkdir()
        self.code.write_text('def inference(logits):\n    return max(logits)\n')
        self.rows = [dict(id=str(i), target=t, group=str(i), image_sha256=str(i), box=[0,0,1,1], fold=i)
                     for i,t in enumerate([1,0,0])]

    def result(self, name, before=None, after=None, rows=None):
        folder = self.root / 'artifacts' / name
        folder.mkdir(parents=True)
        rows = rows or self.rows
        before = before or [.9,.8,.9]
        after = after or [.9,.8,.9]
        (folder / 'result.json').write_text(json.dumps(dict(rows=rows, before_scores=before, scores=after,
            comparison=compare_predictions([r['target'] for r in rows],before,after), independent=False)))
        (folder / 'plan.json').write_text(json.dumps({'hypothesis':'test', 'tracked_sha256':{str(self.code):'historical'}}))
        return folder

    def test_latest_by_experiment_date_not_just_mtime(self):
        old = self.result('old-20261018')
        new = self.result('new-20261019')
        os.utime(old / 'result.json', (2000000000, 2000000000))
        packet = latest_packet(self.root)
        self.assertIn(new.name, packet['latest_result'])
        self.assertEqual(packet['error_count'], 2)
        self.assertEqual(packet['source_mode'], 'project-latest')
        self.assertIn('related_code', packet['evidence'])

    def test_training_diagnostics_are_carried_as_separate_provenance_evidence(self):
        folder=self.result('new-20261019')
        details={'version':1,'folds':[{'status':'recorded','independently_verified':False,'optimizers':[{'iterations':12,'max_gradient':1e-8,'converged':True}]}]}
        (folder/'training-diagnostics.json').write_text(json.dumps(details))
        packet=latest_packet(self.root)
        item=packet['evidence']['latest_training_diagnostics']
        self.assertEqual(item['summary'],details)
        self.assertTrue(item['sha256'])
        self.assertEqual(packet['same_evaluation_metrics']['latest_experiment']['after']['fp'],2)

    def test_actual_new_improvement_and_followup_stagnation_are_separate(self):
        folder = self.result('new-20261019', after=[.9,.2,.8])
        comparison = compare_predictions([1,0,0],[.9,.2,.8],[.9,.1,.8])
        (folder / 'geometry-diagnostic.json').write_text(json.dumps(dict(scores=[.9,.1,.8],
            comparison=comparison, eligible_rows=1, positive_rows_with_approved_geometry=0)))
        packet = latest_packet(self.root)
        self.assertEqual(packet['same_evaluation_metrics']['latest_experiment']['before']['fp'], 2)
        self.assertEqual(packet['same_evaluation_metrics']['latest_experiment']['after']['fp'], 1)
        self.assertEqual(packet['same_evaluation_metrics']['latest_followup']['after']['fp'], 1)
        self.assertEqual([r['id'] for r in packet['error_cases']], ['2'])
        self.assertIn('new-20261019/geometry', packet['failed_hypotheses'])

    def test_history_with_changed_truth_is_not_compared(self):
        changed = [dict(r) for r in self.rows]
        changed[1]['target'] = 1
        self.result('old-20261018', rows=changed)
        self.result('new-20261019')
        packet = latest_packet(self.root)
        self.assertNotIn('old-20261018', packet['failed_hypotheses'])

    def test_bad_latest_metrics_fail_instead_of_using_stale_example(self):
        self.result('old-20261018')
        folder = self.result('new-20261019')
        path=folder/'result.json';result=json.loads(path.read_text());result['comparison']['after']['fp']=0
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError,'Saved experiment metrics'):
            latest_packet(self.root)

    def test_no_stagnation_does_not_trigger_review(self):
        self.result('new-20261019',after=[.9,.1,.1])
        with self.assertRaisesRegex(ValueError,'정체 근거'):
            latest_packet(self.root)

    def test_missing_source_never_falls_back_to_example(self):
        with self.assertRaisesRegex(ValueError,'예제 자료로 대체하지'):
            latest_packet(self.root)

    def test_foreign_project_code_never_enters_packet(self):
        folder=self.result('new-20261019')
        (folder/'plan.json').write_text(json.dumps({'tracked_sha256':{'/other-project/secrets.py':'hash'}}))
        with self.assertRaisesRegex(ValueError,'관련 프로젝트 코드'):
            latest_packet(self.root)

    def test_invalid_old_history_is_excluded_without_blocking_valid_latest(self):
        folder = self.result('old-20261018')
        path = folder/'result.json'
        result = json.loads(path.read_text())
        result['comparison']['after']['fp'] = 0
        path.write_text(json.dumps(result))
        self.result('new-20261019')
        packet = latest_packet(self.root)
        self.assertIn('new-20261019', packet['latest_result'])
        self.assertNotIn('old-20261018', packet['failed_hypotheses'])

    def test_missing_photo_identity_blocks_evidence(self):
        rows = [dict(r) for r in self.rows]
        rows[0].pop('image_sha256')
        self.result('new-20261019', rows=rows)
        with self.assertRaisesRegex(ValueError, 'identity'):
            latest_packet(self.root)

    def test_different_threshold_blocks_automatic_packet(self):
        folder = self.result('new-20261019')
        plan = json.loads((folder/'plan.json').read_text())
        plan['threshold'] = .7
        (folder/'plan.json').write_text(json.dumps(plan))
        with self.assertRaisesRegex(ValueError, 'threshold'):
            latest_packet(self.root)

    def test_failed_conditions_and_actual_point_reason_are_kept(self):
        folder=self.result('failed-20261019')
        plan=json.loads((folder/'plan.json').read_text())
        plan.update(hypothesis_id='same-smoothing',change='0.5 center + 0.125 each neighbor',acceptance={'max_fp':2,'require_actual_point_guard':True})
        (folder/'plan.json').write_text(json.dumps(plan))
        result=json.loads((folder/'result.json').read_text())
        result['point_comparison']={'before':{'fn':0},'after':{'fn':1},'new_misses':['p']}
        (folder/'result.json').write_text(json.dumps(result))
        packet=latest_packet(self.root);summary=packet['evidence']['failed_0']['summary']
        self.assertEqual(summary['conditions']['change'],plan['change'])
        self.assertEqual(summary['conditions']['acceptance'],plan['acceptance'])
        self.assertIn('actual_point_miss',summary['failure_reasons'])
        self.assertEqual(summary['point_comparison']['after']['fn'],1)

    def test_same_sources_stop_and_new_measurements_reopen_freshness(self):
        folder=self.result('old-20261019');packet=latest_packet(self.root)
        history=self.root/'artifacts/manual-cross-review/previous';history.mkdir(parents=True)
        (history/'result.json').write_text(json.dumps(dict(packet=packet,response={'cause':'stored'},attempts=[{'status':'complete'}],deadline=1)))
        unchanged=latest_packet(self.root)
        self.assertEqual(unchanged['fresh_evidence_ids'],[])
        self.result('new-20261020')
        updated=latest_packet(self.root)
        self.assertIn('latest_result',updated['fresh_evidence_ids'])
        self.assertNotIn('related_code',updated['fresh_evidence_ids'])

    def test_local_reuse_is_not_a_new_review_baseline(self):
        self.result('old-20261019');packet=latest_packet(self.root)
        history=self.root/'artifacts/manual-cross-review/imported';history.mkdir(parents=True)
        (history/'result.json').write_text(json.dumps(dict(packet=packet,response={'cause':'stored'},attempts=[{'status':'complete'}])))
        (history/'response_reuse.json').write_text('{}')
        self.assertIn('latest_result',latest_packet(self.root)['fresh_evidence_ids'])


class EvidenceBudgetTest(unittest.TestCase):
    def test_only_partial_code_excerpt_is_trimmed(self):
        import copy
        from card_condition.cross_review import encoded
        from card_condition.cross_review_evidence import bound_code_excerpt
        packet=dict(evidence=dict(related_code=dict(path='changes.diff',sha256='source-sha',summary=dict(excerpt='코드\n'*6000)),
            failed_0=dict(conditions='fixed criteria',failure_reasons=['actual_point_miss'])),
            completed_diagnostics={'audit':['completed_diagnostic_0']},failed_hypotheses={'failed':['failed_0']},
            fresh_evidence_ids=['related_code'])
        original=copy.deepcopy(packet)
        result=bound_code_excerpt(packet)
        self.assertLessEqual(len(encoded(result).encode()),23700)
        self.assertEqual(result['evidence']['failed_0'],original['evidence']['failed_0'])
        for key in ('completed_diagnostics','failed_hypotheses','fresh_evidence_ids'):
            self.assertEqual(result[key],original[key])
        self.assertEqual(result['evidence']['related_code']['sha256'],'source-sha')
        self.assertTrue(result['evidence']['related_code']['summary']['budget_truncated'])
        self.assertTrue(original['evidence']['related_code']['summary']['excerpt'].startswith(result['evidence']['related_code']['summary']['excerpt']))

    def test_large_repeated_errors_preserve_metrics_conditions_and_all_cohort_ids(self):
        import copy
        from card_condition.cross_review import encoded
        from card_condition.cross_review_evidence import bound_repeated_errors,compact_evidence,expand_evidence
        from card_condition.regression_audit import compare_predictions
        comparison=compare_predictions([1,0,0],[.9,.1,.8],[.8,.8,.9])
        cohort=dict(id='a',comparison=comparison,point_comparison=None,acceptance_passed=False,
                    acceptance={'max_fn':0,'max_fp':0,'no_new_errors':True,'require_actual_point_guard':False},
                    errors=[dict(id='case-'+str(i),target=0,score=.8,kind='false_positive') for i in range(400)])
        other=dict(copy.deepcopy(cohort),id='same-metrics-different-cohort')
        evidence={'latest_result':dict(path='result.json',sha256='frozen',summary=dict(required_cohorts=[cohort,other],comparison=comparison)),
                  'failed_0':dict(path='failed.json',sha256='old',summary=dict(required_cohorts=[cohort,other],conditions={'max_fp':0},failure_reasons=['new_crop_errors']))}
        errors=[dict(id=str(i),kind='miss' if i==9 else 'false_positive',score=.7,target=1 if i==9 else 0) for i in range(12)]
        packet=dict(evidence=compact_evidence(evidence),error_cases=errors,error_count=100,evidence_reference_format='refs',
                    failed_hypotheses={'failed':['failed_0']},same_evaluation_metrics={'cohort':'fixed'})
        original=copy.deepcopy(packet);bounded=bound_repeated_errors(packet)
        self.assertLess(len(encoded(bounded).encode()),24000)
        decoded=expand_evidence(bounded['evidence'])
        for key in ('latest_result','failed_0'):
            self.assertEqual(decoded[key]['path'],evidence[key]['path']);self.assertEqual(decoded[key]['sha256'],evidence[key]['sha256'])
            expected={v['id']:v for v in evidence[key]['summary']['required_cohorts']}
            actual={v['id']:v for v in decoded[key]['summary']['required_cohorts']}
            self.assertEqual(set(expected),set(actual))
            for identity,c in actual.items():
                for field in ('comparison','point_comparison','acceptance','acceptance_passed'):
                    self.assertEqual(c[field],expected[identity][field])
                self.assertEqual(c['error_count'],400);self.assertEqual(c['errors_omitted'],400);self.assertEqual(c['errors'],[])
        self.assertEqual(decoded['failed_0']['summary']['conditions'],{'max_fp':0})
        self.assertEqual(decoded['failed_0']['summary']['failure_reasons'],['new_crop_errors'])
        self.assertEqual(bounded['failed_hypotheses'],packet['failed_hypotheses'])
        self.assertEqual(bounded['same_evaluation_metrics'],packet['same_evaluation_metrics'])
        self.assertEqual({v['kind'] for v in bounded['error_cases']},{'miss','false_positive'})
        self.assertEqual(bounded['error_list_summary']['omitted'],97)
        self.assertEqual(packet,original)

    def test_late_miss_case_is_not_hidden_by_repeated_false_positives(self):
        from card_condition.cross_review_evidence import error_examples
        errors=[dict(id=str(i),kind='false_positive') for i in range(20)]+[dict(id='missed-defect',kind='miss')]
        sample=error_examples(errors,3)
        self.assertEqual(len(sample),3)
        self.assertEqual({v['kind'] for v in sample},{'miss','false_positive'})
        self.assertEqual(len(errors),21)

    def test_large_noncode_evidence_still_fails_original_limit(self):
        from card_condition.cross_review import encoded
        from card_condition.cross_review_evidence import bound_code_excerpt
        packet=dict(evidence=dict(related_code=dict(summary=dict(excerpt='x')),important='z'*25000))
        result=bound_code_excerpt(packet)
        self.assertGreater(len(encoded(result).encode()),24000)
        self.assertEqual(result['evidence']['important'],'z'*25000)


if __name__=='__main__':
    unittest.main()

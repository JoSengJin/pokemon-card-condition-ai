from datetime import datetime,timedelta,timezone
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from card_condition import experiment_record as recording
from card_condition.cross_review_evidence import latest_packet
from card_condition.regression_audit import compare_predictions


class ExperimentRecordTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'card_condition').mkdir()
        self.code = self.root / 'card_condition/model.py'
        self.code.write_text('def score(x):\n    return x + 1\n')
        self.old = self.root / 'artifacts/old-20261019'
        self.old.mkdir(parents=True)
        (self.old / 'baseline.py').write_text('def score(x):\n    return x\n')
        self.rows = [dict(id=str(i), target=t, group=str(i), image_sha256=str(i), box=[0,0,1,1], fold=i)
                     for i,t in enumerate([1,0,0])]
        result = dict(rows=self.rows, before_scores=[.9,.8,.9], scores=[.9,.8,.9],
                      comparison=compare_predictions([1,0,0],[.9,.8,.9],[.9,.8,.9]), independent=False,
                      peaks=[{'human_token':0,'human_score':.9}, {}, {}])
        recording.save(self.old / 'result.json', result)
        recording.save(self.old / 'plan.json', dict(hypothesis='old', tracked_sha256={str(self.code):'old'}))
        self.plan = dict(hypothesis_id='normal-objective-v2', hypothesis='검증할 가설', change='집계 변수 하나',
                         success_criterion='FP 1 이하, FN 0, 새 오답·실제점 누락 없음', failure_criterion='하나라도 미충족',
                         reference_result='artifacts/old-20261019/result.json',
                         acceptance=dict(max_fp=1,max_fn=0,no_new_errors=True,require_actual_point_guard=True),
                         code_changes=[dict(path='card_condition/model.py', baseline='artifacts/old-20261019/baseline.py')])
        self.worker = '''import json,os
from pathlib import Path
p=Path(os.environ['CARD_CONDITION_EXPERIMENT_DIR'])
r=json.loads(Path(os.environ['CARD_CONDITION_EXPERIMENT_REFERENCE']).read_text())
o=dict(rows=r['rows'],scores=r['before_scores'],point_ids=r['point_ids'],point_scores=r['point_scores'])
BODY
(p/'observations.json').write_text(json.dumps(o))
'''
        network = patch('httpx.Client.send', side_effect=AssertionError('No Gemini or other HTTP calls'))
        network.start()
        self.addCleanup(network.stop)

    def run_case(self, body='', command=None):
        with contextlib.redirect_stdout(io.StringIO()):
            code = recording.run(self.root, self.plan, command or [sys.executable, '-c', self.worker.replace('BODY', body)])
        folder, record = recording.records(self.root)[0]
        return code, folder, record

    def test_diagnostic_evidence_reaches_review_without_becoming_failed_model_hypothesis(self):
        self.plan['experiment_kind']='diagnostic'
        self.run_case(command=[sys.executable,'-c','raise SystemExit(7)'])
        code,folder,item=self.run_case("o['diagnostic_evidence']={'kind':'gradient_conflict','supporting_groups':2};(p/'diagnostics.json').write_text('{}')")
        self.assertEqual(code,0);self.assertEqual(item['status'],'completed')
        result=recording.read(folder/'result.json')
        self.assertFalse(result['acceptance_passed'])
        packet=latest_packet(self.root)
        self.assertEqual(packet['evidence']['latest_diagnostic']['summary']['supporting_groups'],2)
        self.assertNotIn(self.plan['hypothesis_id'],packet['failed_hypotheses'])
        self.assertIn(self.plan['hypothesis_id'],packet['failed_executions'])
        (folder/'diagnostics.json').write_text('{"tampered":true}')
        with self.assertRaises(ValueError):latest_packet(self.root)

    def test_non_diagnostic_plan_cannot_add_diagnostic_evidence(self):
        code,folder,item=self.run_case("o['diagnostic_evidence']={'kind':'gradient_conflict'}")
        self.assertEqual(code,1);self.assertEqual(item['status'],'failed')

    def test_completed_diagnostic_is_retained_after_new_model_experiment(self):
        self.plan['experiment_kind']='diagnostic'
        self.run_case(command=[sys.executable,'-c','raise SystemExit(7)'])
        self.run_case("o['diagnostic_evidence']={'kind':'gradient_conflict','supporting_groups':2}")
        diagnostic_id=self.plan['hypothesis_id']
        self.plan.pop('experiment_kind');self.plan['hypothesis_id']='later-model'
        self.run_case()
        packet=latest_packet(self.root)
        refs=packet['completed_diagnostics'][diagnostic_id]
        self.assertEqual(packet['evidence'][refs[0]]['summary']['status'],'completed')
        self.assertEqual(packet['evidence'][refs[0]]['summary']['measurements']['supporting_groups'],2)
        self.assertIn(diagnostic_id,packet['failed_executions'])
        self.assertNotIn(diagnostic_id,packet['failed_hypotheses'])

    def test_completed_plan_diff_and_actual_scores_are_frozen(self):
        code, folder, record = self.run_case()
        self.assertEqual((code,record['status']),(0,'completed'))
        self.assertFalse(recording.read(folder/'result.json')['acceptance_passed'])
        self.assertEqual(recording.read(folder/'plan.json')['success_criterion'], self.plan['success_criterion'])
        self.assertIn('+    return x + 1', (folder/'changes.diff').read_text())
        self.assertIn('-    return x', (folder/'changes.diff').read_text())
        recording.verify(folder,record)
        self.code.write_text('def unrelated():\n    return 999\n')
        packet = latest_packet(self.root)
        self.assertIn(str(folder.name),packet['latest_result'])
        self.assertIn('+    return x + 1',packet['evidence']['related_code']['summary']['excerpt'])
        self.assertNotIn('unrelated',packet['evidence']['related_code']['summary']['excerpt'])
        self.assertIn(self.plan['hypothesis_id'],packet['failed_hypotheses'])
        self.assertIn('execution_record',packet['evidence'])
        self.assertIn('success_criterion',packet['evidence']['latest_plan']['summary'])

    def test_acceptance_pass_blocks_review(self):
        _, folder, _ = self.run_case("o['scores']=[.9,.1,.9]")
        self.assertTrue(recording.read(folder/'result.json')['acceptance_passed'])
        with self.assertRaisesRegex(ValueError,'정체 근거'):
            latest_packet(self.root)

    def test_predeclared_strict_criterion_not_aggregate_gain_decides(self):
        self.plan['acceptance']['max_fp']=0
        self.run_case("o['scores']=[.9,.1,.9]")
        packet=latest_packet(self.root)
        self.assertTrue(packet['same_evaluation_metrics']['latest_experiment']['informative_improvement'])
        self.assertTrue(packet['stalled'])

    def required_cohort(self, actual_point=False):
        rows = [dict(r, id='held-' + str(i)) for i, r in enumerate(self.rows[:2])]
        result = dict(rows=rows, before_scores=[.9,.8], scores=[.9,.8])
        if actual_point:
            result.update(point_ids=['held-0:4'], point_scores=[.9])
        path = self.root/'artifacts/held/reference.json'
        path.parent.mkdir(exist_ok=True)
        recording.save(path, result)
        self.plan['required_cohorts'] = [dict(id='held', reference_result='artifacts/held/reference.json',
            acceptance=dict(max_fp=0,max_fn=0,no_new_errors=True,require_actual_point_guard=actual_point))]

    def required_body(self, scores='[.9,.1]', points='c["point_scores"]'):
        return ("o['scores']=[.9,.1,.9]\n"
                "c=r['required_cohorts'][0]\n"
                "o['required_cohorts']=[dict(id=c['id'],rows=c['rows'],scores=" + scores +
                ",point_ids=c['point_ids'],point_scores=" + points + ")]\n")

    def test_required_failure_blocks_primary_pass_and_reaches_review(self):
        self.required_cohort()
        code,folder,item=self.run_case(self.required_body('[.9,.8]'))
        result=recording.read(folder/'result.json')
        self.assertEqual((code,item['status']),(0,'completed'))
        self.assertTrue(result['primary_acceptance_passed'])
        self.assertFalse(result['acceptance_passed'])
        self.assertEqual(result['required_cohorts'][0]['comparison']['after']['fp'],1)
        packet=latest_packet(self.root)
        self.assertEqual(packet['evidence']['latest_result']['summary']['required_cohorts'][0]['errors'][0]['id'],'held-1')
        reasons=[v['summary'].get('failure_reasons',[]) for k,v in packet['evidence'].items() if k.startswith('failed_')]
        self.assertTrue(any('required_cohort_failed:held' in r for r in reasons))
        from card_condition.cross_review_auto import measured_gain, render_result
        self.assertFalse(measured_gain(result))
        render_result(self.root,folder)
        self.assertIn('필수 평가: held',(folder/'comparison.html').read_text())

    def test_all_required_and_primary_pass(self):
        self.required_cohort()
        code,folder,_=self.run_case(self.required_body())
        result=recording.read(folder/'result.json')
        self.assertEqual(code,0)
        self.assertTrue(result['acceptance_passed'])
        self.assertTrue(result['required_cohorts'][0]['acceptance_passed'])

    def test_required_cohort_missing_output_or_changed_truth_fails(self):
        self.required_cohort()
        for body in ["o['scores']=[.9,.1,.9]",self.required_body()+"o['required_cohorts'][0]['rows'][0]['target']=0",
                     self.required_body()+"o['required_cohorts'][0]['scores']=[.9,float('nan')]",
                     self.required_body()+"o['required_cohorts']=[o['required_cohorts'][0]]*2"]:
            with self.subTest(body=body):
                code,_,item=self.run_case(body)
                self.assertEqual((code,item['status']),(1,'failed'))

    def test_required_actual_point_miss_blocks_otherwise_passing_result(self):
        self.required_cohort(actual_point=True)
        _,folder,_=self.run_case(self.required_body(points='[.1]'))
        result=recording.read(folder/'result.json')
        self.assertTrue(result['primary_acceptance_passed'])
        self.assertFalse(result['acceptance_passed'])
        self.assertEqual(result['required_cohorts'][0]['point_comparison']['new_misses'],[0])

    def test_required_declaration_preserves_points_and_unknown_is_not_normal(self):
        self.required_cohort(actual_point=True)
        self.plan['required_cohorts'][0]['acceptance']['require_actual_point_guard']=False
        with self.assertRaises(ValueError):self.run_case()
        self.required_cohort()
        self.plan['required_cohorts']*=2
        with self.assertRaises(ValueError):self.run_case()
        self.required_cohort()
        path=self.root/'artifacts/held/reference.json'
        reference=recording.read(path);reference['rows'][1]['target']=None;recording.save(path,reference)
        with self.assertRaises(ValueError):self.run_case()

    def test_required_cohorts_cannot_be_dropped_on_next_reference(self):
        self.required_cohort()
        _,folder,_=self.run_case(self.required_body())
        self.plan['reference_result']=str((folder/'result.json').relative_to(self.root))
        self.plan.pop('required_cohorts')
        with self.assertRaisesRegex(ValueError,'cannot be dropped'):self.run_case()

    def test_required_cohort_uses_latest_reference_scores_not_original_scores(self):
        self.required_cohort()
        _,previous,_=self.run_case(self.required_body())
        self.plan['reference_result']=str((previous/'result.json').relative_to(self.root))
        _,folder,_=self.run_case(self.required_body('[.9,.8]'))
        cohort=recording.read(folder/'result.json')['required_cohorts'][0]
        self.assertEqual(cohort['before_scores'],[.9,.1])
        self.assertEqual(cohort['comparison']['new_false_positives'],[1])

    def test_unplanned_required_scores_fail(self):
        code,_,item=self.run_case("o['required_cohorts']=[dict(id='unplanned',rows=[],scores=[])]")
        self.assertEqual((code,item['status']),(1,'failed'))

    def test_failed_child_and_missing_output_are_recorded_without_old_fallback(self):
        for command in ([sys.executable,'-c','raise SystemExit(7)'], [sys.executable,'-c','pass'], ['missing-experiment-executable']):
            with self.subTest(command=command):
                code,folder,r=self.run_case(command=command)
                self.assertEqual((code,r['status']),(1,'failed'))
                self.assertTrue(r['finished_at'])
                self.assertTrue((folder/'plan.json').exists())
                with self.assertRaisesRegex(recording.LatestExperimentUnavailable,'failed'):
                    latest_packet(self.root)

    def test_changed_truth_or_point_identity_and_source_mutation_fail(self):
        bodies=["o['rows'][0]['target']=0", "o['point_ids']=['invented']",
                "Path('card_condition/model.py').write_text('changed during run')"]
        for body in bodies:
            self.code.write_text('def score(x):\n    return x + 1\n')
            with self.subTest(body=body):
                code,_,r=self.run_case(body)
                self.assertEqual((code,r['status']),(1,'failed'))

    def test_new_actual_point_miss_rejects_otherwise_better_result(self):
        _,folder,_=self.run_case("o['scores']=[.9,.1,.9]; o['point_scores']=[.1]")
        r=recording.read(folder/'result.json')
        self.assertFalse(r['acceptance_passed'])
        self.assertEqual(r['point_comparison']['new_misses'],[0])

    def test_changed_frozen_evidence_blocks_review(self):
        _,folder,_=self.run_case()
        (folder/'changes.diff').write_text('tampered')
        with self.assertRaisesRegex(ValueError,'Frozen experiment'):
            latest_packet(self.root)

    def test_equal_ids_with_different_truth_are_not_failed_history(self):
        self.run_case()
        source=recording.read(self.old/'result.json')
        source['rows'][1]['image_sha256']='different-photo'
        recording.save(self.old/'result.json',source)
        self.plan['hypothesis_id']='different-cohort'
        self.run_case()
        packet=latest_packet(self.root)
        self.assertNotIn('normal-objective-v2',packet['failed_hypotheses'])

    def test_declared_execution_time_wins_over_mtime_and_legacy_folder_date(self):
        _,older,_=self.run_case()
        self.plan['hypothesis_id']='newer-run'
        _,newer,_=self.run_case()
        os.utime(older/'result.json',(2000000000,2000000000))
        packet=latest_packet(self.root)
        self.assertIn(newer.name,packet['latest_result'])

    def test_common_experiment_to_review_and_cached_response_without_http(self):
        import hashlib
        from card_condition import cross_review_manual as manual
        from card_condition.cross_review import FIELDS
        self.run_case()
        config=recording.read(Path('examples/cross-review/config.json'))
        config['free_tier_verification']=dict(tier='Free',project_id='test-only',model=config['model'],billing_disabled=True,verified_at=datetime.now(timezone.utc).isoformat(),expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),evidence='mock only',
                                            key_sha256=hashlib.sha256(b'test-key').hexdigest())
        path=self.root/'artifacts/cross-review-20261019/local-config.json'; path.parent.mkdir()
        recording.save(path,config)
        response=dict.fromkeys(FIELDS,'')
        response.update(proposal_status='propose',new_evidence_ids=['latest_result'],compared_failed_hypotheses=list(manual.latest_packet(self.root)['failed_hypotheses']),difference_from_failed='최신 diff에 근거한 다른 집계 조건')
        response.update(hypothesis_id='alternative',cause='변경 diff를 대조한 검증용 가설',evidence='related_code')
        with patch.object(manual,'ROOT',self.root), patch.dict(os.environ,{'POKEMON_CARD_CONDITION_GEMINI_API_KEY':'test-key'}), \
             patch('card_condition.cross_review.Gemini.__call__',return_value=(json.dumps(response),{'total_token_count':7})) as api, \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manual.main([]),0)
            self.assertEqual(manual.main([]),0)
            api.assert_called_once()
        active=recording.read(self.root/'artifacts/manual-cross-review/active.json')
        packet=recording.read(Path(active['directory'])/'packet.json')
        self.assertIn('execution_record',packet['evidence'])
        self.assertIn('+    return x + 1',packet['evidence']['related_code']['summary']['excerpt'])

    def test_no_signal_handler_or_child_side_effect_from_invalid_threshold(self):
        self.plan['threshold']=.7
        with patch('subprocess.Popen') as child:
            with self.assertRaises(ValueError): recording.run(self.root,self.plan,['anything'])
            child.assert_not_called()

    def test_newest_failed_or_running_record_blocks_stale_success(self):
        self.run_case()
        folder,item=recording.prepare(self.root,self.plan,[sys.executable,'-c','pass'])
        with self.assertRaisesRegex(recording.LatestExperimentUnavailable,'running'):
            latest_packet(self.root)
        with patch('card_condition.experiment_record.os.kill',side_effect=ProcessLookupError()):
            with self.assertRaisesRegex(recording.LatestExperimentUnavailable,'interrupted'):
                latest_packet(self.root)
        item=recording.read(folder/'record.json')
        self.assertEqual(item['error_kind'],'orphaned_process')
        self.assertTrue(item['end_time_inferred'])

    def test_prior_execution_failure_is_included_without_invented_metrics(self):
        self.plan['hypothesis_id']='failed-execution'
        self.run_case(command=[sys.executable,'-c','raise SystemExit(7)'])
        self.plan['hypothesis_id']='new-experiment'
        self.run_case()
        packet=latest_packet(self.root)
        refs=packet['failed_executions']['failed-execution']
        self.assertNotIn('failed-execution',packet['failed_hypotheses'])
        summary=packet['evidence'][refs[0]]['summary']
        self.assertEqual(summary['status'],'failed')
        self.assertNotIn('comparison',summary)

    def test_invalid_plan_or_missing_truth_does_not_start_child(self):
        del self.plan['success_criterion']
        with patch('subprocess.Popen') as child:
            with self.assertRaises(ValueError): recording.run(self.root,self.plan,['anything'])
            child.assert_not_called()
        self.plan['success_criterion']='criterion'
        result=recording.read(self.old/'result.json'); result.pop('peaks')
        recording.save(self.old/'result.json',result)
        with self.assertRaisesRegex(ValueError,'Actual human point'):
            recording.run(self.root,self.plan,['anything'])

    def test_failed_partial_result_cannot_become_new_reference(self):
        _,folder,_=self.run_case("o['point_ids']=['wrong']")
        self.plan['reference_result']=str((folder/'result.json').relative_to(self.root))
        with patch('subprocess.Popen') as child:
            with self.assertRaisesRegex(ValueError,'incomplete experiment'):
                recording.run(self.root,self.plan,['anything'])
            child.assert_not_called()

    def test_supervisor_sigterm_persists_interruption(self):
        plan=self.root/'input-plan.json'; recording.save(plan,self.plan)
        script=('from pathlib import Path; import json; from card_condition.experiment_record import run; '
                'raise SystemExit(run(Path('+repr(str(self.root))+'),json.loads(Path('+repr(str(plan))+').read_text()),'
                '['+repr(sys.executable)+',"-c","import time; time.sleep(30)"]))')
        env=dict(os.environ,PYTHONPATH=str(Path.cwd()))
        process=subprocess.Popen([sys.executable,'-c',script],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+10
            record_path=None
            while time.monotonic()<deadline:
                paths=list((self.root/'artifacts/experiments').glob('*/record.json'))
                if paths and recording.read(paths[0]).get('child_pid'):
                    record_path=paths[0];break
                time.sleep(.02)
            self.assertIsNotNone(record_path)
            process.send_signal(signal.SIGTERM)
            _,stderr=process.communicate(timeout=8)
            self.assertEqual(process.returncode,143,stderr.decode())
            r=recording.read(record_path)
            self.assertEqual((r['status'],r['signal']),('interrupted',signal.SIGTERM))
            self.assertTrue(r['finished_at'])
        finally:
            if process.poll() is None:
                process.kill();process.wait()
            if process.stderr: process.stderr.close()


if __name__ == '__main__':
    unittest.main()

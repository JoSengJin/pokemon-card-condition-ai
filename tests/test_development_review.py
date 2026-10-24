from datetime import datetime,timedelta,timezone
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from card_condition import development_review as integration
from card_condition import experiment_record as recording
from card_condition import cross_review_manual as manual
from card_condition import cross_review_auto as auto
from card_condition.workspace_lock import workspace_lock, ENV_FD
import test_experiment_record as experiment_fixture
import test_cross_review_auto as auto_fixture

REPO = Path(__file__).resolve().parents[1]


def contender(root):
    code = '''import sys
from pathlib import Path
from card_condition.workspace_lock import workspace_lock
try:
    with workspace_lock(Path(sys.argv[1]),'contender'): pass
except BlockingIOError: raise SystemExit(3)
'''
    env = dict(os.environ, PYTHONPATH=str(REPO)); env.pop(ENV_FD, None)
    return subprocess.run([sys.executable, '-c', code, str(root)], env=env, capture_output=True).returncode


class HandoffTest(unittest.TestCase):
    setUp = experiment_fixture.ExperimentRecordTest.setUp
    run_case = experiment_fixture.ExperimentRecordTest.run_case

    def enable(self):
        recording.save(self.root/'development-review.json',dict(enabled=True,session_id='development-session'))
        env=patch.dict(os.environ,{'CODEX_THREAD_ID':'development-session'})
        env.start();self.addCleanup(env.stop)

    def test_other_sessions_and_disabled_policy_never_call_review(self):
        self.enable()
        for session, enabled in [('other',True),('development-session',False)]:
            recording.save(self.root/'development-review.json',dict(enabled=enabled,session_id='development-session'))
            with patch.dict(os.environ,{'CODEX_THREAD_ID':session}), patch.object(manual,'main',side_effect=AssertionError('No review')):
                _,folder,_=self.run_case()
                self.assertFalse((folder/'development_handoff.json').exists())

    def test_passing_experiment_and_execution_failure_do_not_trigger_ai(self):
        self.enable()
        with patch.object(manual,'main',side_effect=AssertionError('No review')):
            _,folder,_=self.run_case("o['scores']=[.9,.2,.2]")
            self.assertEqual(recording.read(folder/'development_handoff.json')['status'],'not_stalled')
            code,folder,_=self.run_case(command=[sys.executable,'-c','raise SystemExit(7)'])
            self.assertEqual(code,1)
            self.assertEqual(recording.read(folder/'development_handoff.json')['status'],'execution_failed')

    def test_no_call_plan_blocks_review_and_persists_handoff(self):
        self.enable()
        self.plan['gemini_calls_allowed']=0
        with patch.object(manual,'main',side_effect=AssertionError('No actual review')):
            _,folder,_=self.run_case()
            state=recording.read(folder/'development_handoff.json')
            again=integration.after_experiment(self.root,folder)
        self.assertEqual(state['status'],'ai_calls_forbidden')
        self.assertEqual(state['gemini_calls'],0)
        self.assertEqual(state,again)
        self.assertEqual(Path(recording.read(self.root/'artifacts/development-cycle/latest.json')['handoff']).resolve(),(folder/'development_handoff.json').resolve())

    def test_no_fresh_evidence_stops_before_review(self):
        self.enable()
        from card_condition.cross_review_evidence import latest_packet
        with patch.object(integration,'enabled',return_value=False): _,folder,_=self.run_case()
        packet=latest_packet(self.root);packet['fresh_evidence_ids']=[]
        with patch('card_condition.cross_review_evidence.latest_packet',return_value=packet),patch.object(manual,'main',side_effect=AssertionError('No review')):
            state=integration.after_experiment(self.root,folder)
        self.assertEqual(state['status'],'no_new_evidence')

    def test_error_or_uncertain_handoff_is_not_retried(self):
        self.enable()
        with patch.object(integration,'enabled',return_value=False): _,folder,_=self.run_case()
        with patch.object(manual,'main',side_effect=ValueError('mock request failure')) as review:
            first=integration.after_experiment(self.root,folder)
            second=integration.after_experiment(self.root,folder)
        self.assertEqual(first['status'],'handoff_error');self.assertEqual(first,second);review.assert_called_once()
        recording.save(folder/'development_handoff.json',dict(status='review_running'))
        with patch.object(manual,'main',side_effect=AssertionError('Uncertain request must not repeat')):
            self.assertEqual(integration.after_experiment(self.root,folder)['status'],'review_running')

    def test_workspace_mutex_blocks_second_process_and_all_entrypoints(self):
        with workspace_lock(self.root,'first writer'):
            with workspace_lock(self.root,'nested same owner'): self.assertEqual(contender(self.root),3)
            with patch.object(recording,'ROOT',self.root),patch.object(manual,'ROOT',self.root),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                # A child owns a different OS lock descriptor; tests below also exercise CLI paths.
                self.assertEqual(contender(self.root),3)
        self.assertEqual(contender(self.root),0)

    def test_contending_experiment_and_review_cli_stop_before_work(self):
        owner_code="import sys\nfrom pathlib import Path\nfrom card_condition.workspace_lock import workspace_lock\nwith workspace_lock(Path(sys.argv[1]),'other owner'):\n print('ready',flush=True)\n sys.stdin.readline()\n"
        env=dict(os.environ,PYTHONPATH=str(REPO));env.pop(ENV_FD,None)
        owner=subprocess.Popen([sys.executable,'-c',owner_code,str(self.root)],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
        try:
            self.assertEqual(owner.stdout.readline().strip(),'ready')
            with patch.object(manual,'ROOT',self.root),patch.object(recording,'ROOT',self.root), \
                 patch.object(manual,'review',side_effect=AssertionError('No model review')), \
                 patch.object(recording,'prepare',side_effect=AssertionError('No experiment')), \
                 contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                path=self.root/'plan.json';recording.save(path,self.plan)
                self.assertEqual(manual.main(['--auto']),1)
                self.assertEqual(recording.main(['--plan',str(path),'--',sys.executable,'-c','pass']),1)
        finally:
            owner.communicate('done\n',timeout=10)
        self.assertEqual(contender(self.root),0)

    def test_wrong_inherited_descriptor_is_rejected(self):
        other=self.root/'other';other.write_text('x')
        with other.open() as file,patch.dict(os.environ,{ENV_FD:str(file.fileno())}):
            with self.assertRaises(ValueError):
                with workspace_lock(self.root,'invalid delegation'):pass

    def test_delegated_child_retains_lock_after_parent_context_closes(self):
        with workspace_lock(self.root,'parent edit') as fd:
            env=dict(os.environ,PYTHONPATH=str(REPO),**{ENV_FD:str(fd)})
            code="import sys; print('ready',flush=True); sys.stdin.readline()"
            child=subprocess.Popen([sys.executable,'-c',code],env=env,pass_fds=(fd,),stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
            self.assertEqual(child.stdout.readline().strip(),'ready')
        try:
            self.assertEqual(contender(self.root),3)
        finally:
            child.communicate('done\n',timeout=10)
        self.assertEqual(contender(self.root),0)

    def test_child_can_inherit_development_lock_without_deadlock(self):
        code='''import sys
from pathlib import Path
from card_condition.workspace_lock import workspace_lock
with workspace_lock(Path(sys.argv[1]),'delegated child'): print('owned')
'''
        with workspace_lock(self.root,'development edit') as fd:
            env=dict(os.environ,PYTHONPATH=str(REPO),**{ENV_FD:str(fd)})
            result=subprocess.run([sys.executable,'-c',code,str(self.root)],env=env,pass_fds=(fd,),capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(contender(self.root),3)
        self.assertEqual(contender(self.root),0)


class HandoffEndToEndTest(unittest.TestCase):
    from test_cross_review_high_fixes import HighFixTest as Fixture
    setUp=Fixture.setUp
    backend=Fixture.backend
    gemini=Fixture.gemini
    judge=Fixture.judge

    def test_stalled_common_run_holds_generated_implementation_and_hands_back(self):
        self.check_cycle(False)

    def test_forged_perfect_worker_cannot_be_adopted_by_development_handoff(self):
        self.check_cycle(True)

    def check_cycle(self,forged):
        from card_condition import cross_review_nemotron as native
        marker=self.root/'untrusted-marker'
        if forged:self.implementation['worker']=f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nscores=[1,0,0]\n"
        recording.save(self.root/'development-review.json',dict(enabled=True,session_id='development-session'))
        config=copy.deepcopy(self.config)
        config['free_tier_verification']=dict(tier='Free',project_id='mock',model=config['model'],billing_disabled=True,verified_at=datetime.now(timezone.utc).isoformat(),expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),evidence='mock only',key_sha256=hashlib.sha256(b'test-key').hexdigest())
        (self.root/'artifacts/cross-review-20261019').mkdir()
        recording.save(self.root/'artifacts/cross-review-20261019/local-config.json',config)
        baseline=self.root/'artifacts/baseline.py';baseline.write_text(self.original)
        plan=dict(hypothesis_id='stalled-parent',hypothesis='mock stalled cause',change='one mock variable',
                  success_criterion='FP<=1 FN0',failure_criterion='otherwise',reference_result=self.packet['latest_result'],
                  acceptance=self.verdict['acceptance'],code_changes=[dict(path='card_condition/model.py',baseline='artifacts/baseline.py')])
        def gemini(prompt,timeout):
            packet=json.loads(prompt[prompt.index('{"comparison":'):])['evidence']
            self.response['compared_failed_hypotheses']=list(packet['failed_hypotheses'])
            self.assertEqual(contender(self.root),3)
            return self.gemini(prompt,timeout)
        def backend(root,phase,prompt,directory,thread):
            self.assertEqual(contender(root),3)
            if phase in ('verify','correct'):
                frozen=recording.read(directory/'input.json')
                self.verdict['failed_hypotheses_checked']=list(frozen['evidence']['failed_hypotheses'])
            return self.backend(root,phase,prompt,directory,thread)
        class Response:
            text='<span>Free Endpoint</span><span>Available</span>'
            def raise_for_status(self):pass
        with patch.dict(os.environ,{'CODEX_THREAD_ID':'development-session','POKEMON_CARD_CONDITION_GEMINI_API_KEY':'test-key'}), \
             patch.object(manual,'ROOT',self.root),patch('card_condition.cross_review.Gemini.__call__',side_effect=gemini), \
             patch('card_condition.cross_review_app_server.app_server_backend',side_effect=backend),patch.object(native,'http_call',side_effect=self.judge),patch('httpx.get',return_value=Response()),contextlib.redirect_stdout(io.StringIO()):
            code=recording.run(self.root,plan,[sys.executable,'-c',self.worker])
            parent=next(folder for folder,item in recording.records(self.root) if item['hypothesis_id']=='stalled-parent')
            state=recording.read(parent/'development_handoff.json')
            before=(self.gemini_calls,len(self.codex_calls),self.n_calls)
            integration.after_experiment(self.root,parent)
            self.assertEqual((self.gemini_calls,len(self.codex_calls),self.n_calls),before)
        self.assertEqual(code,0)
        self.assertEqual(state['status'],'review_finished')
        self.assertEqual(state['review_status'],'trusted_execution_required')
        self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,1)
        self.assertEqual([phase for phase,_ in self.codex_calls],['verify','correct','implement'])
        self.assertEqual(len(recording.records(self.root)),1)  # No generated or recursive experiment.
        self.assertIsNone(state['acceptance_passed']);self.assertIsNone(state['performance_improved_on_same_cohort'])
        self.assertFalse(state['code_applied']);self.assertFalse(state['worker_executed'])
        self.assertEqual(self.source.read_text(),self.original);self.assertFalse(marker.exists())
        self.assertIsNone(state['experiment_record']);self.assertTrue(Path(state['implementation_proposal']).exists())
        self.assertTrue(Path(state['next_steps']).exists());self.assertTrue(Path(state['token_report']).exists())
        self.assertEqual(contender(self.root),0)


if __name__=='__main__': unittest.main()

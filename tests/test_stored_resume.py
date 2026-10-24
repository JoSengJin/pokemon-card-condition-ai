import contextlib
import io
import unittest
from unittest.mock import patch
from card_condition import cross_review_flow as flow,cross_review_nemotron as native
from card_condition.cross_review import digest
from card_condition.experiment_record import read,save,sha
from card_condition.workspace_lock import workspace_lock
from card_condition.development_review import review_scope
import test_cross_review_high_fixes as fixture

class StoredResumeTest(unittest.TestCase):
    setUp=fixture.HighFixTest.setUp
    backend=fixture.HighFixTest.backend
    gemini=fixture.HighFixTest.gemini
    judge=fixture.HighFixTest.judge
    run_flow=fixture.HighFixTest.run_flow

    def prepare_saved(self):
        with patch.object(native,'review',return_value=None):self.assertEqual(self.run_flow(),1)
        state=read(self.folder/'automation.json');state['status']='verifying';state['critic_config'].pop('shared_core');save(self.folder/'automation.json',state)
        return dict(correction_sha256=sha(next(self.folder.glob('codex/correct-*/call.json'))),critiques_sha256=digest(state['critiques']),authorization='explicit test human authorization')

    def resume(self,proof):
        class Response:
            text='Free Endpoint Available'
            def raise_for_status(self):pass
        with workspace_lock(self.root,'test authorized resume'),review_scope(),patch.object(native,'http_call',side_effect=self.judge),patch('httpx.get',return_value=Response()),contextlib.redirect_stdout(io.StringIO()):
            return flow.run_codex_first(self.root,self.folder,read(self.folder/'result.json'),backend=self.backend,
                gemini_caller=lambda *a: self.fail('Gemini must not be called'),call_ceiling=1,stored_resume=proof)

    def test_explicit_reuse_runs_only_judge_and_final_implementation_and_warns_about_old_inputs(self):
        proof=self.prepare_saved();before_calls=list(self.codex_calls);before_gem=self.gemini_calls
        self.assertEqual(self.resume(proof),2)
        self.assertEqual(self.codex_calls[len(before_calls):],[('implement',None)])
        self.assertEqual(self.gemini_calls,before_gem);self.assertEqual(self.n_calls,1)
        self.assertIn('earlier inputs',dict(self.inputs)['judge']['debate']['stored_review_notice'])
        self.assertNotIn('shared_core',read(self.folder/'automation.json')['critic_config'])

    def test_default_cannot_relabel_archived_response_as_current_shared_core(self):
        self.prepare_saved();self.assertEqual(self.resume(None),1);self.assertEqual(self.n_calls,0)

    def test_changed_saved_response_provenance_stops_before_judge(self):
        proof=self.prepare_saved();proof['correction_sha256']='wrong'
        self.assertEqual(self.resume(proof),1);self.assertEqual(self.n_calls,0)

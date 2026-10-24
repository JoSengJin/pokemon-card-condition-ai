import copy
import tempfile
import unittest
from pathlib import Path

from card_condition.cross_review_adversarial import build, evaluate, evidence_registry, score_arguments, measurement_claim_text
from card_condition.experiment_record import save, sha


class EvidencePolicyTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.folder=self.root/'review'; self.folder.mkdir()
        self.file=self.root/'result.json'; save(self.file,dict(fp=3, measured=True))
        self.packet=dict(stagnation_reason='오탐 개선 정체', evidence=dict(result=dict(path='result.json',sha256=sha(self.file))))
        self.a=dict(cause='새 손실이 오탐을 줄인다',evidence='result')
        self.b=dict(rationale='원인을 입증하는 새 실험은 없다')
        self.j=dict(action='stop',evidence_ids=['result'],new_question='')

    def run_round(self, **updates):
        state=dict(root=str(self.root),packet=self.packet,advocate_arguments=self.a,
                   skeptic_arguments=self.b,judge=self.j,prior={},max_rounds=2)
        state.update(updates)
        from langgraph.checkpoint.memory import InMemorySaver
        return build(InMemorySaver()).invoke(state,dict(configurable=dict(thread_id='test'),recursion_limit=16))

    def test_exact_measured_claim_accepts(self):
        self.packet['machine_claim']=dict(evidence_id='result',field=['fp'],expected=3)
        self.a['cause']=measurement_claim_text(self.packet['machine_claim'])
        self.assertEqual(self.run_round()['decision'],'ACCEPT')

    def test_decisive_measurement_rejects(self):
        self.packet['machine_claim']=dict(evidence_id='result',field=['fp'],expected=0)
        self.a['cause']=measurement_claim_text(self.packet['machine_claim'])
        self.assertEqual(self.run_round()['decision'],'REJECT')

    def test_insufficient_causal_evidence_uncertain_even_if_selected(self):
        self.j['action']='select'
        result=self.run_round()
        self.assertEqual(result['decision'],'UNCERTAIN')
        self.assertEqual(result['experiment_action'],'select')

    def test_wrong_agreement_cannot_verify_claim(self):
        self.b=copy.deepcopy(self.a)
        self.assertEqual(self.run_round()['verified_facts'],[])
        self.assertEqual(self.run_round()['decision'],'UNCERTAIN')

    def test_groundless_high_judge_ratings_are_capped(self):
        supplied={k:100 for k in ('reliability','logic','response','independence')}
        result=score_arguments(dict(advocate=dict(supplied,evidence_ids=['invented'])),evidence_registry(self.root,self.packet))
        self.assertEqual(result['advocate']['weighted_total'],49)
        self.assertIsNone(result['skeptic']['weighted_total'])
        same=dict(supplied,evidence_ids=['result','duplicate'])
        self.packet['evidence']['duplicate']=dict(self.packet['evidence']['result'])
        result=score_arguments(dict(advocate=same),evidence_registry(self.root,self.packet))
        self.assertEqual(result['advocate']['adjusted']['independence'],49)

    def test_repetition_and_stagnation_stop(self):
        self.j.update(action='second',new_question='새 반증 확인')
        first=self.run_round()
        second=self.run_round(prior=first,max_rounds=8)
        self.assertEqual(second['decision'],'UNCERTAIN')
        self.assertIn('반복',second['stop_reason'])
        modified=dict(self.a,cause='같은 출처로 표현만 바꾸기')
        prior=dict(first,stagnation_count=1)
        self.assertEqual(self.run_round(prior=prior,advocate_arguments=modified,max_rounds=8)['stagnation_count'],2)

    def test_max_rounds(self):
        self.j.update(action='second',new_question='한 번 더')
        self.assertEqual(self.run_round(max_rounds=1)['decision'],'UNCERTAIN')

    def test_api_failure_does_not_manufacture_arguments(self):
        self.j=dict(action='stop',evidence_ids=[],new_question='')
        result=self.run_round(skeptic_arguments=dict(status='timeout',usage=None))
        self.assertEqual(result['decision'],'UNCERTAIN')
        self.assertEqual(result['history'][0]['arguments']['skeptic']['status'],'timeout')

    def test_external_verification_disabled_and_fake_source(self):
        self.packet['evidence']['web']=dict(url='https://invented.invalid')
        self.j['evidence_ids']=['web']
        result=self.run_round()
        self.assertEqual(result['evidence_registry']['web']['status'],'UNVERIFIED')
        self.assertIn('disabled',result['judge_feedback']['external_verification'])
        self.assertEqual(result['decision'],'UNCERTAIN')

    def test_feedback_and_revise_preserved_across_checkpoint_resume(self):
        self.j.update(action='second',new_question='새 반증 질문',debate_assessment=dict(revision_required=True))
        first=evaluate(self.root,self.folder,self.packet,self.a,self.b,self.j)
        self.assertEqual(first['decision'],'REVISE')
        again=evaluate(self.root,self.folder,self.packet,self.a,self.b,self.j)
        self.assertEqual(len(again['history']),1)
        (self.folder/'adversarial.json').unlink() # Crash after SQLite commit, before JSON export.
        recovered=evaluate(self.root,self.folder,self.packet,self.a,self.b,self.j)
        self.assertEqual(len(recovered['history']),1)
        self.assertEqual(recovered['input_key'],first['input_key'])
        self.j=dict(self.j,action='select')
        final=evaluate(self.root,self.folder,self.packet,dict(self.a,cause='반론 반영'),self.b,self.j)
        self.assertEqual(final['round_number'],2)
        self.assertEqual(final['judge_feedback']['previous_feedback_received'],'새 반증 질문')
        self.assertEqual(len(final['history']),2)
        self.assertTrue((self.folder/'adversarial.sqlite').exists())

    def test_source_modified_and_unknown_citations_block(self):
        self.file.write_text('{"fp":0}')
        self.packet['machine_claim']=dict(evidence_id='result',field=['fp'],expected=0)
        self.j.update(action='second',new_question='반증',evidence_ids=['missing'])
        result=self.run_round()
        self.assertEqual(result['decision'],'UNCERTAIN')
        self.assertEqual(result['errors'],['unknown_evidence_id'])

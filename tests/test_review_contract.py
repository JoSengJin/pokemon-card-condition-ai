import copy
import json
import unittest
from unittest.mock import patch
from card_condition import cross_review_contract as contract,cross_review_auto as auto
from card_condition.cross_review_evidence import expand_evidence
from card_condition.experiment_record import read,save,sha
import test_cross_review_high_fixes as fixture


class ContractFlowTest(unittest.TestCase):
    setUp=fixture.HighFixTest.setUp
    backend=fixture.HighFixTest.backend
    gemini=fixture.HighFixTest.gemini
    judge=fixture.HighFixTest.judge
    run_flow=fixture.HighFixTest.run_flow

    def mix_execution_id(self):
        self.packet['failed_executions']={'known-execution-failed':{'status':'failed'}}
        save(self.folder/'packet.json',self.packet);save(self.folder/'result.json',self.result)
        backend=self.backend
        def mixed(*args):
            value,usage,thread=backend(*args)
            if args[1]=='correct':value['failed_hypotheses_checked'].append('known-execution-failed')
            return value,usage,thread
        return mixed

    def test_known_misclassification_reaches_judge_and_separate_gate_without_rewriting_response(self):
        with patch.object(self,'backend',side_effect=self.mix_execution_id()):self.assertEqual(self.run_flow(),2)
        state=read(self.folder/'automation.json');gate=read(self.folder/'development-gate.json')
        self.assertEqual(self.n_calls,1);self.assertTrue(gate['allowed']);self.assertTrue(gate['strict_verdict_valid'])
        self.assertEqual(state['classification_issues']['correct']['execution_failure_ids'],['known-execution-failed'])
        original=read(next(self.folder.glob('codex/correct-*/call.json')))['data']
        self.assertIn('known-execution-failed',original['failed_hypotheses_checked'])
        self.assertIn('correct',dict(self.inputs)['judge']['debate']['classification_issues'])
        count=len(self.codex_calls);self.assertEqual(self.run_flow(),2);self.assertEqual(len(self.codex_calls),count)

    def test_high_scoring_judge_with_unresolved_history_cannot_authorize_development(self):
        self.judge_issues=['仍需核实：不能把执行失败作为假设失败']
        with patch.object(self,'backend',side_effect=self.mix_execution_id()):self.assertEqual(self.run_flow(),0)
        self.assertEqual(self.n_calls,1);self.assertNotIn('Codex:implement',self.order)
        self.assertFalse(read(self.folder/'development-gate.json')['allowed'])

    def test_unknown_or_missing_history_still_blocks_before_judge(self):
        self.verdict['failed_hypotheses_checked'].append('unknown-failure')
        self.assertEqual(self.run_flow(),1);self.assertEqual(self.n_calls,0)
        self.assertNotIn('Codex:implement',self.order)

    def test_missing_required_failed_id_cannot_be_normalized(self):
        verdict=copy.deepcopy(self.verdict);verdict['failed_hypotheses_checked']=[]
        with self.assertRaisesRegex(ValueError,'missing='):contract.classify_history(self.packet,verdict)

    def test_all_agents_receive_identical_core_and_actual_execution_quote(self):
        policy=dict(editable_sources=['card_condition/model.py'],trainer_sources=[],baseline_training_contract=dict(source='card_condition/model.py',source_sha256=sha(self.source),quote='return x',normal_reduction='active-branch'))
        save(self.root/'trusted-experiment.json',policy)
        self.implementation['final_decision']='stop'
        self.assertEqual(self.run_flow(),0)
        inputs=dict(self.inputs)
        cores=[]
        for phase in ('verify','correct','implement'):
            context=inputs[phase]
            if context.get('context_reference_root')=='document':context=expand_evidence(context)
            cores.append(context['shared_core'])
        gemini=json.loads(inputs['Gemini'][inputs['Gemini'].index('{"comparison":'):])
        cores.append(gemini['comparison']['shared_core']);cores.append(inputs['judge']['shared_core'])
        self.assertTrue(all(c==cores[0] for c in cores));self.assertEqual(cores[0]['baseline_training_contract']['normal_reduction'],'active-branch')
        self.assertEqual(len(self.codex_calls),3);self.assertEqual(self.gemini_calls,1);self.assertEqual(self.n_calls,1)

    def test_tampered_core_blocks_before_another_model_request(self):
        gemini=self.gemini
        def tamper(*args):
            result=gemini(*args);path=self.folder/'shared-core.json';value=read(path);value['core']['threshold']=99;save(path,value);return result
        with patch.object(self,'gemini',side_effect=tamper):self.assertEqual(self.run_flow(),1)
        self.assertEqual(len(self.codex_calls),1);self.assertEqual(self.n_calls,0)

    def test_changed_baseline_source_rejected_before_initial_model_request(self):
        save(self.root/'trusted-experiment.json',dict(baseline_training_contract=dict(source='card_condition/model.py',source_sha256='0'*64,quote='return x')))
        self.assertEqual(self.run_flow(),1);self.assertEqual(self.order,[])

    def test_resolving_classification_never_changes_experiment_or_acceptance(self):
        self.mix_execution_id()
        raw=copy.deepcopy(self.verdict);raw['failed_hypotheses_checked'].append('known-execution-failed')
        canonical,issue=contract.classify_history(self.packet,raw)
        self.assertEqual(canonical['experiment'],raw['experiment']);self.assertEqual(canonical['acceptance'],raw['acceptance'])
        self.assertIn('known-execution-failed',raw['failed_hypotheses_checked']);self.assertNotIn('known-execution-failed',canonical['failed_hypotheses_checked'])

    def test_judge_projection_retains_full_evidence_critic_and_current_numeric_rules(self):
        from card_condition.cross_review_nemotron import judge_input
        from card_condition.cross_review_flow import proposal_context
        context=dict(original_proposal=proposal_context(self.verdict),revised_proposal=proposal_context(self.verdict),
            critiques=[dict(id='c',response=self.response)])
        before=copy.deepcopy(context);core=contract.shared_core(self.root,self.folder,self.packet)
        value=expand_evidence(judge_input(self.packet,context,core))
        self.assertEqual(value['evidence']['evidence'],expand_evidence(self.packet['evidence']))
        self.assertEqual(value['debate']['critiques'],context['critiques'])
        self.assertEqual(value['debate']['revised_proposal']['acceptance'],self.verdict['acceptance'])
        self.assertEqual(value['debate']['revised_proposal']['experiment']['smallest_experiment'],self.verdict['experiment']['smallest_experiment'])
        self.assertEqual(context,before)

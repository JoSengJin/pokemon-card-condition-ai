import copy
import unittest
from unittest.mock import patch
from card_condition import cross_review_auto as auto
from card_condition.cross_review_contract import registered_evidence
from card_condition.cross_review_evidence import latest_packet,expand_evidence
from card_condition.cross_review_adversarial import evidence_registry
from card_condition.experiment_record import read,save,sha
import test_cross_review_auto as auto_fixture
import test_cross_review_high_fixes as high_fixture


class ContractErrorsTest(unittest.TestCase):
    setUp=auto_fixture.AutoReviewTest.setUp

    def configure_contract(self):
        contract=dict(source='card_condition/model.py',source_sha256=sha(self.source),quote=self.original)
        save(self.root/'trusted-experiment.json',dict(baseline_training_contract=contract,editable_sources=['card_condition/model.py']))
        return contract

    def test_verified_baseline_id_matches_packet_input_and_validator(self):
        contract=self.configure_contract()
        packet=latest_packet(self.root);save(self.folder/'packet.json',packet)
        value=copy.deepcopy(self.verdict);value['evidence_ids'].append('baseline_training_contract')
        auto.validate_verdict(self.root,dict(packet=packet),value,require_parameter=True)
        context=expand_evidence(auto.review_context(self.root,self.folder,'verify',dict(flow_role='advocate')))
        self.assertIn('baseline_training_contract',context['valid_evidence_ids'])
        self.assertEqual(context['evidence']['evidence']['baseline_training_contract']['summary'],contract)
        self.assertEqual(context['valid_evidence_ids'],sorted(packet['evidence']))
        self.assertEqual(evidence_registry(self.root,packet)['baseline_training_contract']['status'],'SOURCE_VERIFIED')

    def test_source_mismatch_and_conflicting_registration_are_not_whitelisted(self):
        self.configure_contract()
        packet=copy.deepcopy(self.packet);packet['evidence']['baseline_training_contract']={'path':'invented'}
        with self.assertRaisesRegex(ValueError,'Conflicting'):registered_evidence(self.root,packet)
        self.source.write_text('changed source')
        with self.assertRaisesRegex(ValueError,'Shared baseline source changed'):registered_evidence(self.root,self.packet)

    def test_unprovided_baseline_or_unknown_id_is_still_rejected(self):
        value=copy.deepcopy(self.verdict);value['evidence_ids']=['baseline_training_contract','invented']
        errors=auto.verdict_errors(self.root,dict(packet=self.packet),value,require_parameter=True)
        self.assertIn('evidence_ids',{e['check'] for e in errors})
        with self.assertRaises(auto.VerdictValidationError):auto.validate_verdict(self.root,dict(packet=self.packet),value,require_parameter=True)

    def test_independent_contract_faults_are_all_reported_without_approval(self):
        value=copy.deepcopy(self.verdict)
        value['evidence_ids']=['invented'];value['failed_hypotheses_checked']=['wrong-history']
        value['review_claims']['completed_diagnostic_ids']=['wrong-diagnostic']
        value['experiment_parameter']['value']=value['experiment_parameter']['baseline']
        value['acceptance']['require_actual_point_guard']=True
        errors=auto.verdict_errors(self.root,dict(packet=self.packet),value,require_parameter=True)
        self.assertTrue({'evidence_ids','failure_history','completed_diagnostics','experiment_parameter','actual_point_guard'}<={e['check'] for e in errors})
        with self.assertRaises(auto.VerdictValidationError) as caught:auto.validate_verdict(self.root,dict(packet=self.packet),value,require_parameter=True)
        self.assertEqual(caught.exception.errors,errors)

    def test_one_correction_receives_every_discovered_error_and_no_extra_call(self):
        case=high_fixture.HighFixTest('runTest');case.setUp();self.addCleanup(case.doCleanups)
        original=case.backend
        def backend(root,phase,prompt,directory,thread):
            value,usage,identity=original(root,phase,prompt,directory,thread)
            if phase=='verify':
                value['evidence_ids']=['invented'];value['failed_hypotheses_checked']=['wrong-history']
                value['review_claims']['completed_diagnostic_ids']=['wrong-diagnostic']
            else:value['action']='stop'
            return value,usage,identity
        case.backend=backend
        self.assertEqual(case.run_flow(),0)
        context=next(v for phase,v in case.inputs if phase=='correct')
        errors=expand_evidence(context)['correction']['errors']
        self.assertTrue({'evidence_ids','failure_history','completed_diagnostics'}<={e['check'] for e in errors})
        self.assertEqual(case.order,['Codex:verify','Codex:correct'])
        self.assertEqual(case.gemini_calls,0);self.assertEqual(case.n_calls,0)
        self.assertEqual(read(case.folder/'automation.json')['status'],'stopped')

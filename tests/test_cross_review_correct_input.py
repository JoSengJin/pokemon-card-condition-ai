import unittest
from card_condition import cross_review_auto as auto
from card_condition.cross_review_evidence import expand_evidence
from card_condition.experiment_record import save


class CohortGateOnceTest(unittest.TestCase):
    from test_cross_review_auto import AutoReviewTest
    setUp=AutoReviewTest.setUp

    def context(self,result_gate):
        plan=[dict(id='guard',reference_result='artifacts/reference/result.json',acceptance={'max_fn':0,'no_new_errors':True})]
        result=[dict(id='guard',acceptance=result_gate,acceptance_passed=False,comparison=None)]
        evidence=self.packet['evidence']
        evidence['latest_plan']=dict(evidence['latest_plan'],summary=dict(evidence['latest_plan'].get('summary',{}),required_cohorts=plan))
        evidence['latest_result']=dict(evidence['latest_result'],summary=dict(evidence['latest_result'].get('summary',{}),required_cohorts=result))
        save(self.folder/'packet.json',self.packet)
        context=expand_evidence(auto.review_context(self.root,self.folder,'verify',{'flow_role':'advocate'}))
        return context['evidence']['evidence']

    def test_identical_plan_gates_are_sent_once_with_exact_result_gate(self):
        evidence=self.context({'max_fn':0,'no_new_errors':True})
        self.assertIsInstance(evidence['latest_plan']['summary']['required_cohorts'],str)
        self.assertEqual(evidence['latest_result']['summary']['required_cohorts'][0]['acceptance'],{'max_fn':0,'no_new_errors':True})

    def test_different_result_gate_keeps_plan_gates(self):
        evidence=self.context({'max_fn':2,'no_new_errors':True})
        self.assertEqual(evidence['latest_plan']['summary']['required_cohorts'],[{'id':'guard','acceptance':{'max_fn':0,'no_new_errors':True}}])


if __name__=='__main__':
    unittest.main()

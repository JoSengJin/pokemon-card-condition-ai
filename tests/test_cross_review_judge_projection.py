"""The judge gets bounded evidence without losing decision gates."""
import copy
import unittest

from card_condition.cross_review_judge_projection import judge_packet


class JudgePacketTest(unittest.TestCase):
    def test_keeps_current_gates_and_summarizes_old_cohort_rows(self):
        cohort = dict(id='front', comparison={'before': {'fn': 2}, 'after': {'fn': 3}},
                      acceptance={'max_fn': 2}, acceptance_passed=False,
                      error_count=1, errors=[{'id': 'photo-1', 'score': .8}])
        packet = dict(same_evaluation_metrics={'fn': 3}, failed_hypotheses={'old': ['failed_0']},
                      evidence=dict(latest_plan={'path': 'plan.json', 'sha256': 'plan',
                          'summary': {'required_cohorts': [dict(cohort, reference_result='fixed.json')]}},
                          latest_result={'path': 'result.json', 'sha256': 'result',
                              'summary': {'required_cohorts': [cohort]}},
                          failed_0={'path': 'old.json', 'sha256': 'old',
                              'summary': {'failure_reasons': ['new false negative'],
                                          'required_cohorts': [dict(cohort, id='passed', acceptance_passed=True), cohort]}}))
        original = copy.deepcopy(packet)
        view = judge_packet(packet)
        self.assertEqual(packet, original)
        self.assertEqual(view['same_evaluation_metrics'], packet['same_evaluation_metrics'])
        self.assertEqual(view['failed_hypotheses'], packet['failed_hypotheses'])
        self.assertEqual(view['evidence']['latest_result']['summary']['required_cohorts'][0]['comparison'], cohort['comparison'])
        self.assertEqual(view['evidence']['latest_plan']['summary']['required_cohorts'][0]['acceptance'], cohort['acceptance'])
        old = view['evidence']['failed_0']
        self.assertEqual(old['path'], 'old.json')
        self.assertEqual(old['sha256'], 'old')
        self.assertEqual(old['summary']['failure_reasons'], ['new false negative'])
        self.assertEqual(old['summary']['required_cohorts'], [{'id': 'front', 'acceptance_passed': False, 'error_count': 1}])


if __name__ == '__main__':
    unittest.main()

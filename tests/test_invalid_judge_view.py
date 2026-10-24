import unittest
from card_condition.experiment_record import read,save,sha
from card_condition.review_chat import snapshot
import test_review_chat as fixture

class InvalidJudgeViewTest(unittest.TestCase):
    setUp=fixture.ChatTest.setUp
    def test_invalid_judge_body_is_visible_but_not_accepted_and_source_unchanged(self):
        self.state.update(status='judge_unavailable',reason='response_error');save(self.folder/'automation.json',self.state)
        p=self.folder/'nemotron/failed.json';p.parent.mkdir()
        save(p,dict(role='judge',status='error',error_kind='response_error',attempted=True,raw_response='{"decision":"reject_experiment","rationale":"공개 반론 원문","evidence_ids":["bad-id"]}',validation_errors=['judge_evidence'],usage={'total_tokens':7}))
        before=sha(p);data=snapshot(self.root,'abc123');judge=next(e for e in data['events'] if e['agent']=='NVIDIA')
        self.assertEqual(judge['message']['rationale'],'공개 반론 원문');self.assertEqual(judge['status'],'response_error');self.assertTrue(judge['unvalidated_response'])
        self.assertEqual(data['stages'][3]['status'],'response_error');self.assertIsNone(data['acceptance_passed']);self.assertEqual(sha(p),before)

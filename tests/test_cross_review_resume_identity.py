"""A bounded excerpt must not turn a saved review into a new request."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from card_condition import cross_review_manual as manual


class ResumeIdentityTest(unittest.TestCase):
    def test_truncated_excerpt_reuses_critic_but_source_changes_do_not(self):
        config = {'model': 'free-model', 'prompt_version': manual.CRITIC_VERSION,
                  'max_calls': 3, 'max_output_tokens': 4096}
        packet = dict(source_mode='project-latest', error_cases=[],
                      same_evaluation_metrics={}, latest_result='result.json', failed_hypotheses={},
                      evidence={'related_code': {'path': 'code.diff', 'sha256': 'source-a',
                          'summary': {'budget_truncated': True, 'excerpt': 'full excerpt'}}})
        changed = copy.deepcopy(packet)
        changed['evidence']['related_code']['summary']['excerpt'] = 'full excer'
        self.assertEqual(manual.review_identity(packet, config), manual.review_identity(changed, config))
        shorter = copy.deepcopy(changed)
        self.assertEqual(packet['evidence']['related_code']['summary']['excerpt'], 'full excerpt')
        changed['evidence']['related_code']['sha256'] = 'source-b'
        self.assertNotEqual(manual.review_identity(packet, config), manual.review_identity(changed, config))
        changed = copy.deepcopy(packet)
        changed['evidence']['related_code']['summary']['budget_truncated'] = False
        changed['evidence']['related_code']['summary']['excerpt'] = 'different code'
        self.assertNotEqual(manual.review_identity(packet, config), manual.review_identity(changed, config))

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base = root / 'artifacts/manual-cross-review'
            base.mkdir(parents=True)
            settings = root / 'artifacts/cross-review-20261019/local-config.json'
            settings.parent.mkdir()
            settings.write_text(json.dumps(config))
            for name, source, status in (('saved', packet, 'critique_recorded'), ('newer', shorter, 'proposal_pending')):
                folder = base / name
                folder.mkdir()
                (folder / 'packet.json').write_text(json.dumps(source))
                (folder / 'config.json').write_text(json.dumps(config))
                (folder / 'result.json').write_text(json.dumps({'status': status, 'response': {'cause': '검토'}, 'pending': []}))
            with (patch.object(manual, 'ROOT', root), patch.object(manual, 'latest_packet', return_value=packet),
                  patch.object(manual, 'validate'), patch.object(manual, 'response_ok', return_value=True),
                  patch.object(manual, 'korean_response_ok', return_value=True),
                  patch('card_condition.cross_review_auto.run_auto', return_value=0) as run,
                  patch.object(manual, 'next_steps')):
                self.assertEqual(manual.review(base, automatic=True), 0)
            self.assertEqual(json.loads((base / 'active.json').read_text())['directory'], str(base / 'saved'))
            run.assert_called_once()


if __name__ == '__main__':
    unittest.main()

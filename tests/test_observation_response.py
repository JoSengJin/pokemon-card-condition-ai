import copy
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from observation_loop_fixture import fixture, response_fixture
from card_condition.observation_page import render_page


class ObservationResponseTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_response"), "response validator missing")
        self.api = importlib.import_module("card_condition.observation_response")
        self.packet, self.assets = fixture()
        self.body = response_fixture(self.packet)

    def test_four_states_and_exact_original_notes(self):
        for state in ("unreviewed", "normal", "defect", "unassessable"):
            self.body['entries'][0].update(state=state, note='  한글 원문\n ')
            event = copy.deepcopy(self.body['observations']['events'][-1])
            event.update(event='change', entry_id='r1', state=state)
            self.body['observations']['events'] = [event, self.body['observations']['events'][-1]]
            before = copy.deepcopy(self.body)
            result = self.api.validate_response(self.packet, self.body)
            self.assertEqual(result['missing_entry_ids'], [])
            self.assertTrue(result['display_verified'])
            self.assertEqual(self.body, before)
        self.body['entries'] = []
        result = self.api.validate_response(self.packet, self.body)
        self.assertEqual(result['missing_entry_ids'], ['r1'])

    def test_rejects_invalid_identity_state_metadata_and_scope(self):
        for key, value in (("state", "unknown"), ("state", None), ("photo_sha256", "0" * 64),
                           ("entry_id", "r2"), ("note", {"target": 1}), ("score", 0.9)):
            with self.subTest(key=key, value=value):
                body = copy.deepcopy(self.body); body['entries'][0][key] = value
                with self.assertRaises(ValueError): self.api.validate_response(self.packet, body)
        for key, value in (("kind", "crop_response"), ("collection_status", "executable"), ("data_origin", "human"),
                           ("packet_id", "0" * 64), ("observation_mode", "A"), ("scope", "candidate_box")):
            with self.subTest(key=key):
                body = copy.deepcopy(self.body); body[key] = value
                with self.assertRaises(ValueError): self.api.validate_response(self.packet, body)
        self.body['entries'].append(copy.deepcopy(self.body['entries'][0]))
        with self.assertRaises(ValueError): self.api.validate_response(self.packet, self.body)

    def test_observations_bind_profile_proofs_events_and_incomplete_display(self):
        for branch, key, value in (("profile", "profile_id", "changed"), ("profile", "zoom_allowed", 1), ("asset", "measured_sha256", "0" * 64),
                                   ("asset", "element_ids", ["other"]), ("event", "at", "bad"),
                                   ("event", "device_pixel_ratio", True), ("event", "entry_id", {"score": 1}), ("event", "score", 0.9)):
            with self.subTest(branch=branch, key=key):
                body = copy.deepcopy(self.body)
                node = body['observations']['profile'] if branch == 'profile' else body['observations']['assets' if branch == 'asset' else 'events'][0]
                node[key] = value
                with self.assertRaises(ValueError): self.api.validate_response(self.packet, body)
        self.body['observations']['assets'][0]['verified'] = False
        self.assertFalse(self.api.validate_response(self.packet, self.body)['display_verified'])
        self.body = response_fixture(self.packet)
        self.body['observations']['events'][0]['image_sizes'][0]['current_src_matches'] = False
        self.assertFalse(self.api.validate_response(self.packet, self.body)['display_verified'])

    def test_node_four_state_events_and_export_validate_in_python(self):
        with tempfile.TemporaryDirectory() as folder:
            page, raw = Path(folder)/'synthetic.html', Path(folder)/'synthetic-response.json'
            page.write_text(render_page(self.packet, self.assets))
            result = subprocess.run(['node','tests/observation_response.test.cjs',str(page),str(raw)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            body=json.loads(raw.read_bytes())
            self.assertEqual(body['entries'][0]['state'],'defect')
            self.assertEqual(body['entries'][0]['note'],'  합성 메모\n ')
            self.assertTrue(self.api.validate_response(self.packet,body)['display_verified'])

    def test_contradictory_history_never_verifies_display_or_answer(self):
        for scenario in ('invalidate', 'missing_change', 'wrong_last_change'):
            with self.subTest(scenario=scenario):
                body = response_fixture(self.packet)
                event = copy.deepcopy(body['observations']['events'][0])
                if scenario == 'invalidate':
                    event['event'] = 'invalidate'
                    body['observations']['events'].insert(0, event)
                else:
                    body['entries'][0]['state'] = 'normal'
                    if scenario == 'wrong_last_change':
                        event.update(event='change', entry_id='r1', state='defect')
                        body['observations']['events'].insert(0, event)
                self.assertFalse(self.api.validate_response(self.packet, body)['display_verified'])

"""Regression inputs are generated fixtures only, never datasets or human labels."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from observation_loop_fixture import fixture, response_fixture
from card_condition.observation_packet import packet_digest
from card_condition.observation_page import render_page
from card_condition.observation_response import validate_response
from card_condition.observation_receipt import capture_receipt, load_receipts, receipt_digest


class ObservationP2Tests(unittest.TestCase):
    def setUp(self):
        self.packet, self.assets = fixture()
        self.context = dict(data_origin="synthetic_fixture", source_type="synthetic_fixture", reviewer_id="synthetic-reviewer",
                            session_id="synthetic-session", received_at="2026-11-17T00:00:01Z")

    def test_explicit_profile_values_match_and_nulls_stay_unknown(self):
        unknown = copy.deepcopy(self.packet)
        self.assertTrue(validate_response(self.packet,response_fixture(self.packet))['display_verified'])
        self.assertIsNone(self.packet['profile']['viewport_css'])
        self.assertEqual(self.packet,unknown)
        packet=copy.deepcopy(self.packet)
        packet['profile'].update(viewport_css=[800,600],device_pixel_ratio=1,image_css=[100,100])
        packet['packet_id']=packet_digest(packet)
        body=response_fixture(packet)
        for image in body['observations']['events'][0]['image_sizes']: image['css_size']=[100,100]
        self.assertTrue(validate_response(packet,body)['display_verified'])
        for field, value in (('viewport_css',[320,240]),('device_pixel_ratio',2),('image_css',[10,10])):
            with self.subTest(field=field):
                changed=copy.deepcopy(body)
                if field=='image_css': changed['observations']['events'][0]['image_sizes'][0]['css_size']=value
                else: changed['observations']['events'][0][field]=value
                self.assertFalse(validate_response(packet,changed)['display_verified'])

    def test_bad_change_time_display_cannot_be_repaired_by_good_export(self):
        for field,value in (('current_src_matches',False),('natural_size',[9,8]),('css_size',[0,0]),('missing',None)):
            with self.subTest(field=field):
                body=response_fixture(self.packet)
                body['entries'][0].update(state='defect',note='  그대로\n ')
                change=copy.deepcopy(body['observations']['events'][0])
                change.update(event='change',entry_id='r1',state='defect')
                if field=='missing': change['image_sizes'].pop()
                else: change['image_sizes'][0][field]=value
                body['observations']['events'].insert(0,change)
                before=copy.deepcopy(body)
                self.assertFalse(validate_response(self.packet,body)['display_verified'])
                self.assertEqual(body,before)

    def test_browser_profile_gate_and_bad_change_are_latched(self):
        packet=copy.deepcopy(self.packet)
        packet['profile'].update(viewport_css=[800,600],device_pixel_ratio=1,image_css=[100,100])
        packet['packet_id']=packet_digest(packet)
        with tempfile.TemporaryDirectory() as folder:
            page=Path(folder)/'synthetic.html';page.write_text(render_page(packet,self.assets))
            result=subprocess.run(['node','tests/observation_profile.test.cjs',str(page)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('profile synthetic checks passed',result.stdout)

    def test_receipt_status_and_reasons_cannot_contradict_source_or_summary(self):
        for scenario in ('ai_status','unknown_status','pending_status','missing_status','ai_reason','ai_conflict'):
            with self.subTest(scenario=scenario),tempfile.TemporaryDirectory() as folder:
                body=response_fixture(self.packet)
                source='ai' if scenario.startswith('ai_') else 'unknown' if scenario.startswith('unknown_') else 'synthetic_fixture'
                if scenario=='pending_status': body['observations']['assets'][0]['verified']=False
                if scenario=='missing_status': body['entries']=[]
                raw=json.dumps(body).encode();context=dict(self.context,source_type=source)
                record=capture_receipt(self.packet,raw,context,folder)
                if scenario=='ai_reason': record['reasons']=['collection_not_authorized']
                elif scenario=='ai_conflict': record['conflicts']=['r1']
                else: record['status']='synthetic_only'
                record['receipt_sha256']=receipt_digest(record)
                (Path(folder)/record['receipt_id']/'receipt.json').write_text(json.dumps(record))
                with self.assertRaises(ValueError): load_receipts(self.packet,folder)
                with self.assertRaises(ValueError): capture_receipt(self.packet,raw,context,folder)
                self.assertEqual((Path(folder)/record['receipt_id']/'raw.bin').read_bytes(),raw)

    def test_valid_classifications_and_reception_preserve_raw_and_blocked_flags(self):
        for source,pending,expected in (('synthetic_fixture',False,'synthetic_only'),('synthetic_fixture',True,'pending_observation'),
                                        ('ai',False,'pending_provenance'),('unknown',True,'pending_provenance')):
            with self.subTest(source=source,pending=pending),tempfile.TemporaryDirectory() as folder:
                body=response_fixture(self.packet)
                if pending: body['observations']['assets'][0]['verified']=False
                raw=(' \n'+json.dumps(body)+'\n ').encode();context=dict(self.context,source_type=source)
                record=capture_receipt(self.packet,raw,context,folder)
                self.assertEqual(record['status'],expected)
                self.assertEqual(load_receipts(self.packet,folder)['receipts'][0],record)
                self.assertEqual(capture_receipt(self.packet,raw,context,folder),record)
                self.assertFalse(record['human_truth']);self.assertFalse(record['eligible_for_collection'])
                self.assertEqual(record['collection_status'],'not_executable_pending_collection_contract_approval')
                self.assertEqual((Path(folder)/record['receipt_id']/'raw.bin').read_bytes(),raw)

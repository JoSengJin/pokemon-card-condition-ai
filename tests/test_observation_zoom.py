import copy
import importlib
import importlib.util
import unittest
from pathlib import Path
import subprocess
import tempfile
from card_condition.observation_page import render_page
from card_condition.observation_collection_contract import contract_digest
from observation_loop_fixture import fixture
from test_observation_collection_contract import contract_fixture


def zoom_events(packet):
    asset=packet["entries"][0]["assets"][1]
    event=dict(seq=0,event="initial",at="2026-11-18T00:00:00Z",entry_id="r1",ref=asset["ref"],asset_sha256=asset["sha256"],
               scale=1,pan=[0,0],source_size=asset["size"],base_css=[64,64],transformed_css=[64,64],source_matches=True)
    last=copy.deepcopy(event);last.update(seq=1,event="export")
    return [event,last]


class ZoomTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_zoom"),"zoom validator missing")
        self.api=importlib.import_module("card_condition.observation_zoom")
        self.packet,_=fixture();self.contract=contract_fixture(complete=True)

    def test_h_initial_change_export_and_a_has_no_zoom(self):
        events=zoom_events(self.packet)
        self.assertTrue(self.api.validate_zoom_log(self.contract,events,self.packet))
        events.insert(1,dict(events[0],event="change",seq=1,scale=2,pan=[1,-1],transformed_css=[128,128]))
        events[2].update(seq=2,scale=2,pan=[1,-1],transformed_css=[128,128])
        self.assertTrue(self.api.validate_zoom_log(self.contract,events,self.packet))
        a=contract_fixture("A");packet,_=fixture("A")
        self.assertTrue(self.api.validate_zoom_log(a,[],packet))
        with self.assertRaises(ValueError):self.api.validate_zoom_log(a,events,packet)

    def test_missing_policy_binding_or_restored_failure_never_verifies(self):
        for field,value in (("source_matches",False),("transformed_css",[65,64]),("source_size",[9,9]),("scale",3),("pan",[99,0])):
            with self.subTest(field=field):
                events=zoom_events(self.packet);events[0][field]=value
                self.assertFalse(self.api.validate_zoom_log(self.contract,events,self.packet))
        self.assertFalse(self.api.validate_zoom_log(contract_fixture(),zoom_events(self.packet),self.packet))
        self.assertFalse(self.api.validate_zoom_log(self.contract,[],self.packet))

    def test_bad_identity_types_and_history_rejected(self):
        for key,value in (("seq",True),("entry_id","r999"),("ref","assets/wrong.png"),("scale",True),("at","bad"),("unexpected",1)):
            with self.subTest(key=key):
                events=zoom_events(self.packet);events[0][key]=value
                with self.assertRaises(ValueError):self.api.validate_zoom_log(self.contract,events,self.packet)

    def test_dom_stub_zoom_preserves_base_gate_and_latches_bad_lens(self):
        c=contract_fixture();c["zoom_policy"].update(scale_min=1,scale_max=2,pan_x_limit=8,pan_y_limit=8)
        c["contract_id"]=contract_digest(c);packet,assets=fixture()
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"page.html";p.write_text(render_page(packet,assets,collection_contract=c))
            r=subprocess.run(["node","tests/observation_zoom.test.cjs",str(p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)

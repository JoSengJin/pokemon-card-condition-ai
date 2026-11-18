import copy
import unittest
from observation_loop_fixture import fixture
from card_condition.observation_packet import validate_packet
import importlib.util
import importlib


def contract_fixture(mode="H", complete=False):
    api=importlib.import_module("card_condition.observation_collection_contract")
    packet, _ = fixture(mode)
    contract = dict(schema_version=2,kind="synthetic_collection_contract",contract_id="",spec_sha256="b"*64,
        packet_id=packet["packet_id"],data_origin="synthetic_fixture",collection_status=packet["collection_status"],
        human_truth=False,eligible_for_collection=False,display_profile=copy.deepcopy(packet["profile"]),
        zoom_policy=dict(scale_min=None,scale_max=None,pan_x_limit=None,pan_y_limit=None),
        assignment_ref=None,seal_policy_ref=None,access_policy_ref=None)
    if complete:
        contract["display_profile"].update(viewport_css=[800,600],image_css=[64,64],device_pixel_ratio=1)
        contract["zoom_policy"].update(scale_min=1,scale_max=2,pan_x_limit=8,pan_y_limit=8)
        for key in ("assignment_ref","seal_policy_ref","access_policy_ref"): contract[key]="synthetic-"+key
    contract["contract_id"]=api.contract_digest(contract)
    return contract


class CollectionContractTests(unittest.TestCase):
    def setUp(self):
        global api
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_collection_contract"), "collection contract implementation missing")
        api=importlib.import_module("card_condition.observation_collection_contract")

    def test_unknowns_and_complete_fixture_never_authorize_collection(self):
        for complete in (False, True):
            c=contract_fixture(complete=complete);before=copy.deepcopy(c)
            result=api.readiness(c)
            self.assertEqual(result["synthetic_ready"],complete)
            self.assertFalse(result["collection_ready"])
            self.assertFalse(result["human_truth"]);self.assertFalse(result["eligible_for_collection"])
            self.assertIn("actual_collection_not_authorized",result["missing"])
            self.assertEqual(c,before)
            if not complete:self.assertIsNone(c["display_profile"]["viewport_css"])

    def test_tampering_guards_unknown_fields_and_invalid_types(self):
        c=contract_fixture()
        for key,value in (("data_origin","human"),("human_truth",True),("eligible_for_collection",True),
                          ("schema_version",True),("unknown",1),("assignment_ref"," "),("spec_sha256","bad")):
            with self.subTest(key=key):
                b=copy.deepcopy(c);b[key]=value;b["contract_id"]=api.contract_digest(b)
                with self.assertRaises(ValueError):api.validate_collection_contract(b)
        for field,value in (("scale_min",True),("scale_max",float("inf")),("pan_x_limit",-1)):
            with self.subTest(field=field):
                b=contract_fixture(complete=True);b["zoom_policy"][field]=value
                if value!=float("inf"):b["contract_id"]=api.contract_digest(b)
                with self.assertRaises(ValueError):api.validate_collection_contract(b)
        b=contract_fixture(complete=True);b["zoom_policy"].update(scale_min=2,scale_max=3);b["contract_id"]=api.contract_digest(b)
        with self.assertRaises(ValueError):api.validate_collection_contract(b)
        c["assignment_ref"]="tampered"
        with self.assertRaises(ValueError):api.validate_collection_contract(c)

    def test_v2_is_not_a_v1_packet(self):
        with self.assertRaises(ValueError):validate_packet(contract_fixture())

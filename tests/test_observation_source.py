import copy
import importlib
import importlib.util
import unittest
from collection_runtime_fixture import candidate_fixture


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_source"),"source validator missing")
        self.api=importlib.import_module("card_condition.observation_source")
        self.p,self.a,self.c,self.body,self.context,self.assignment=candidate_fixture()

    def test_synthetic_assignment_match_is_never_human_truth(self):
        before=copy.deepcopy((self.context,self.assignment))
        self.assertTrue(self.api.validate_source_context(self.context,self.assignment))
        self.assertEqual(before,(self.context,self.assignment))
        c=dict(self.context,assignment_id=None)
        self.assertFalse(self.api.validate_source_context(c,None))

    def test_real_source_and_mismatched_custody_rejected(self):
        for key,value in (("source_type","human"),("session_id","other"),("rater_id","other"),("received_at","bad"),("extra",True)):
            with self.subTest(key=key):
                c=dict(self.context);c[key]=value
                with self.assertRaises(ValueError):self.api.validate_source_context(c,self.assignment)
        a=dict(self.assignment,evidence_origin="human")
        with self.assertRaises(ValueError):self.api.validate_source_context(self.context,a)

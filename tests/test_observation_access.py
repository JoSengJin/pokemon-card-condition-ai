import importlib
import importlib.util
import unittest
from collection_runtime_fixture import candidate_fixture,access_fixture


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("card_condition.observation_access"),"access policy missing")
        self.api=importlib.import_module("card_condition.observation_access")
        _,_,self.c,_,_,_=candidate_fixture();self.policy,self.actors=access_fixture(self.c)
        self.state=dict(contract_id=self.c["contract_id"],sealed=True,released=False,quarantined=False,freeze_ref=None)

    def test_roles_and_release_are_logical_not_actual_access(self):
        self.assertFalse(self.api.authorize("custodian","read_raw",self.state,self.policy)["allowed"])
        self.assertFalse(self.api.authorize(self.actors["developer"],"read_raw",self.state,self.policy)["allowed"])
        self.assertFalse(self.api.authorize(self.actors["evaluator"],"read_evaluation",self.state,self.policy)["allowed"])
        for state in (dict(self.state,released=True,freeze_ref="fixture-freeze"),):
            result=self.api.authorize(self.actors["evaluator"],"read_evaluation",state,self.policy)
            self.assertTrue(result["allowed"]);self.assertFalse(result["actual_access_verified"])
            self.assertFalse(self.api.authorize(self.actors["evaluator"],"read_evaluation",dict(state,quarantined=True),self.policy)["allowed"])
        fake=dict(self.actors["developer"],role="custodian")
        self.assertFalse(self.api.authorize(fake,"read_raw",self.state,self.policy)["allowed"])

    def test_aggregate_does_not_disclose_receipt_or_photo_ids(self):
        records=[dict(status="pending_observation",receipt_id="secret",photo_id="private",response={"note":"private"})]
        result=self.api.aggregate_projection(self.actors["developer"],self.state,self.policy,records)
        self.assertEqual(result,{"receipt_count":1,"status_counts":{"pending_observation":1},"quarantined":False})
        self.assertNotIn("secret",str(result));self.assertNotIn("private",str(result))

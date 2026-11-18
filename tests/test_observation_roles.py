import unittest
from readiness_fixture import role_contract
from card_condition.observation_roles import overlap_findings, validate_role_contract

MUTATIONS = (("developer", "receives", ["final_eval_item"]),
             ("evaluator", "sends_to_developer", ["lineage_map"]),
             ("custodian", "sends_to_developer", ["raw_response", "memo"]),
             ("automation", "creates_human_truth", True))


class RoleContractTests(unittest.TestCase):
    def test_undecided_values_stay_null(self):
        c = role_contract()
        validate_role_contract(c)
        self.assertIsNone(c["roles"]["custodian"]["principals"])
        self.assertTrue(all(v is None for v in c["roles"]["custodian"]["channels"].values()))

    def test_protected_payloads_and_truth_claims_rejected(self):
        for role, key, value in MUTATIONS:
            c = role_contract()
            c["roles"][role][key] = value
            with self.assertRaises(ValueError):
                validate_role_contract(c)
        for edit in (dict(actual_access_verified=True), dict(data_origin="real_files")):
            with self.assertRaises(ValueError):
                validate_role_contract(dict(role_contract(), **edit))
        c = role_contract()
        c["roles"]["developer"]["channels"]["email"] = "allow"
        with self.assertRaises(ValueError):
            validate_role_contract(c)

    def test_overlap_keeps_dependence_note(self):
        c = role_contract()
        c["roles"]["evaluator"]["principals"] = ["dev-fixture"]
        self.assertEqual([(f["principal"], f["independent"]) for f in overlap_findings(c)], [("dev-fixture", False)])
        self.assertEqual(overlap_findings(role_contract()), [])

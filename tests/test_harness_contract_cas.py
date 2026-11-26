"""작업 계약 검증·task_key와 내용 주소 저장소(CAS) 시험(합성 시험, 모델 성능 근거 아님)."""
import os
import tempfile
import unittest

from harness import cas, contract
from tests.test_harness_support import make_contract


class ContractTest(unittest.TestCase):
    def test_valid_contract_key_is_stable_and_ignores_expected_minutes(self):
        task = make_contract()
        self.assertEqual(contract.validate_contract(task), task)
        key = contract.task_key(task)
        self.assertRegex(key, r"^[0-9a-f]{64}$")
        self.assertEqual(key, contract.task_key(dict(task, expected_minutes=45)))
        self.assertNotEqual(key, contract.task_key(make_contract(tag="b")))
        self.assertNotEqual(contract.new_run_id(), contract.new_run_id())

    def test_rejects_unknown_missing_and_wrongly_typed_fields(self):
        bad = [dict(make_contract(), surprise=1), {k: v for k, v in make_contract().items() if k != "risk"},
               dict(make_contract(), needs_llm="no"), dict(make_contract(), escalation_level=True),
               dict(make_contract(), retry_policy={"max_transient_retries": 3}),
               dict(make_contract(), depends_on=["not-a-key"]), "not a dict"]
        for task in bad:
            with self.subTest(task=task), self.assertRaises(contract.ContractError):
                contract.validate_contract(task)

    def test_rejects_empty_duplicate_and_unsafe_outputs(self):
        for outputs in ([], ["a", "a"], ["/abs"], ["../up"], ["a/../b"], [""]):
            with self.subTest(outputs=outputs), self.assertRaises(contract.ContractError):
                contract.validate_contract(make_contract(outputs=outputs))


class CasTest(unittest.TestCase):
    def test_put_get_roundtrip_and_idempotent_put(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.bin")
            with open(src, "wb") as handle:
                handle.write(b"payload")
            sha = cas.put(os.path.join(tmp, "cas"), src)
            self.assertEqual(sha, cas.put(os.path.join(tmp, "cas"), src))
            self.assertTrue(cas.has(os.path.join(tmp, "cas"), sha))
            dest = os.path.join(tmp, "x", "restored.bin")
            cas.get(os.path.join(tmp, "cas"), sha, dest)
            with open(dest, "rb") as handle:
                self.assertEqual(handle.read(), b"payload")

    def test_corrupt_blob_is_not_served_and_put_repairs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, root = os.path.join(tmp, "src.bin"), os.path.join(tmp, "cas")
            with open(src, "wb") as handle:
                handle.write(b"payload")
            sha = cas.put(root, src)
            with open(cas.blob_path(root, sha), "ab") as handle:
                handle.write(b"x")
            self.assertFalse(cas.has(root, sha))
            with self.assertRaises(cas.CasError):
                cas.get(root, sha, os.path.join(tmp, "out.bin"))
            self.assertEqual(cas.put(root, src), sha)
            self.assertTrue(cas.has(root, sha))

    def test_rejects_malformed_sha_instead_of_building_a_path(self):
        for sha in ("../../etc/passwd", "ab", None, "G" * 64):
            with self.subTest(sha=sha), self.assertRaises(cas.CasError):
                cas.blob_path("/tmp/cas", sha)

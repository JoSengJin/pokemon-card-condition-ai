"""해시 체인 장부 시험(T-ledger): 줄 변조·중간 삭제·순서 변경·꼬리 잘림을 위치와 함께 감지."""
import os
import tempfile
import unittest

from harness import ledger


def make_ledger(tmp, count=5):
    path = os.path.join(tmp, "ledger.jsonl")
    for i in range(count):
        ledger.append(path, 100.0 + i, "event%d" % i, {"n": i})
    return path


def rewrite(path, edit):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(edit(lines)) + "\n")


class LedgerTest(unittest.TestCase):
    def test_append_chains_and_verifies_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp)
            self.assertEqual(ledger.verify(path, expected_tail=ledger.tail(path)), [])
            self.assertEqual(ledger.verify(os.path.join(tmp, "absent.jsonl")), [])

    def test_line_tamper_is_detected_at_its_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp)
            rewrite(path, lambda ls: ls[:2] + [ls[2].replace('"n": 2', '"n": 99')] + ls[3:])
            found = ledger.verify(path)
            self.assertEqual([(p["line"], p["seq"], p["problem"]) for p in found], [(3, 2, "hash_mismatch")])

    def test_middle_deletion_and_reordering_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp)
            rewrite(path, lambda ls: ls[:2] + ls[3:])
            found = ledger.verify(path)
            self.assertEqual({(p["line"], p["seq"]) for p in found}, {(3, 3)})  # 삭제 다음 줄에서 발견
            self.assertEqual({p["problem"] for p in found}, {"seq_mismatch", "prev_mismatch"})
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp)
            rewrite(path, lambda ls: [ls[0], ls[2], ls[1]] + ls[3:])
            self.assertEqual({p["line"] for p in ledger.verify(path)}, {2, 3, 4})

    def test_tail_truncation_is_detected_only_with_an_external_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp)
            copied_tail = ledger.tail(path)
            rewrite(path, lambda ls: ls[:-1])
            self.assertEqual(ledger.verify(path), [])  # 복제본 없이는 알 수 없다(문서화된 한계)
            found = ledger.verify(path, expected_tail=copied_tail)
            self.assertEqual([p["problem"] for p in found], ["tail_mismatch"])
            self.assertEqual(found[0]["seq"], 3)

    def test_append_refuses_to_extend_a_damaged_tail_and_flags_garbage(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = make_ledger(tmp, 3)
            rewrite(path, lambda ls: ls[:-1] + [ls[-1].replace('"n": 2', '"n": 7')])
            with self.assertRaises(ledger.LedgerError):
                ledger.append(path, 1.0, "late", {})
            rewrite(path, lambda ls: ls + ["not json", ""])
            self.assertEqual([p["problem"] for p in ledger.verify(path) if p["problem"] == "unparseable"],
                             ["unparseable", "unparseable"])

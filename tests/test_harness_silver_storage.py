"""장부 줄 나누기(U+2028·U+2029·U+0085)와 CAS 읽기 실패. 합성 자료이며 장부·CAS의 공개 함수만 쓴다."""
import os
import tempfile
import unittest

from harness import cas, ledger, silver_store

ODD = "a b c\u0085d"  # ensure_ascii=False로 그대로 기록되고 str.splitlines()는 줄로 나누는 문자
# 수정 전(805d9c7) ledger.append가 만든 두 줄 그대로: 해시·형식이 바뀌지 않았음을 고정한다
OLD = ('{"data": {"n": 1, "text": "한글\\n줄바꿈 \\t \\" \\\\"}, "event": "first", "hash": "674426180844f4c672a7c2010340411afdb44f63fb62'
       'c4bc48ce86e398e2ad90", "prev": "0000000000000000000000000000000000000000000000000000000000000000", "seq": 0, "ts": 100.0}\n'
       '{"data": {"list": [1, null, true]}, "event": "second", "hash": "2e5e5c83b625131adacfd3f2d7a19144ab3e46daf3afc5dfc98b16e471a5f'
       'd70", "prev": "674426180844f4c672a7c2010340411afdb44f63fb62c4bc48ce86e398e2ad90", "seq": 1, "ts": 101.5}\n')


def write(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


class LedgerLineTest(unittest.TestCase):
    def test_unicode_line_separators_survive_append_verify_and_further_appends(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, silver_store.STORE)
            for n in range(3):  # 두 번째부터는 이상 문자가 든 마지막 줄 뒤에 이어 쓴다
                entry = silver_store.append(root, ODD, "e" + ODD, {ODD: [ODD, n]})
                self.assertEqual((n, []), (entry["seq"], ledger.verify(path, entry["hash"])))
                self.assertEqual(entry["hash"], ledger.tail(path))
            self.assertEqual([[ODD, 0], [ODD, 1], [ODD, 2]], [e["data"][ODD] for e in silver_store.load(root)])

    def test_a_ledger_written_by_the_old_code_still_verifies_and_can_be_extended(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.jsonl")
            write(path, OLD)
            self.assertEqual([], ledger.verify(path, "2e5e5c83b625131adacfd3f2d7a19144ab3e46daf3afc5dfc98b16e471a5fd70"))
            self.assertEqual(2, ledger.append(path, 102.0, "third", {})["seq"])
            with open(path, "r", encoding="utf-8") as handle:
                self.assertTrue(handle.read().startswith(OLD))  # 앞 줄은 그대로
            self.assertEqual([], ledger.verify(path))
            write(path, OLD.replace("\n", "\r\n"))  # 텍스트 모드의 줄바꿈 변환은 이전과 같다
            self.assertEqual([], ledger.verify(path))

    def test_damaged_blank_and_cut_lines_are_still_refused(self):
        first, second = OLD.split("\n")[:2]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "l.jsonl")
            for text in (OLD + "\n", OLD + "not json\n", OLD + second[:40], OLD + " \n", "\n",
                         first + " " + second + "\n", OLD[:-1] + " \n"):
                write(path, text)
                self.assertIn("unparseable", [p["problem"] for p in ledger.verify(path)], repr(text[-30:]))
                with self.assertRaises(ledger.LedgerError, msg=repr(text[-30:])):
                    ledger.append(path, 1.0, "late", {})
            write(path, "")
            self.assertEqual(([], ledger.GENESIS), (ledger.verify(path), ledger.tail(path)))
            self.assertEqual(0, ledger.append(path, 1.0, "first", {})["seq"])


class CasReadTest(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, "root는 읽기 권한 제거를 무시한다")
    def test_an_unreadable_blob_is_a_cas_error_not_a_permission_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, root = os.path.join(tmp, "src.bin"), os.path.join(tmp, "cas")
            write(src, "payload")
            sha = cas.put(root, src)
            os.chmod(cas.blob_path(root, sha), 0)
            try:
                with self.assertRaises(cas.CasError):
                    cas.get(root, sha, os.path.join(tmp, "out.bin"))
                self.assertEqual([os.path.join(tmp, "out.bin")], cas.restore(root, [(sha, os.path.join(tmp, "out.bin"))]))
            finally:
                os.chmod(cas.blob_path(root, sha), 0o600)
            self.assertFalse(os.path.exists(os.path.join(tmp, "out.bin")))


if __name__ == "__main__":
    unittest.main()

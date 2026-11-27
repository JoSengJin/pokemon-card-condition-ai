"""형식 거절(실제 훅 프로세스)과 발급 규칙."""
import hashlib
import json
import os
import tempfile
import unittest
from unittest import mock

from harness import gold_issue, gold_parse, gold_store, ledger
from tests.test_harness_gold_support import CRITERIA, hook, issue, paste, stored, zones
from tools.self_agreement import answers


class GoldRejectTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.meta = issue(self.root)

    def test_format_errors_rejected_without_consuming_nonce(self):
        meta, good = self.meta, paste(self.meta)
        cases = {
            "duplicate_key": [good + "\nz2=결함", good + "\n# nonce=" + meta["nonce"], good + "\nz2=정상"],
            "unknown_value": [paste(meta, ["정상", "미세"]), paste(meta, ["정상", ""]), paste(meta, ["정상|2", "정상"]),
                              paste(meta, ["정상", "정 상"])],
            "unknown_line": ["내 답이야\n" + good, good + "\n끝", good + "\n# 메모=급함", good + "\nz02=정상", good + "\nz0=정상",
                             good.replace("z2=정상", "z2 정상"), "```\n" + good + "\n```"],
            "zone_mismatch": [paste(meta, ["정상"]), paste(meta, ["정상"] * 3)],
            "missing_line": [paste(meta, 화면=None), paste(meta, nonce=None), paste(meta, 제출시각=None), paste(meta, [])],
            "bad_screen_id": [paste(meta, 화면="A|B")],
            "bad_nonce_format": [paste(meta, nonce=meta["nonce"][:-1]), paste(meta, nonce="G" * 32),
                                 paste(meta, nonce=meta["nonce"] + "0")],
            "bad_submitted_at": [paste(meta, 제출시각="2026-12-01T10:00:00Z"), paste(meta, 제출시각="2026-13-01T10:00:00+09:00")],
            "too_large": [good + "\n" * gold_parse.MAX_BYTES],
            "not_utf8": [good + "\n\ud800"],
        }
        for code, prompts in cases.items():
            for prompt in prompts:
                with self.subTest(code=code, tail=prompt[-30:]):
                    reply = hook(self, self.root, prompt)
                    self.assertIn("저장하지 않음 [%s]" % code, reply)
                    self.assertNotIn(meta["nonce"], reply)
        self.assertEqual(stored(self.root), [])
        self.assertIn("Gold 저장됨", hook(self, self.root, good))  # 거절은 nonce를 쓰지 않는다

    def test_missing_direct_judgment_confirmation_rejected(self):
        only_answers = "z1=정상\nz2=정상"
        for prompt in (paste(self.meta, 직접판정=None), paste(self.meta, 직접판정=""), paste(self.meta, 직접판정="미확인"),
                       paste(self.meta, 직접판정="AI"), paste(self.meta, 직접판정="확인함"), only_answers):
            with self.subTest(prompt=prompt):
                self.assertIn("저장하지 않음 [no_direct_judgment]", hook(self, self.root, prompt))
        self.assertEqual(stored(self.root), [])

    def test_issue_is_recorded_first_with_hashed_nonce_and_no_prediction(self):
        self.assertRegex(self.meta["nonce"], r"\A[0-9a-f]{32}\Z")
        self.assertRegex(self.meta["screen_id"], r"\A[0-9a-f]{16}\Z")
        self.assertEqual(self.meta["confirm"], {"key": "직접판정", "required_value": "확인", "preset": False})
        self.assertEqual(set(self.meta), {"screen_id", "nonce", "zones", "criteria_version", "judge", "planned_repeat",
                                          "confirm"})
        self.assertEqual({k for z in self.meta["zones"].values() for k in z}, {"image_sha256", "region", "crop_sha256"})
        [row] = gold_store.rows(self.root, gold_store.ISSUED)  # 돌려받은 시점에 이미 기록돼 있다
        self.assertEqual(row["data"]["nonce_sha256"], hashlib.sha256(self.meta["nonce"].encode()).hexdigest())
        self.assertNotIn(self.meta["nonce"], json.dumps(row))
        other = issue(self.root)
        self.assertEqual(len({self.meta["nonce"], other["nonce"], self.meta["screen_id"], other["screen_id"]}), 4)
        with mock.patch("harness.gold_issue.secrets.token_hex", side_effect=["ab" * 8, "cd" * 16]) as token:
            self.assertEqual(issue(self.root)["nonce"], "cd" * 16)  # 난수는 secrets에서 온다
        self.assertEqual([c.args for c in token.call_args_list], [(8,), (16,)])

    def test_bad_issue_or_failed_record_hands_out_nothing(self):
        before = len(gold_store.rows(self.root, gold_store.ISSUED))
        base = zones("x")[0]
        bad = [[], [dict(base, prediction="결함")], [dict(base, score=0.9)], [{k: base[k] for k in ("image_sha256", "region")}],
               [dict(base, image_sha256="abc")], [dict(base, region="upper left")], [base, dict(base)]]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                gold_issue.issue(self.root, value, CRITERIA, "Judy", 1.0)
        for criteria, judge, planned in (("", "Judy", False), (CRITERIA, "Ju dy", False), (CRITERIA, "", False),
                                         (CRITERIA, "Judy", "yes")):
            with self.assertRaises(ValueError):
                gold_issue.issue(self.root, [base], criteria, judge, 1.0, planned)
        with mock.patch("harness.gold_issue.ledger.append", side_effect=OSError("디스크 가득")):
            with self.assertRaises(OSError):
                issue(self.root)
        self.assertEqual(len(gold_store.rows(self.root, gold_store.ISSUED)), before)
        with open(os.path.join(self.root, gold_store.ISSUED), "a") as handle:
            handle.write("{깨진 줄\n")
        with self.assertRaises(ledger.LedgerError):
            issue(self.root)

    def test_values_match_existing_screen_format(self):
        self.assertEqual(gold_parse.VALUES, answers.VALUES)
        body = "\n".join(line for line in paste(self.meta, ["불가", "미확인"]).splitlines()
                         if not line.startswith(("# nonce", "# 직접판정")))
        self.assertEqual(answers.parse(body)[2], gold_parse.parse(paste(self.meta, ["불가", "미확인"]))["answers"])


if __name__ == "__main__":
    unittest.main()

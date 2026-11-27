"""Gold 저장 흐름(실제 훅 프로세스): 원문 보존, nonce, 완료 키, Gold가 아닌 입력, 설정 템플릿."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unicodedata
import unittest

from harness import gold_store, ledger
from tests.test_harness_gold_support import REPO, hook, issue, paste, stored


class GoldFlowTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()

    def test_save_keeps_original_bytes_and_hash(self):
        meta = issue(self.root)
        # 정규화하면 달라지는 원문: CRLF, 줄 끝 공백, 앞뒤 빈 줄, 1단계 장부의 splitlines가 줄로 보는 U+2028·U+0085
        # U+2000은 NFC가 U+2002로 바꾸는 공백이라, 해시·원문을 정규화본으로 만들면 아래 대조가 어긋난다.
        prompt = "\n  " + paste(meta, ["결함", "불가"]).replace("\n", " \r\n") + " \u2028\x85\u2000\r\n\n"
        self.assertNotEqual(unicodedata.normalize("NFC", prompt), prompt)
        reply = hook(self, self.root, prompt)
        [record] = stored(self.root)
        self.assertEqual(base64.b64decode(record["raw_b64"]), prompt.encode("utf-8"))
        self.assertEqual(record["raw_sha256"], hashlib.sha256(prompt.encode("utf-8")).hexdigest())
        self.assertIn(record["raw_sha256"], reply)
        self.assertIn("Gold 저장됨", reply)
        self.assertEqual((record["source"], record["screen_id"], record["nonce"], record["judge_confirmation"],
                          record["judge"], record["planned_repeat"], record["session_id"], record["transcript_path"]),
                         ("human", meta["screen_id"], meta["nonce"], "확인", "judy", False, "session-test",
                          "/tmp/transcript-test.jsonl"))
        self.assertGreater(record["received_at"], 1.0e9)
        self.assertEqual([(i["zone"], i["value"], i["image_sha256"], i["crop_sha256"]) for i in record["items"]],
                         [(z, v, meta["zones"][z]["image_sha256"], meta["zones"][z]["crop_sha256"])
                          for z, v in (("z1", "결함"), ("z2", "불가"))])
        # 다음 저장이 이어 써진다. 입력의 대화 기록 칸에 줄을 가르는 문자가 있으면 그 칸만 버려 장부를 지킨다.
        odd = {"hook_event_name": "UserPromptSubmit", "prompt": paste(issue(self.root, "c")), "session_id": "a\u2028b",
               "transcript_path": 7}
        self.assertIn("Gold 저장됨", hook(self, self.root, None, stdin=json.dumps(odd).encode("utf-8")))
        self.assertEqual((stored(self.root)[1]["session_id"], stored(self.root)[1]["transcript_path"]), (None, None))
        self.assertEqual(ledger.verify(os.path.join(self.root, gold_store.STORE)), [])
        self.assertEqual(gold_store.audit(self.root), [])

    def test_unissued_and_reused_nonce_rejected(self):
        fake = {"screen_id": "0" * 16, "nonce": "1" * 32, "zones": {"z1": {}, "z2": {}}}
        self.assertIn("[not_issued]", hook(self, self.root, paste(fake)))  # 발급 장부 자체가 없음
        first, other = issue(self.root), issue(self.root, "c", "d")
        for forged in (paste(first, nonce="2" * 32), paste(first, nonce=other["nonce"]), paste(first, 화면="3" * 16)):
            self.assertIn("[not_issued]", hook(self, self.root, forged))
        self.assertEqual(stored(self.root), [])
        # 전부 미확인이라 완료 키가 생기지 않는다: 아래 거절은 nonce 규칙만의 결과다
        unjudged = paste(first, ["미확인", "미확인"])
        self.assertIn("Gold 저장됨", hook(self, self.root, unjudged))
        for again in (unjudged, paste(first, ["정상", "결함"])):
            self.assertIn("[nonce_reused]", hook(self, self.root, again))
        planned = issue(self.root, "e", planned_repeat=True)
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(planned)))
        self.assertIn("[nonce_reused]", hook(self, self.root, paste(planned)))  # 계획된 재판정도 nonce는 한 번
        self.assertEqual(len(stored(self.root)), 2)

    def test_completed_key_rejected_planned_repeat_marked(self):
        early = [issue(self.root, "b", "a") for _ in range(2)]  # 키가 끝나기 전에 발급한 화면은 저장 때 거절한다
        late_b = issue(self.root, "b")
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(issue(self.root, "a", "b"), ["결함", "미확인"])))
        for meta, value in zip(early, ("정상", "미확인")):  # 끝난 키 a가 있으면 값과 상관없이 화면 전체를 거절
            reply = hook(self, self.root, paste(meta, ["정상", value]))
            self.assertIn("[completed_key]", reply)
            self.assertIn("z2", reply)
        self.assertEqual(len(stored(self.root)), 1)
        before = len(gold_store.rows(self.root, gold_store.ISSUED))
        with self.assertRaises(gold_store.GoldError) as caught:  # 끝난 키는 발급부터 거절(사람이 판정하기 전에)
            issue(self.root, "b", "a")
        self.assertEqual((caught.exception.args[0], "z2" in caught.exception.args[1]), ("completed_key", True))
        self.assertEqual(len(gold_store.rows(self.root, gold_store.ISSUED)), before)
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(issue(self.root, "b"), ["불가"])))  # 미확인은 미완료
        self.assertIn("[completed_key]", hook(self, self.root, paste(late_b)))  # 불가는 완료
        with self.assertRaises(gold_store.GoldError):
            issue(self.root, "b")
        other_criteria = hashlib.sha256(b"corner-criteria:test-2").hexdigest()
        for meta in (issue(self.root, "a", criteria=other_criteria), issue(self.root, "a", judge="other"),
                     issue(self.root, "a", planned_repeat=True)):
            self.assertIn("Gold 저장됨", hook(self, self.root, paste(meta)))
        self.assertEqual([r["planned_repeat"] for r in stored(self.root)], [False, False, False, False, True])
        self.assertEqual(gold_store.audit(self.root), [])

    def test_non_gold_input_is_silent_or_not_saved(self):
        for prompt in ("다음 작업 진행해줘", "# 제목\nz축 = 3", "", "화면=abc 를 설명해줘"):
            self.assertEqual(hook(self, self.root, prompt), "", prompt)
        self.assertEqual(os.listdir(self.root), [])
        meta = issue(self.root)
        self.assertIn("읽지 못함", hook(self, self.root, paste(meta), event="PreToolUse"))
        self.assertIn("읽지 못함", hook(self, self.root, None, stdin=b"{not json"))
        self.assertIn("읽지 못함", hook(self, self.root, None, stdin=b'["list"]'))
        self.assertIn("설정 오류", hook(self, "relative/root", paste(meta)))
        self.assertEqual(stored(self.root), [])

    def test_settings_template_command_runs_the_hook(self):
        with open(os.path.join(REPO, "harness", "hooks", "settings-snippet.json.template"), encoding="utf-8") as handle:
            [group] = json.load(handle)["hooks"]["UserPromptSubmit"]
        [entry] = group["hooks"]
        command = entry["command"]
        for key, value in (("__PYTHON__", sys.executable), ("__REPO__", REPO), ("__HARNESS_ROOT__", self.root)):
            command = command.replace(key, value)
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": paste(issue(self.root))}
        done = subprocess.run(command, shell=True, input=json.dumps(payload).encode(), capture_output=True, check=False)
        self.assertEqual((done.returncode, done.stderr), (0, b""))
        self.assertIn("Gold 저장됨", done.stdout.decode("utf-8"))
        self.assertIsNone(stored(self.root)[0]["session_id"])


if __name__ == "__main__":
    unittest.main()

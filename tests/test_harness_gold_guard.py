"""fail-closed와 위조 시험: 직접 저장 거절, 장부 직접 쓰기의 감지, 막지 못하는 경우의 기록."""
import base64
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from harness import gold_hook, gold_store, ledger
from tests.test_harness_gold_support import REPO, hook, issue, paste, stored


class GoldGuardTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.meta = issue(self.root)
        self.store = os.path.join(self.root, gold_store.STORE)

    def test_direct_write_without_hook_mark_refused(self):
        payload = {"hook_event_name": "UserPromptSubmit", "prompt": paste(self.meta)}
        with self.assertRaises(gold_store.GoldError) as caught:
            gold_store.save(self.root, payload, 1.0)
        self.assertEqual(caught.exception.args[0], "no_hook_mark")
        self.assertIn("[no_hook_mark]", gold_hook.handle(self.root, json.dumps(payload).encode(), 1.0))
        code = "import json,sys; sys.path.insert(0, sys.argv[1]); from harness import gold_store\n" \
               "gold_store.save(sys.argv[2], json.loads(sys.argv[3]), 1.0)"
        for command in ([sys.executable, "-c", code, REPO, self.root, json.dumps(payload)],
                        [sys.executable, "-", REPO, self.root, json.dumps(payload)]):
            done = subprocess.run(command, input=code.encode(), capture_output=True, check=False)
            self.assertNotEqual(done.returncode, 0)
            self.assertIn(b"no_hook_mark", done.stderr)
        script = os.path.join(self.root, "user_prompt_submit.py")  # 이름만 같은 다른 파일
        pathlib.Path(script).write_text(code, encoding="utf-8")
        done = subprocess.run([sys.executable, script, REPO, self.root, json.dumps(payload)], capture_output=True, check=False)
        self.assertIn(b"no_hook_mark", done.stderr)
        self.assertFalse(os.path.exists(self.store))

    def test_direct_ledger_forgery_is_detected_by_audit(self):
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(self.meta)))
        self.assertEqual(gold_store.audit(self.root), [])
        genuine, original = stored(self.root)[0], pathlib.Path(self.store).read_bytes()
        target = issue(self.root, "z")
        [row] = [r for r in gold_store.rows(self.root, gold_store.ISSUED) if r["data"]["screen_id"] == target["screen_id"]]
        consistent = dict(gold_store._derive(row, paste(target).encode()), session_id=None, transcript_path=None,
                          received_at=1.0)
        changed_raw = base64.b64encode(paste(target, ["결함"]).encode()).decode()
        forgeries = {
            "발급 없는 화면": dict(genuine, screen_id="9" * 16),
            "답만 바꿈": dict(consistent, items=[dict(consistent["items"][0], value="결함")]),
            "원문만 바꿈": dict(consistent, raw_b64=changed_raw),
            "계획된 재판정 표시를 붙임": dict(consistent, planned_repeat=True),
            "AI 출처": dict(consistent, source="ai"),
            "칸 추가": dict(consistent, prediction="결함"),
            "같은 기록 재사용": genuine,
            "형식이 아닌 기록": {"value": "정상"},
        }
        for name, data in forgeries.items():
            with self.subTest(name=name):
                pathlib.Path(self.store).write_bytes(original)
                ledger.append(self.store, 2.0, "gold_received", data)  # 체인은 정상으로 이어진다
                self.assertEqual(ledger.verify(self.store), [])
                self.assertTrue(any(p["seq"] == 1 for p in gold_store.audit(self.root)), gold_store.audit(self.root))
        pathlib.Path(self.store).write_bytes(original)
        ledger.append(self.store, 2.0, "gold_received", genuine)
        problems = {p["problem"] for p in gold_store.audit(self.root)}
        self.assertEqual(problems, {"nonce_reused", "completed_key_repeated"})
        pathlib.Path(self.store).write_bytes(original.replace(b'"value": "\xec\xa0\x95', b'"value": "\xea\xb2\xb0', 1))
        self.assertIn("hash_mismatch", [p["problem"] for p in gold_store.audit(self.root)])

    def test_piped_forgery_is_not_prevented_but_leaves_transcript_evidence(self):
        # 알려진 한계를 고정한다: 같은 권한으로 진입점에 모의 JSON을 넣으면 저장되고 audit()은 구별하지 못한다.
        # 남는 것은 대화 기록과 대조할 session_id·transcript_path·원문 해시뿐이다(그 대조 도구는 이번 범위에 없다).
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(self.meta)))
        self.assertEqual(gold_store.audit(self.root), [])
        [record] = stored(self.root)
        self.assertEqual((record["session_id"], record["transcript_path"], len(record["raw_sha256"])),
                         ("session-test", "/tmp/transcript-test.jsonl", 64))

    def test_damaged_chain_refuses_save_and_leaves_evidence(self):
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(self.meta)))
        fresh = issue(self.root, "z")
        for path in (self.store, os.path.join(self.root, gold_store.ISSUED)):
            with self.subTest(path=path):
                good = pathlib.Path(path).read_bytes()
                damaged = good.replace(b'"ts": ', b'"ts": 9', 1)
                pathlib.Path(path).write_bytes(damaged)
                self.assertIn("[chain_broken]", hook(self, self.root, paste(fresh)))
                self.assertEqual(pathlib.Path(path).read_bytes(), damaged)  # 고치거나 지우지 않는다
                self.assertTrue(gold_store.audit(self.root))
                pathlib.Path(path).write_bytes(good)
        self.assertEqual(len(stored(self.root)), 1)

    def test_tail_truncation_needs_external_tail_copy(self):
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(self.meta)))
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(issue(self.root, "z"))))
        tail = ledger.tail(self.store)
        lines = pathlib.Path(self.store).read_bytes().splitlines(True)
        pathlib.Path(self.store).write_bytes(b"".join(lines[:-1]))
        self.assertEqual(gold_store.audit(self.root), [])  # 복제본이 없으면 모른다
        self.assertEqual([p["problem"] for p in gold_store.audit(self.root, store_tail=tail)], ["tail_mismatch"])


if __name__ == "__main__":
    unittest.main()

"""fail-closed와 위조 시험: 직접 저장 거절, 장부 직접 쓰기의 감지, 막지 못하는 경우의 기록."""
import base64
import hashlib
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
            "발급 줄 해시만 다름": dict(consistent, issued_hash="0" * 64),
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

    def test_issue_lines_not_shaped_like_issue_are_refused_and_audited(self):
        [row] = gold_store.rows(self.root, gold_store.ISSUED)
        nonce, data = self.meta["nonce"], row["data"]
        self.assertEqual(data["nonce_sha256"], hashlib.sha256(nonce.encode()).hexdigest())
        z1, z2 = data["zones"]["z1"], data["zones"]["z2"]
        broken_z1 = {
            "예측 칸": dict(z1, prediction="결함"), "점수 칸": dict(z1, score=0.9),
            "구역 칸 빠짐": {k: z1[k] for k in ("image_sha256", "region")},
            "구역 이름 변형": dict(z1, region="Upper_Left"), "해시 형식": dict(z1, crop_sha256="abc"), "같은 구역 두 번": z2,
        }
        cases = {name: dict(data, zones={"z1": zone, "z2": z2}) for name, zone in broken_z1.items()}
        cases.update({
            "번호 이름": dict(data, zones={"z1": z1, "z3": z2}), "화면 칸 추가": dict(data, prediction="결함"),
            "기준 변형": dict(data, criteria_version="CRIT-1"), "판정자 변형": dict(data, judge="Judy"),
            "재판정 표시가 문자열": dict(data, planned_repeat=""),
        })
        cases = {name: ("gold_screen_issued", value) for name, value in cases.items()}
        cases["다른 이벤트 이름"] = ("anything", data)
        cases["대조(바꾼 것 없음)"] = ("gold_screen_issued", data)  # 형식을 다 맞춘 직접 기록은 구별하지 못한다(한계)
        for name, (event, value) in cases.items():
            with self.subTest(name=name):
                root, control = tempfile.mkdtemp(), name.startswith("대조")
                ledger.append(os.path.join(root, gold_store.ISSUED), 1.0, event, value)
                values = ["정상"] * len(value["zones"])
                reply = hook(self, root, paste(self.meta, values))
                self.assertIn("Gold 저장됨" if control else "저장하지 않음 [bad_issue_record]", reply)
                self.assertEqual(len(stored(root)), int(control))
                found = [(p["file"], p["seq"]) for p in gold_store.audit(root)]
                self.assertEqual(found, [] if control else [(gold_store.ISSUED, 0)])
        # 화면 ID조차 없는 발급 줄: audit는 예외 없이 목록으로 알리고, 무관한 화면의 발급·저장은 막지 않는다
        root = tempfile.mkdtemp()
        for value in ({"x": 1}, "문자열", {"screen_id": ["목록"]}):
            ledger.append(os.path.join(root, gold_store.ISSUED), 1.0, "gold_screen_issued", value)
        self.assertEqual([p["seq"] for p in gold_store.audit(root)], [0, 1, 2])
        self.assertIn("Gold 저장됨", hook(self, root, paste(issue(root, "z"))))
        self.assertEqual([(p["file"], p["seq"]) for p in gold_store.audit(root)], [(gold_store.ISSUED, n) for n in (0, 1, 2)])
        # 저장 뒤에 발급 줄이 형식 밖이 된 경우: audit의 저장 기록 대조도 같은 검사를 거친다
        ledger.append(os.path.join(self.root, gold_store.ISSUED), 1.0, "anything", dict(data, screen_id="9" * 16))
        self.assertIn("Gold 저장됨", hook(self, self.root, paste(self.meta)))
        pathlib.Path(self.root, gold_store.ISSUED).unlink()
        ledger.append(os.path.join(self.root, gold_store.ISSUED), 1.0, "anything", data)
        self.assertIn("invalid_record:bad_issue_record", [p["problem"] for p in gold_store.audit(self.root)])

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

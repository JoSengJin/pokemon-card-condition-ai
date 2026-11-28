"""PLAN_GATE의 봉인 읽기 차단 시험(2026-11-28 신뢰 경계 조사): Supervisor는 sandbox 밖이라 plan_gate._external이 봉인 목록 아래 실험 기록을 열지 않아야 한다.

합성 원본 저장소·임시 봉인 목록만 쓴다(실제 봉인 파일·./experiment·claude·모델 호출 없음). 열기 감시는 builtins.open을 감싸 경로를 기록한다.
"""
import builtins
import json
import os
import tempfile
import unittest
from unittest import mock

from harness import claude_perm, plan_gate
from tests import harness_plan_gate_kit as kit
from tests import test_harness_vs3_fixes as fixes
from tests import test_harness_vs3_gate as vs3_gate

SEALED = "20300110T000000-5ea1ed00"  # 폴더째 봉인(같은 조건의 기록: 열렸다면 기각 가설로 거절됐을 것)
SEALED_FILE = "20300111T000000-5ea1ed01"  # 폴더는 개발용, record.json만 봉인
HIDDEN = os.path.join("hidden", "code.py")  # 봉인 목록의 다른 항목(source_hashes가 가리킬 자리)


class PlanGateSealTest(unittest.TestCase):
    _chain = vs3_gate.PlanGateTest._chain
    _record = fixes.PlanGateFixTest._record

    def _world(self, listed=None):
        """(world, 봉인 목록 패치 시작). 봉인 폴더·파일·숨은 코드 파일을 합성 원본에 심는다."""
        root, src, head = kit.world(self)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"paths": listed or ["artifacts/experiments/" + SEALED, "artifacts/experiments/%s/record.json" % SEALED_FILE, HIDDEN]}, handle)
        self.addCleanup(os.unlink, handle.name)
        patch = mock.patch.object(claude_perm, "SEALED_LIST", handle.name)
        patch.start()
        self.addCleanup(patch.stop)
        os.makedirs(os.path.join(src, "hidden"))
        with open(os.path.join(src, HIDDEN), "w", encoding="utf-8") as out:
            out.write("secret = 1\n")
        self._record(src, SEALED)
        self._record(src, SEALED_FILE)
        return root, src, head

    def _opened(self, world, **chain):
        """gate가 여는 파일의 실제 경로 목록과 _chain 결과."""
        seen, real_open = [], builtins.open

        def spy(file, *args, **kwargs):
            seen.append(os.path.realpath(file) if isinstance(file, (str, bytes, os.PathLike)) else file)
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", spy):
            got = self._chain({"over": {"value": 0.8}}, world=world, **chain)
        return got, [p for p in seen if isinstance(p, str)]

    def test_sealed_records_are_not_opened_and_a_normal_plan_is_not_held_forever(self):
        world = self._world()
        got, seen = self._opened(world)
        src = os.path.realpath(world[1])
        self.assertEqual([p for p in seen if p.startswith(os.path.join(src, "artifacts", "experiments", SEALED))
                          or p == os.path.join(src, "artifacts", "experiments", SEALED_FILE, "record.json")], [])
        self.assertIsNone(got["reason"], got["reason"])  # 봉인 폴더가 있어도 영구 대기·거절이 아니다
        self.assertEqual(len([c for c in got["out"].values() if got["analyze"] in c["depends_on"]]), 1)

    def test_dev_record_is_still_compared_with_sealed_folders_present(self):
        world = self._world()
        self._record(world[1], "20300112T000000-0badc0de")
        got = self._chain({"over": {"value": 0.8}}, world=world)
        self.assertTrue(got["reason"].startswith("refused: 기각·중복 가설") and "20300112T000000-0badc0de" in got["reason"], got["reason"])

    def test_record_pointing_source_hashes_at_a_sealed_file_waits_without_hashing_it(self):
        world = self._world()
        self._record(world[1], "20300113T000000-00000007", code="0" * 64)
        path = os.path.join(world[1], "artifacts", "experiments", "20300113T000000-00000007", "record.json")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        record["source_hashes"] = {HIDDEN: "0" * 64}
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)
        got, seen = self._opened(world)
        self.assertNotIn(os.path.realpath(os.path.join(world[1], HIDDEN)), seen)
        self.assertTrue(got["reason"].startswith("waiting") and "20300113T000000-00000007" in got["reason"], got["reason"])

    def _hashes(self, world, name, hashes, **kw):
        """개발 폴더 name에 같은 조건의 기록을 심고 source_hashes만 hashes로 바꾼다."""
        self._record(world[1], name, **kw)
        path = os.path.join(world[1], "artifacts", "experiments", name, "record.json")
        with open(path, encoding="utf-8") as handle:
            record = json.load(handle)
        record["source_hashes"] = hashes
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle)

    def test_hard_link_to_a_sealed_record_waits_without_opening_it(self):
        world = self._world()
        dev = os.path.join(world[1], "artifacts", "experiments", "20300114T000000-11111111")
        os.makedirs(dev)
        for name in ("record.json", "plan.json"):  # 봉인 폴더의 파일을 개발 폴더에 하드 링크(이름·상위 폴더 검사를 피한다)
            os.link(os.path.join(world[1], "artifacts", "experiments", SEALED, name), os.path.join(dev, name))
        got, seen = self._opened(world)
        self.assertEqual([p for p in seen if p.startswith(os.path.realpath(dev))], [])
        self.assertTrue(got["reason"].startswith("waiting") and "하드 링크" in got["reason"], got["reason"])

    def test_absolute_or_parent_source_hash_keys_wait_without_hashing(self):
        outside = tempfile.NamedTemporaryFile("w", delete=False)
        self.addCleanup(os.unlink, outside.name)
        outside.close()
        for key in (outside.name, "../" + os.path.basename(outside.name), "a/../../x"):
            world = self._world()
            self._hashes(world, "20300115T000000-22222222", {key: "0" * 64})
            got, seen = self._opened(world)
            self.assertNotIn(os.path.realpath(outside.name), seen, key)
            self.assertTrue(got["reason"].startswith("waiting") and "20300115T000000-22222222" in got["reason"], (key, got["reason"]))

    def test_a_record_with_another_condition_is_not_hashed_and_does_not_hold_the_plan(self):
        world = self._world()
        self._hashes(world, "20300116T000000-33333333", {HIDDEN: "0" * 64, "/etc/hosts": "0" * 64}, value=0.85)  # 조건이 다름: 해시가 필요 없다
        got, seen = self._opened(world)
        self.assertNotIn(os.path.realpath(os.path.join(world[1], HIDDEN)), seen)
        self.assertIsNone(got["reason"], got["reason"])

    def test_unreadable_seal_list_blocks_the_comparison_fail_closed(self):
        world = self._world()
        got = self._chain({"over": {"value": 0.8}}, world=world)
        [new] = [c for c in got["out"].values() if got["analyze"] in c["depends_on"]]
        with mock.patch.object(claude_perm, "SEALED_LIST", os.path.join(world[1], "missing.json")):
            with self.assertRaisesRegex(ValueError, "봉인 경로 목록"):  # gate는 ValueError를 그 계획만 대기(_PLAN_ERRORS)로 처리한다
                plan_gate._external(world[1], new)


if __name__ == "__main__":
    unittest.main()

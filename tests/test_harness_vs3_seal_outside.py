"""PLAN_GATE의 저장소 밖 봉인 루트 차단 시험(2026-11-29 독립 검증 D1): seal_check.load가 claude_perm.outside_roots도 합쳐야
plan_gate._external이 바깥 봉인 루트로 가는 심볼릭 링크(실험 폴더·source_hashes 키)를 열지 않는다.

합성 원본 저장소·임시 봉인 목록·임시 바깥 루트만 쓴다(실제 봉인 파일·./experiment·claude·모델 호출 없음). 열기 감시는 test_harness_vs3_seal의 _opened.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import cas, claude_perm, plan_gate
from tests import test_harness_vs3_seal as seal

OUT = "20300120T000000-0a75de00"  # 바깥 루트로 옮긴 같은 조건의 기록(열렸다면 기각 가설로 거절됐을 것)


class PlanGateOutsideSealTest(unittest.TestCase):
    _chain = seal.PlanGateSealTest._chain
    _record = seal.PlanGateSealTest._record
    _opened = seal.PlanGateSealTest._opened

    def _world(self):
        """(world, 바깥 루트). 봉인 목록(test_harness_vs3_seal)에 더해 임시 바깥 루트 하나를 OUTSIDE_LIST로 둔다."""
        world = seal.PlanGateSealTest._world(self)
        outside = os.path.realpath(tempfile.mkdtemp(prefix="sealed-outside-"))
        self.addCleanup(shutil.rmtree, outside, True)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"roots": [outside]}, handle)
        self.addCleanup(os.unlink, handle.name)
        patch = mock.patch.object(claude_perm, "OUTSIDE_LIST", handle.name)
        patch.start()
        self.addCleanup(patch.stop)
        return world, outside

    def test_experiment_folder_linked_into_an_outside_sealed_root_is_skipped_unopened(self):
        world, outside = self._world()
        folder = os.path.join(world[1], "artifacts", "experiments", OUT)
        self._record(world[1], OUT)
        shutil.move(folder, os.path.join(outside, OUT))
        os.symlink(os.path.join(outside, OUT), folder)
        got, seen = self._opened(world)
        self.assertEqual([p for p in seen if p.startswith(outside + os.sep)], [])
        self.assertIsNone(got["reason"], got["reason"])  # 건너뛰었으므로 거절·대기 없음

    def test_source_hash_key_linked_into_an_outside_sealed_root_waits_without_hashing(self):
        world, outside = self._world()
        target = os.path.join(outside, "code.py")
        shutil.copy(os.path.join(world[1], "code.py"), target)
        os.symlink(target, os.path.join(world[1], "linked.py"))
        self._hashes(world, "20300121T000000-44444444", {"linked.py": cas.sha_file(target)})
        got, seen = self._opened(world)
        self.assertNotIn(target, seen)
        self.assertTrue(got["reason"].startswith("waiting") and "20300121T000000-44444444" in got["reason"], got["reason"])

    def test_unreadable_outside_list_blocks_the_comparison_fail_closed(self):
        world, _ = self._world()
        got = self._chain({"over": {"value": 0.8}}, world=world)
        [new] = [c for c in got["out"].values() if got["analyze"] in c["depends_on"]]
        with mock.patch.object(claude_perm, "OUTSIDE_LIST", os.path.join(world[1], "missing.json")):
            with self.assertRaisesRegex(ValueError, "저장소 밖 봉인 루트 목록"):
                plan_gate._external(world[1], new)

    _hashes = seal.PlanGateSealTest._hashes


if __name__ == "__main__":
    unittest.main()

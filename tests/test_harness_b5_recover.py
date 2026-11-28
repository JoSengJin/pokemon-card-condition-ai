"""B5-1(VS6): Supervisor 회차 앞 철회 복구 연결(verify-b924753 중요 결함 ①). 합성 root만 쓰며 실제 승격·학습·모델 호출은 없다.

철회 도중 실제 SIGKILL(모든 쓰기 지점) → 실제 진입점 `python -m harness.supervisor --max-cycles 1` 한 번 → 포인터가 무효 모델을 유효로
읽지 않고 끊김 없는 철회와 같은 최종 상태, 두 번째 회차는 아무 것도 바꾸지 않음(멱등). 장부 변조는 fail-closed(INTEGRITY_HALT, 쓰기 없음),
정지 상태에서는 복구도 하지 않음(보수적 기본값, 사용자 확인 필요), Silver 저장소가 없는 root에는 부작용 없음.
"""
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

from harness import champion, graph, opstate, registry, silver_store, supervisor, withdrawal
from tests import harness_depth_kit as kit
from tests.harness_recover_kit import CLEAR, RESTORE, call_for, entry, interrupted, stale, tree
from tests.test_harness_champion_support import add_model, make_root
from tests.test_harness_supervisor_kit import events
from tests.test_harness_withdrawal_support import run_point, scenario, snapshot


class RecoverTest(unittest.TestCase):
    def test_kill_at_every_write_then_one_entry_cycle_recovers_and_repeats_are_no_ops(self):
        reproduced = []
        for setup, fn in ((RESTORE, "withdraw"), (CLEAR, "withdraw"), (RESTORE, "verdicts")):
            ref = scenario(self, **setup)
            trace = run_point(self, ref["root"], "none", call_for(ref, fn))
            want = snapshot(ref["root"], ref["models"])
            for point in sorted(set(trace), key=trace.index):
                s = interrupted(self, setup, point, fn)
                before = snapshot(s["root"], s["models"])
                reproduced.append(stale(s["root"]))
                out = entry(self, s["root"])
                where = (setup["champions"], fn, point)
                self.assertEqual((opstate.RUNNING, None), (out["state"], stale(s["root"])), where)
                started = any(e["event"] == "policy_withdrawn" for e in silver_store.load(s["root"]))
                if fn == "withdraw":  # 시작 기록이 있으면 끊김 없는 결과, 없으면(시작 전 kill) 아무 변화 없음
                    self.assertEqual(want if started else before, snapshot(s["root"], s["models"]), where)
                after = tree(s["root"])
                again = entry(self, s["root"])["withdrawal"]
                self.assertEqual(([], None), (again["invalidated"], again["restore"]), where)
                self.assertEqual(after, tree(s["root"]), where)  # 두 번째 회차: 장부·포인터·가중치 한 바이트도 안 바뀜
        # 결함 재현: 복구 전에는 무효 모델이 valid=True로 읽히는 지점이 있었다(m1 철회 시작·감사 실패 기록 직후 등)
        self.assertTrue([m for m in reproduced if m is not None], reproduced)

    def test_tampered_ledgers_fail_closed_without_writes(self):
        for rel in (silver_store.STORE, registry.REGISTRY):
            s = interrupted(self)
            path = os.path.join(s["root"], rel)
            with open(path, encoding="utf-8") as handle:
                lines = handle.read().split("\n")
            row = json.loads(lines[0])
            row["ts"] += 1  # 해시를 다시 계산하지 않은 변조
            lines[0] = json.dumps(row)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("\n".join(lines))
            skip = ("supervisor", "ledger.jsonl")  # 주 장부에는 정지 전이(opstate_transition)만 더해진다(아래에서 대조)
            before, main = tree(s["root"], skip), events(s["root"])
            for _ in range(2):
                self.assertEqual(opstate.INTEGRITY_HALT, entry(self, s["root"])["state"], rel)
                self.assertEqual(before, tree(s["root"], skip), rel)  # 철회 장부·레지스트리·포인터·가중치에 쓰기 없음
            self.assertEqual(["opstate_transition"], [e["event"] for e in events(s["root"])[len(main):]], rel)
            self.assertIn(opstate.INTEGRITY_HALT, opstate.load(s["root"])["conditions"], rel)

    def test_halting_states_do_not_recover_until_cleared(self):
        for name in opstate.HALTING:
            s = interrupted(self)
            opstate.set_condition(s["root"], name, 1.0, "user", "정지")
            before = tree(s["root"])
            out = entry(self, s["root"])
            self.assertEqual((name, before), (out["state"], tree(s["root"])), name)  # 정지 중에는 복구도 쓰지 않는다
            self.assertNotIn("withdrawal", out, name)
            self.assertEqual(s["models"]["m1"], stale(s["root"]), name)  # 남는 틈(사용자 확인 필요): 정지 중엔 유효로 읽힌다
            if name == opstate.USER_STOPPED:  # 사람이 정지를 푼 뒤(시험이 사람 해제 함수를 직접 부름) 첫 회차에 복구
                opstate.clear_by_user(s["root"], name, 2.0, "재개")
                self.assertEqual((opstate.RUNNING, None), (entry(self, s["root"])["state"], stale(s["root"])))

    def test_roots_without_a_silver_store_get_no_side_effects(self):
        empty = make_root(self)
        out = entry(self, empty)
        self.assertEqual(({}, False), (tree(empty), "withdrawal" in out))
        self.assertEqual(["supervisor.lock"], os.listdir(os.path.join(empty, "supervisor")))
        probe = tempfile.mkdtemp()  # 대조(pre-b5 확인 동작): 조건 없이 부르면 빈 root에 잠금 폴더 두 개를 만든다
        self.addCleanup(shutil.rmtree, probe, True)
        withdrawal.withdraw(probe, 1.0)
        self.assertEqual(["models", "silver"], sorted(os.listdir(probe)))
        root = make_root(self)  # Silver 없이 Champion만 있는 root: 레지스트리·포인터·가중치 그대로
        self.assertTrue(champion.promote(root, 2.0, add_model(root, "base"))["ok"])
        self.assertFalse(os.path.exists(os.path.join(root, silver_store.STORE)))
        before = tree(root)
        self.assertNotIn("withdrawal", entry(self, root))
        self.assertEqual(before, tree(root))

    def test_recovery_runs_before_graph_and_python_and_keeps_depth(self):
        s = interrupted(self)
        os.makedirs(os.path.join(s["root"], "supervisor"))
        with open(os.path.join(s["root"], supervisor.DECLARED), "w", encoding="utf-8") as handle:
            json.dump({"x": {}}, handle)
        calls = mock.Mock()
        with mock.patch.object(withdrawal, "withdraw", wraps=withdrawal.withdraw) as recover, \
                mock.patch.object(graph, "register_missing") as register, \
                mock.patch.object(supervisor, "_python", return_value=(0, 0)) as python:
            calls.attach_mock(recover, "withdraw")
            calls.attach_mock(register, "graph")
            calls.attach_mock(python, "python")
            out = supervisor.run(s["root"], executors="x:Y", max_cycles=1, poll_s=0)
        self.assertEqual(["withdraw", "graph", "python"], [c[0] for c in calls.mock_calls])  # withdraw가 끝난 뒤 그래프·Python
        self.assertEqual((None, None), (out["withdrawal"]["restore"]["model_id"], stale(s["root"])))
        depth, path = kit.longest("supervisor.run")
        self.assertLessEqual(depth, 4, path)
        self.assertLessEqual(kit.longest("withdrawal.withdraw")[0] + 1, 4)  # run에서 직접 부른다(래퍼 없음)


if __name__ == "__main__":
    unittest.main()

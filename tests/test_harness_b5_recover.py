"""B5-1(VS6): Supervisor 회차 앞 철회 복구 연결(verify-b924753 중요 결함 ①). 합성 root만 쓰며 실제 승격·학습·모델 호출은 없다.

철회 도중 실제 SIGKILL(모든 쓰기 지점) → 실제 진입점 `python -m harness.supervisor --max-cycles 1` 한 번 → 포인터가 무효 모델을 유효로
읽지 않고 끊김 없는 철회와 같은 최종 상태, 두 번째 회차는 아무 것도 바꾸지 않음(멱등). 장부 변조는 fail-closed(INTEGRITY_HALT, 쓰기 없음),
정지 상태에서는 복구도 하지 않음(보수적 기본값, 사용자 확인 필요), Silver 저장소가 없는 root에는 부작용 없음.
"""
import json
import os
import subprocess
import tempfile
import unittest
from unittest import mock

from harness import champion, eligibility, graph, opstate, registry, silver_store, supervisor, withdrawal
from tests import harness_depth_kit as kit
from tests.test_harness_champion_support import REPO, add_model, make_root
from tests.test_harness_supervisor_kit import SUPERVISOR, events
from tests.test_harness_withdrawal_support import run_point, sample_of, scenario, snapshot

RESTORE = {"champions": ("base", "m2", "m1"), "legacy": ("m1",)}  # m1 철회 → m2는 보류라 제외 → base로 복원
CLEAR = {"champions": ("m2", "m1"), "legacy": ("m1",)}  # 적격 후보 없음 → Champion 없음


def tree(root, skip=("supervisor",)):
    """root 아래 파일 {상대 경로: 바이트}. skip으로 시작하는 경로(Supervisor 자신의 잠금·상태·알림)는 뺀다."""
    out = {}
    for folder, _, names in os.walk(root):
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), root)
            if not rel.startswith(skip):
                with open(os.path.join(folder, name), "rb") as handle:
                    out[rel] = handle.read()
    return out


def stale(root):
    """포인터가 유효(valid=True)로 읽히지만 장부 파생 계산으로는 무효인 모델 ID(결함), 아니면 None."""
    holder = champion.read_current(root)
    if not holder or not holder["valid"]:
        return None
    facts = eligibility.silver_facts(silver_store.load(root))
    return holder["model_id"] if holder["model_id"] in eligibility.invalid_models(registry.load(root), facts) else None


def entry(case, root):
    """실제 진입점 1회차(별도 프로세스). 출력 요약 dict."""
    proc = subprocess.run(SUPERVISOR + ["--root", root, "--max-cycles", "1", "--poll", "0"], cwd=REPO,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)
    case.assertEqual(0, proc.returncode, proc.stderr)
    return json.loads(proc.stdout.strip().split("\n")[-1])


class RecoverTest(unittest.TestCase):
    def test_kill_at_every_write_then_one_entry_cycle_recovers_and_repeats_are_no_ops(self):
        cases = [(RESTORE, lambda s: {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}}),
                 (CLEAR, lambda s: {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}}),
                 (RESTORE, lambda s: {"fn": "verdicts", "batch_id": "b1", "verdicts": {sample_of(s["root"], "b1")[0]: "incorrect"}})]
        reproduced = []
        for setup, make_call in cases:
            ref = scenario(self, **setup)
            trace = run_point(self, ref["root"], "none", make_call(ref))
            want = snapshot(ref["root"], ref["models"])
            for point in sorted(set(trace), key=trace.index):
                s = scenario(self, **setup)
                run_point(self, s["root"], point, make_call(s))
                before = snapshot(s["root"], s["models"])
                reproduced.append(stale(s["root"]))
                out = entry(self, s["root"])
                where = (setup["champions"], make_call(s)["fn"], point)
                self.assertEqual((opstate.RUNNING, None), (out["state"], stale(s["root"])), where)
                started = any(e["event"] == "policy_withdrawn" for e in silver_store.load(s["root"]))
                if make_call(s)["fn"] == "withdraw":  # 시작 기록이 있으면 끊김 없는 결과, 없으면(시작 전 kill) 아무 변화 없음
                    self.assertEqual(want if started else before, snapshot(s["root"], s["models"]), where)
                after = tree(s["root"])
                self.assertEqual({k: v for k, v in out.items() if k != "withdrawal"},
                                 {k: v for k, v in entry(self, s["root"]).items() if k != "withdrawal"}, where)
                self.assertEqual(after, tree(s["root"]), where)  # 두 번째 회차: 장부·포인터·가중치 한 바이트도 안 바뀜
        # 결함 재현: 복구 전에는 무효 모델이 valid=True로 읽히는 지점이 있었다(m1 철회 시작·감사 실패 기록 직후 등)
        self.assertTrue([m for m in reproduced if m is not None], reproduced)

    def test_tampered_ledgers_fail_closed_without_writes(self):
        for rel in (silver_store.STORE, registry.REGISTRY):
            s = scenario(self, **CLEAR)
            run_point(self, s["root"], "after:policy_withdrawn:1",
                      {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}})
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
            s = scenario(self, **CLEAR)
            run_point(self, s["root"], "after:policy_withdrawn:1",
                      {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}})
            opstate.set_condition(s["root"], name, 1.0, "user", "정지")
            before = tree(s["root"])
            out = entry(self, s["root"])
            self.assertEqual((name, before), (out["state"], tree(s["root"])), name)  # 정지 중에는 복구도 쓰지 않는다
            self.assertNotIn("withdrawal", out, name)
            self.assertEqual(s["models"]["m1"], stale(s["root"]), name)  # 남는 틈(사용자 확인 필요): 정지 중엔 유효로 읽힌다
            if name == opstate.USER_STOPPED:  # 사람이 정지를 푼 뒤 첫 회차에 복구
                opstate.clear_by_user(s["root"], name, 2.0, "재개")
                self.assertEqual((opstate.RUNNING, None), (entry(self, s["root"])["state"], stale(s["root"])))

    def test_roots_without_a_silver_store_get_no_side_effects(self):
        empty = make_root(self)
        out = entry(self, empty)
        self.assertEqual(({}, False), (tree(empty), "withdrawal" in out))
        self.assertEqual(["supervisor.lock"], os.listdir(os.path.join(empty, "supervisor")))
        probe = tempfile.mkdtemp()  # 대조(pre-b5 확인 동작): 조건 없이 부르면 빈 root에 잠금 폴더 두 개를 만든다
        self.addCleanup(__import__("shutil").rmtree, probe, True)
        withdrawal.withdraw(probe, 1.0)
        self.assertEqual(["models", "silver"], sorted(os.listdir(probe)))
        root = make_root(self)  # Silver 없이 Champion만 있는 root: 레지스트리·포인터·가중치 그대로
        self.assertTrue(champion.promote(root, 2.0, add_model(root, "base"))["ok"])
        self.assertFalse(os.path.exists(os.path.join(root, silver_store.STORE)))
        before = tree(root)
        self.assertNotIn("withdrawal", entry(self, root))
        self.assertEqual(before, tree(root))

    def test_recovery_runs_before_graph_and_python_and_keeps_depth(self):
        s = scenario(self, **CLEAR)
        run_point(self, s["root"], "after:policy_withdrawn:1",
                  {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}})
        os.makedirs(os.path.join(s["root"], "supervisor"))
        with open(os.path.join(s["root"], supervisor.DECLARED), "w", encoding="utf-8") as handle:
            json.dump({"x": {}}, handle)
        order = []
        real = withdrawal.withdraw

        def recover(root, now):
            order.append(("withdraw", stale(root)))
            return real(root, now)
        with mock.patch.object(withdrawal, "withdraw", side_effect=recover), \
                mock.patch.object(graph, "register_missing", side_effect=lambda *a, **k: order.append(("graph", stale(s["root"])))), \
                mock.patch.object(supervisor, "_python", side_effect=lambda *a: order.append(("python", stale(s["root"]))) or (0, 0)):
            out = supervisor.run(s["root"], executors="x:Y", max_cycles=1, poll_s=0)
        m1 = s["models"]["m1"]
        self.assertEqual([("withdraw", m1), ("graph", None), ("python", None)], order)  # 그래프·Python 전에 이미 복구됨
        self.assertEqual(None, out["withdrawal"]["restore"]["model_id"])
        depth, path = kit.longest("supervisor.run")
        self.assertLessEqual(depth, 4, path)
        self.assertLessEqual(kit.longest("withdrawal.withdraw")[0] + 1, 4)  # run에서 직접 부른다(래퍼 없음)


if __name__ == "__main__":
    unittest.main()

"""B5-6: route_history(결정론 검사기 기록 → route 이력). 합성 작업을 실제 queue(enqueue·claim·complete)로 완료시킨다.

claude·모델 호출 없음. 검사 유형은 아직 dedupe 목록에 없어 시험 안에서만 더한다(통합 때 추가).
"""
import json
import os
import tempfile
import unittest
from unittest import mock

from harness import contract as ct
from harness import dedupe, lease, manifest, queue, route, route_history
from harness.jsonio import read_json, write_json
from tests import harness_depth_kit as kit
from tests.test_harness_support import make_contract

FULL = ["data", "checker", "criteria"]


def done(root, name, task_type, deps=(), llm=True, body=None, inputs=None):
    """작업 하나를 등록해 VERIFIED까지 만든다. body가 있으면 산출물은 판정 기록(VERDICT)이다. task_key."""
    task = make_contract(name, depends_on=list(deps), task_type=task_type, needs_llm=llm, inputs=inputs or {"in.txt": "a" * 64},
                         outputs=(route_history.VERDICT,) if body is not None else ("result.txt",))
    task["risk"] = name  # 같은 유형·입력의 재시도를 다른 계약으로 만든다
    with mock.patch.object(dedupe, "PLAIN_TYPES", dedupe.PLAIN_TYPES | set(route_history.CHECKER_TYPES)):
        key = queue.enqueue(root, task, 1.0)
    claimed = queue.claim(root, key, os.getpid(), lease.boot_id(), 2.0)
    out = os.path.join(root, "tasks", key, "out")
    os.makedirs(out)
    with open(os.path.join(out, task["outputs"][0]), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(body))
    with open(os.path.join(root, "tasks", key, ct.COMPLETION), "w", encoding="utf-8") as handle:
        json.dump({"task_key": key, "outputs": manifest.build(out, task["outputs"])}, handle)
    queue.complete(root, key, claimed["run_id"], claimed["lease"], 3.0)
    return key


def judged(root, name, target, cause, ruled_out=FULL, kind="quality_gate", **extra):
    """target을 판정한 검사 작업(needs_llm=false)."""
    return done(root, name, kind, [target], False, dict({"target_task_key": target, "cause": cause, "ruled_out": ruled_out}, **extra))


class RouteHistoryTest(unittest.TestCase):
    def test_chain_follows_the_existing_escalation_and_stop_rules(self):
        root, policy, deps, seen = tempfile.mkdtemp(), route.load_policy(), [], []
        causes = ("quality_gate_miss", "verification_failed", "unresolved_disagreement", "quality_gate_miss", "quality_gate_miss")
        for n in range(6):
            attempt = done(root, "try%d" % n, "general_dev", deps)
            history = route_history.history(root, attempt, policy)
            self.assertEqual([h["cause"] for h in history], list(causes[:n]))
            self.assertEqual(history, route_history.history(root, attempt, policy))  # 재시작해도 같은 이력(읽기 전용)
            contract = read_json(os.path.join(root, "tasks", attempt, "contract.json"))
            got = route.route(contract, history, policy)  # claude_job처럼 runtime(사용량 예산) 없이
            seen.append((got["model"], got["effort"], got["pending"], got["xhigh_used"], len(got["escalations"])))
            if n < 5:
                deps = [judged(root, "gate%d" % n, attempt, causes[n])]
        self.assertEqual(seen, [("sonnet", "medium", False, False, 0), ("sonnet", "high", False, False, 1),
                                ("opus", "high", False, False, 2), ("opus", "high", True, False, 2),
                                ("opus", "high", True, False, 2), ("opus", "high", True, False, 2)])
        # 마지막 결정은 pending인데 model이 남아 있다: 연결부가 pending이면 실행하지 않아야 반복이 멈춘다(통합 필수)
        self.assertEqual((got["model"], got["pending"], got["request_user"]), ("opus", True, False))

    def test_gate_failure_alone_or_a_non_model_problem_never_escalates(self):
        policy = route.load_policy()
        cases = {"확인 없음": [("quality_gate_miss", [])], "데이터만 확인 안 함": [("quality_gate_miss", ["checker", "criteria"])],
                 "검사기 확인 안 함": [("verification_failed", ["data", "criteria"])],
                 "기준 확인 안 함": [("unresolved_disagreement", ["data", "checker"])],
                 "데이터 부족": [("data_shortage", [])], "이미지 품질": [("image_quality", FULL)], "검사기·기준 오류": [("code_error", [])],
                 "정책에 없는 원인": [("criteria_problem", FULL)],
                 "검사기 둘 중 하나가 데이터 문제": [("quality_gate_miss", FULL), ("data_shortage", [])],
                 "검사기 둘 중 하나가 확인 모자람": [("quality_gate_miss", FULL), ("verification_failed", [])]}
        for name, verdicts in cases.items():
            with self.subTest(name):
                root = tempfile.mkdtemp()
                first = done(root, "first", "general_dev")
                gates = [judged(root, "g%d" % i, first, c, r) for i, (c, r) in enumerate(verdicts)]
                history = route_history.history(root, done(root, "second", "general_dev", gates), policy)
                got = route.route(make_contract(task_type="general_dev", needs_llm=True), history, policy)
                self.assertEqual((len(history), got["effort"], got["escalations"], got["pending"]), (1, "medium", [], False))
        root = tempfile.mkdtemp()  # 한 번의 시도를 검사기 둘이 실패시켜도 한 단계만(다른 하나가 통과해도 실패는 남는다)
        first = done(root, "first", "general_dev")
        gates = [judged(root, "g1", first, "quality_gate_miss"), judged(root, "g2", first, "verification_failed", kind="reverification"),
                 judged(root, "g3", first, None, [], kind="promotion_judge")]
        second = done(root, "second", "general_dev", gates)
        history = route_history.history(root, second, policy)
        self.assertEqual((len(history), sorted(history[0]["checker_task_keys"])), (1, sorted(gates)))
        self.assertEqual(route.route(make_contract(task_type="general_dev", needs_llm=True), history, policy)["effort"], "high")
        passed = judged(root, "ok", second, None, [])  # 통과하면 이전 실패는 다음 작업에 이어지지 않는다
        self.assertEqual(route_history.history(root, done(root, "third", "general_dev", [passed]), policy), [])
        mixed = judged(root, "data", second, "data_shortage", [])  # 데이터 문제 회차는 올리지도 내리지도 않는다
        history = route_history.history(root, done(root, "third2", "general_dev", [mixed]), policy)
        self.assertEqual([h["cause"] for h in history], ["quality_gate_miss", "data_shortage"])
        self.assertEqual(route.route(make_contract(task_type="general_dev", needs_llm=True), history, policy)["effort"], "high")

    def test_only_deterministic_checker_records_of_a_previous_attempt_count(self):
        root, policy = tempfile.mkdtemp(), route.load_policy()
        first = done(root, "first", "general_dev")
        claim = {"target_task_key": first, "cause": "quality_gate_miss", "ruled_out": FULL}
        fakes = [done(root, "claude-says", "misanalysis_general", [first], True, claim),  # 모델이 쓴 같은 형식
                 done(root, "llm-gate", "quality_gate", [first], True, claim),  # 검사 유형 이름 + needs_llm=true
                 done(root, "generic", "deterministic", [first], False, claim),  # 정해진 검사 유형이 아님
                 done(root, "silent-gate", "quality_gate", [first], False)]  # 원인 기록을 선언하지 않은 검사 작업
        os.makedirs(os.path.join(root, "tasks", first, "failures"))
        with open(os.path.join(root, "tasks", first, "failures", "001-ab.json"), "w", encoding="utf-8") as handle:
            json.dump({"cause": "quality_gate_miss", "kind": "deterministic", "run_id": "ab"}, handle)
        self.assertEqual(route_history.history(root, done(root, "second", "general_dev", fakes), policy), [])
        real = judged(root, "gate", first, "quality_gate_miss")
        self.assertEqual(len(route_history.history(root, done(root, "retry", "general_dev", [real]), policy)), 1)
        more = {"in.txt": "a" * 64, "gate.json": "b" * 64}  # 근거를 더한 재시도는 같은 작업이다
        self.assertEqual(len(route_history.history(root, done(root, "retry+", "general_dev", [real], inputs=more), policy)), 1)
        for name, task_type, inputs in (("analysis", "misanalysis_general", None), ("next-batch", "general_dev", {"in.txt": "c" * 64}),
                                        ("renamed", "general_dev", {"other.txt": "a" * 64})):
            with self.subTest(name):  # 판정 결과를 분석하는 다른 작업·다음 묶음은 상속하지 않는다
                self.assertEqual(route_history.history(root, done(root, name, task_type, [real], inputs=inputs), policy), [])
        script = done(root, "script", "general_dev", llm=False)  # 모델을 쓰지 않은 실행의 실패는 모델 상향 이력이 아니다
        after = judged(root, "gate-script", script, "quality_gate_miss")
        self.assertEqual(route_history.history(root, done(root, "after-script", "general_dev", [after]), policy), [])
        indirect = done(root, "middle", "misanalysis_general", [real])  # 검사 작업에 직접 의존하지 않으면 귀속하지 않는다
        self.assertEqual(route_history.history(root, done(root, "far", "general_dev", [indirect]), policy), [])

    def test_forged_damaged_or_misattributed_records_hold_the_job_instead_of_resetting(self):
        root, policy = tempfile.mkdtemp(), route.load_policy()
        first, stranger = done(root, "first", "general_dev"), done(root, "stranger", "general_dev")
        ok = {"target_task_key": first, "cause": "quality_gate_miss", "ruled_out": FULL}
        bad = {"의존하지 않은 대상": dict(ok, target_task_key=stranger), "경로 대상": dict(ok, target_task_key="../x"),
               "Xhigh 필요성 끼워 넣기": dict(ok, xhigh_justified=True), "사용자 요청 끼워 넣기": dict(ok, learning_value_high=True),
               "원인 숫자": dict(ok, cause=1), "원인 빈 문자열": dict(ok, cause=""), "ruled_out 문자열": dict(ok, ruled_out="data"),
               "ruled_out 모름": dict(ok, ruled_out=FULL + ["x"]), "ruled_out 중복": dict(ok, ruled_out=["data", "data"]),
               "키 누락": {"target_task_key": first, "cause": None}, "목록": [ok]}
        for name, body in bad.items():
            with self.subTest(name), self.assertRaises(route_history.RouteHistoryError):
                gate = done(root, "bad-" + name, "quality_gate", [first], False, body)
                route_history.history(root, done(root, "after-" + name, "general_dev", [gate]), policy)
        gate = judged(root, "gate", first, "quality_gate_miss")
        second = done(root, "second", "general_dev", [gate])
        other = judged(root, "gate-s", stranger, "quality_gate_miss")  # 서로 다른 두 시도의 판정에 함께 의존: 순서를 모른다
        with self.assertRaisesRegex(route_history.RouteHistoryError, "순서"):
            route_history.history(root, done(root, "both", "general_dev", [gate, other]), policy)
        waiting = make_contract("w", depends_on=["f" * 64], task_type="general_dev", needs_llm=True)
        pending = queue.enqueue(root, waiting, 4.0)  # 의존 계약이 없으면 검사 작업인지 알 수 없다
        for key in (pending, "e" * 64):
            with self.assertRaises(route_history.RouteHistoryError):
                route_history.history(root, key, policy)
        for victim, rel, text in ((gate, "out/" + route_history.VERDICT, json.dumps(dict(ok, cause=None))),  # 검증 뒤 바꿔치기
                                  (first, "out/result.txt", "changed"), (gate, "done.json", None)):  # 대상 손상, 미검증 검사 작업
            path = os.path.join(root, "tasks", victim, rel)
            with open(path, "rb") as handle:
                saved = handle.read()
            if text is None:
                os.remove(path)
            else:
                with open(path, "w", encoding="utf-8") as handle:
                    handle.write(text)
            with self.subTest(rel), self.assertRaises(route_history.RouteHistoryError):
                route_history.history(root, second, policy)
            with open(path, "wb") as handle:
                handle.write(saved)
        record = os.path.join(root, "tasks", gate, "done.json")
        saved = read_json(record)  # 판정 파일·해시는 맞지만 완료 기록이 계약과 어긋난(CORRUPT) 검사 작업
        write_json(record, dict(saved, manifest=dict(saved["manifest"], extra="0" * 64)))
        with self.assertRaisesRegex(route_history.RouteHistoryError, "VERIFIED"):
            route_history.history(root, second, policy)
        write_json(record, saved)
        self.assertEqual(len(route_history.history(root, second, policy)), 1)

    def test_read_bytes_are_rechecked_against_the_done_manifest_and_depth_fits(self):
        root = tempfile.mkdtemp()
        first = done(root, "first", "general_dev")
        gate_dir = os.path.join(root, "tasks", judged(root, "gate", first, "data_shortage", []))
        self.assertEqual(route_history._verdict(gate_dir)["cause"], "data_shortage")
        with open(os.path.join(gate_dir, "out", route_history.VERDICT), "w", encoding="utf-8") as handle:
            json.dump({"target_task_key": first, "cause": "quality_gate_miss", "ruled_out": FULL}, handle)
        with self.assertRaises(route_history.RouteHistoryError):  # VERIFIED 판정과 읽기 사이에 바뀐 바이트도 거절한다
            route_history._verdict(gate_dir)
        depth, path = kit.longest("route_history.history")
        self.assertLessEqual(depth + 2, 4, path)  # supervisor.run -> claude_job.execute -> history


if __name__ == "__main__":
    unittest.main()

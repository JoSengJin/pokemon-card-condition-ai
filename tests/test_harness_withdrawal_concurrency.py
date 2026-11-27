"""철회와 승격의 동시 실행(실제 하위 프로세스, 지연 주입): 잠금 순서 silver → registry가 같아 교착 없이 직렬화되고, 철회 시작 기록 뒤에
영향 모델로의 승격 전환은 0건이다. 순서는 장부 ts(호출 시작 시각)가 아니라 하위 프로세스가 장부 쓰기 직후 공용 순서 기록(order.log)에 남긴
실제 쓰기 순서로 비교한다(쓰기와 순서 기록 사이에 잠금을 놓지 않으므로, 잠금이 지켜지면 두 프로세스의 쓰기 순서가 그대로 남는다). 합성 시험이다."""
import json
import os
import random
import subprocess
import sys
import time
import unittest

from tests.test_harness_champion_support import REPO, add_model, pointer_model
from tests.test_harness_withdrawal_support import scenario

HOLD = "policy_withdrawn_hold"
# withdraw: 철회 시작 기록을 쓴 직후 flag를 만들고 delay초 잠금을 쥔 채 멈춘다. promote: 적격성 판정 뒤 전환 직전에 flag를 만들고 멈춘다
CONC = r'''
import json, os, sys, time
from harness import champion, ledger, silver_store, withdrawal
root, mode, arg, delay, flag = sys.argv[1], sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5]
real_append = ledger.append
def logged(path, ts, event, data):
    entry = real_append(path, ts, event, data)
    with open(os.path.join(root, "order.log"), "a") as handle:  # 장부 쓰기 직후의 실제 순서(같은 잠금 안)
        handle.write(json.dumps([event, data.get("target"), data.get("reason")]) + "\n")
    return entry
ledger.append = logged
def mark():
    open(flag, "w").close()
    time.sleep(delay)
if mode == "withdraw":
    real = silver_store.append
    def append(r, now, event, data):
        entry = real(r, now, event, data)
        if event == "policy_withdrawn":
            mark()
        return entry
    silver_store.append = append
    print(json.dumps(withdrawal.withdraw(root, time.time(), **json.loads(arg))))
else:
    real = champion._switch
    def switch(*args):
        mark()
        return real(*args)
    champion._switch = switch
    print(json.dumps(champion.promote(root, time.time(), arg)))
'''


def spawn(root, mode, arg, delay, flag):
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.Popen([sys.executable, "-c", CONC, root, mode, arg, str(delay), flag], cwd=REPO, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


def order(root):
    """하위 프로세스들이 남긴 실제 장부 쓰기 순서 [(이벤트, 대상, 사유)...]."""
    with open(os.path.join(root, "order.log"), "r", encoding="utf-8") as handle:
        return [tuple(json.loads(line)) for line in handle.read().split("\n") if line]


def finish(case, procs, flag=None):
    """flag가 생길 때까지 기다린 뒤(주어지면) 모든 프로세스의 출력 JSON을 돌려준다. 교착이면 시간 초과로 실패한다."""
    deadline = time.time() + 20
    while flag is not None and not os.path.exists(flag) and time.time() < deadline:
        time.sleep(0.005)
    outs = [p.communicate(timeout=30) for p in procs]
    case.assertEqual([0] * len(procs), [p.returncode for p in procs], outs)
    return [json.loads(out) for out, _ in outs]


class WithdrawalConcurrencyTest(unittest.TestCase):
    def test_a_promotion_that_starts_during_a_withdrawal_is_refused(self):
        s = scenario(self)
        r, flag = s["root"], os.path.join(s["root"], "withdraw.flag")
        kw = json.dumps({"policy_id": s["policy"], "reason": "unclear"})
        withdrawing = spawn(r, "withdraw", kw, 0.5, flag)
        finish(self, [], flag)  # 철회 시작 기록이 쓰였고 철회 쪽은 잠금을 쥔 채 멈춰 있다
        promoting = spawn(r, "promote", s["models"]["c2"], 0, os.path.join(r, "promote.flag"))
        withdrawn, promoted = finish(self, [withdrawing, promoting])
        self.assertEqual((False, HOLD), (promoted["ok"], promoted["reason"]))
        self.assertEqual((s["models"]["m2"], s["models"]["m2"]), (pointer_model(r), withdrawn["conditional"]["model_id"]))

    def test_a_withdrawal_that_starts_during_a_promotion_waits_for_it(self):
        s = scenario(self)
        r, flag = s["root"], os.path.join(s["root"], "promote.flag")
        promoting = spawn(r, "promote", s["models"]["c2"], 0.5, flag)  # 적격성 판정을 마치고 전환 직전에 멈춘다
        finish(self, [], flag)
        withdrawing = spawn(r, "withdraw", json.dumps({"policy_id": s["policy"], "reason": "unclear"}), 0, os.path.join(r, "w.flag"))
        promoted, withdrawn = finish(self, [promoting, withdrawing])
        self.assertTrue(promoted["ok"])  # 철회 전에 판정·전환을 끝낸 승격(그 시점에는 적격)
        written = order(r)
        self.assertLess(written.index(("switched", s["models"]["c2"], "promote")), written.index(("policy_withdrawn", None, "unclear")),
                        written)  # 철회 시작 기록은 승격 전환이 끝난 뒤에야 쓰였다(잠금 직렬화)
        self.assertEqual(s["models"]["c2"], withdrawn["conditional"]["model_id"])  # 그 Champion은 이어서 조건부 유지로 기록된다

    def test_random_races_never_promote_an_affected_model_after_the_withdrawal_record(self):
        rng = random.Random(20261127)
        for round_no in range(6):
            s = scenario(self)
            r = s["root"]
            s["models"]["x2"] = add_model(r, "x2", batches=["b2"])  # 철회 전에는 적격(b2 감사 통과)
            kw = json.dumps({"policy_id": s["policy"], "reason": rng.choice(["unclear", "contamination"]), "batches": None})
            procs = [spawn(r, "withdraw", kw, rng.uniform(0, 0.05), os.path.join(r, "w.flag"))]
            time.sleep(rng.uniform(0, 0.08))
            procs += [spawn(r, "promote", s["models"][name], rng.uniform(0, 0.05), os.path.join(r, name + ".flag")) for name in ("c2", "x2")]
            finish(self, procs)
            written = order(r)
            first = next(n for n, row in enumerate(written) if row[0] == "policy_withdrawn")
            late = [row for row in written[first:] if row[0] == "switched" and row[2] == "promote"
                    and row[1] in (s["models"]["c2"], s["models"]["x2"])]
            self.assertEqual([], late, (round_no, written))  # 철회 기록 뒤의 영향 모델 승격 0건


if __name__ == "__main__":
    unittest.main()

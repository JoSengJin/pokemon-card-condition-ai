"""Silver 시험 공용 도구(시험 없음). 합성 후보·정책·묶음·장애 주입 하위 프로세스. 사진·라벨·모델은 쓰지 않는다."""
import json
import os
import signal
import subprocess
import sys

from harness import audit, champion, silver_gate, silver_policy, silver_store
from tests.test_harness_champion_support import add_model, make_root

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCOPE = {"defect_type": "corner", "stratum": "front", "label_value": "normal"}
EMPTY = {"image_shas": [], "group_ids": []}
PROTECTED = {"sealed": EMPTY, "calibration": EMPTY}
FAST = {"initial": 0.5, "floor": 0.1, "initial_rounds": 1}  # 작은 묶음용(합성 값, 권고 아님)
# 하위 프로세스가 ledger.append를 감싸 "before|after:<이벤트>:<n번째>" 지점에서 스스로 SIGKILL을 맞는다
KILL = r'''
import json, os, signal, sys
from harness import audit, ledger, silver_gate
root, mode, point, payload = sys.argv[1], sys.argv[2], sys.argv[3], json.loads(sys.argv[4])
when, event, nth = point.split(":") if point != "none" else ("none", "", "0")
real, seen = ledger.append, {}
def append(path, ts, name, data):
    seen[name] = seen.get(name, 0) + 1
    hit = when != "none" and name == event and seen[name] == int(nth)
    if hit and when == "before":
        os.kill(os.getpid(), signal.SIGKILL)
    entry = real(path, ts, name, data)
    if hit and when == "after":
        os.kill(os.getpid(), signal.SIGKILL)
    return entry
ledger.append = append
if mode == "verdicts":
    audit.record_verdicts(root, 9.0, payload["batch_id"], payload["verdicts"])
else:
    silver_gate.judge_candidates(root, 9.0, payload["batch_id"], payload["policy_id"], payload["candidates"], payload["protected"], {},
                                 criteria_version="c1", model_version="m1")
print("SURVIVED")
'''


def approve(root, scope=SCOPE, n=50, errors=2, batch="cal-confirm-1", now=1.0):
    """보정 확인용 묶음 결과로 정책을 승인하고 정책 ID를 돌려준다(오류율 4%, 상한 이하)."""
    result = silver_policy.approve(root, now, scope, {"batch_id": batch, "role": "confirm", "n": n, "errors": errors},
                                   cap=0.10, min_n=50)
    assert result["ok"], result
    return result["policy_id"]


def cands(count, prefix="img", scope=SCOPE, uncertain=False, group="grp"):
    """에이전트 후보 count개(정책 범위 안, 확실). image_sha는 prefix 기준 고유."""
    return [{"image_sha": "%s%03d" % (prefix, i), "zone": "z1", "group_id": "%s%03d" % (group, i), "defect_type": scope["defect_type"],
             "stratum": scope["stratum"], "label_value": scope["label_value"], "uncertain": uncertain} for i in range(count)]


def judge(root, batch_id, policy_id, candidates, now=2.0, verifiers=None, protected=None):
    """품질 관문 호출 줄임(기본: 봉인·보정 비어 있음, 검증 함수 없음)."""
    return silver_gate.judge_candidates(root, now, batch_id, policy_id, candidates, protected or PROTECTED, verifiers or {},
                                        criteria_version="c1", model_version="m1")


def stored_labels(root):
    """저장소에 쓰인 Silver·Pending 라벨 이벤트의 data 목록(저장 순서)."""
    return [e["data"] for e in silver_store.load(root) if e["event"] in ("silver_label", "pending_label")]


def al_pool(count):
    """능동 학습 합성 후보 count개. 점수가 모두 달라 순위가 결정적이다."""
    pool = []
    for i in range(count):
        offset = (i - count / 2) / (count * 3.0)
        pool.append({"region_id": "r%03d" % i, "image_sha": "sha%03d" % i, "zone": "z%d" % (i % 4), "group_id": "g%03d" % (i // 2),
                     "seller_id": "s%02d" % (i % 7), "cluster_id": "c%d" % (i % 5), "defect_type": "corner" if i % 3 else "surface",
                     "stratum": "front" if i % 2 else "back", "error_type": "FN" if i % 4 else "FP", "expected_label": "normal",
                     "score": 0.5 + offset * (1 + i / 1000.0), "threshold": 0.5})
    return pool


def run_kill(case, root, mode, point, payload):
    """하위 프로세스를 지정 지점에서 SIGKILL로 죽인다(point가 "none"이면 끝까지 실행해 SURVIVED를 확인)."""
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-c", KILL, root, mode, point, json.dumps(payload)], cwd=REPO, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if point == "none":
        case.assertEqual((0, "SURVIVED\n"), (proc.returncode, proc.stdout), proc.stderr)
    else:
        case.assertEqual(-signal.SIGKILL, proc.returncode, (point, proc.stdout, proc.stderr))
        case.assertNotIn("SURVIVED", proc.stdout)


def cascade_setup(case, champion_is_failing=True):
    """감사 실패 시험용 상태: 정책 하나, 묶음 b1(Silver 20개, 감사율 50%라 표본 10개), 모델 base·m1(b1 사용)·c1(m1의 자식)·u(무관).

    champion_is_failing=True이면 base → c1 승격(c1은 호출자가 audit_status를 직접 줘서 승격 = 감사 상태를 잘못 준 경우 등 복원 경로 시험용),
    False이면 base → u 승격이다. 반환 dict: root, policy_id, ids(b1의 Silver 라벨 ID), sample(표본 ID), models(base·m1·c1·u).
    """
    root = make_root(case)
    policy_id = approve(root)
    ids = judge(root, "b1", policy_id, cands(20))["silver"]
    plan = audit.plan_audit(root, 3.0, "b1", seed=7, schedule=FAST)["plan"]
    models = {"base": add_model(root, "base")}
    models["m1"] = add_model(root, "m1", batches=["b1"])
    models["c1"] = add_model(root, "c1", parent=models["m1"])
    models["u"] = add_model(root, "u", batches=["b0"])
    assert champion.promote(root, 4.0, models["base"])["ok"]
    target = models["c1"] if champion_is_failing else models["u"]
    assert champion.promote(root, 5.0, target, {"b1": "complete", "b0": "not_required"})["ok"]
    return {"root": root, "policy_id": policy_id, "ids": ids, "sample": plan["sample_ids"], "models": models}

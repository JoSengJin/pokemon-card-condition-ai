"""철회·적격성 시험 공용 도구(시험 없음). 합성 정책·묶음·모델 상태, 옛 코드가 남긴 상태 모사, 최종 상태 요약, 장애 주입 하위 프로세스.

사진·라벨·모델은 쓰지 않는다. 합성 시험이며 라벨 품질·모델 성능 근거가 아니다.
"""
import json
import os
import signal
import subprocess
import sys

from harness import audit, audit_rate, champion, eligibility, ledger, registry, silver_gate, silver_policy, silver_store
from tests.test_harness_champion_support import REPO, add_model, make_root
from tests.test_harness_silver_support import SCOPE, cands, judge

SCHEDULE = dict(audit_rate.SUGGESTED_SCHEDULE)  # D-3 제안값(초기 10%): 묶음 20개면 표본 2개
OTHER = dict(SCOPE, label_value="defect")  # 영향받지 않는 다른 정책 범위
# 하위 프로세스: ledger.append와 포인터·복원 가중치의 os.replace 앞뒤("before|after:<이름>:<n번째>")에서 스스로 SIGKILL을 맞는다.
# point가 "none"이면 끝까지 실행하고 지나간 지점 목록(JSON)을 출력한다.
KILL = r'''
import json, os, signal, sys
from harness import audit, champion, ledger, withdrawal
root, point, call = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
real_append, real_replace, seen, trace = ledger.append, os.replace, {}, []
def hit(name, when):
    seen[name] = seen.get(name, 0) + (when == "before")
    tag = "%s:%s:%d" % (when, name, seen[name])
    trace.append(tag)
    if tag == point:
        os.kill(os.getpid(), signal.SIGKILL)
def append(path, ts, event, data):
    hit(event, "before")
    entry = real_append(path, ts, event, data)
    hit(event, "after")
    return entry
def replace(src, dst):
    name = "pointer" if dst.endswith("champion.json") else "weights" if dst.endswith("weights") else None
    if name is None:
        return real_replace(src, dst)
    hit(name, "before")
    real_replace(src, dst)
    hit(name, "after")
ledger.append, os.replace = append, replace
if call["fn"] == "withdraw":
    withdrawal.withdraw(root, 9.0, **call["kw"])
else:
    audit.record_verdicts(root, 9.0, call["batch_id"], call["verdicts"])
print(json.dumps(trace))
'''


def make_batch(root, batch, state="complete", scope=SCOPE, count=20, now=2.0):
    """범위의 승인 정책(없으면 승인)에 묶음 하나를 만든다. state: unplanned|planned|partial|complete|failed|not_required. 정책 ID를 돌려준다.

    감사율은 D-3 제안값 10%라 Silver 20개 묶음의 표본은 2개다. failed는 표본 1개 오류(1/2 > 10%): 작은 표본의 단일 오류 실패.
    """
    approval = silver_policy.approve(root, now, scope, {"batch_id": "cal-" + scope["label_value"], "role": "confirm", "n": 50, "errors": 2},
                                     cap=0.10, min_n=50)
    policy = approval["policy_id"]  # 이미 승인돼 있으면 already_approved와 함께 그 정책 ID가 온다
    rows = [dict(c, label_value=None) for c in cands(2, prefix=batch)] if state == "not_required" else cands(count, prefix=batch, scope=scope)
    judge(root, batch, policy, rows, now=now)
    if state == "unplanned":
        return policy
    sample = audit.plan_audit(root, now, batch, seed=1, schedule=SCHEDULE)["plan"]
    sample = [] if sample is None else sample["sample_ids"]
    verdicts = {"complete": {i: "correct" for i in sample}, "failed": {i: "incorrect" for i in sample[:1]},
                "partial": {i: "correct" for i in sample[:1]}}.get(state)
    if verdicts:
        audit.record_verdicts(root, now, batch, verdicts)
    return policy


def legacy_promote(root, now, model_id):
    """옛 코드(호출자가 준 감사 상태를 믿던 승격)가 남겼을 수 있는 상태를 모사한다: 관문 없이 같은 WAL 전환만 쓴다."""
    with registry.lock(root):
        state = registry.load(root)
        holder = champion.current(root, state)
        champion._switch(root, now, state, model_id, "promote", holder["model_id"] if holder else None)


def scenario(case, champions=("base", "m2"), legacy=()):
    """정책 P(묶음 b2 감사 통과, b1 감사 대기)와 다른 정책 Q(묶음 o1 통과). 모델 base(Silver 없음)·m2(b2)·c2(m2의 자식)·m1(b1)·c1(m1의 자식)·u(o1).

    champions 순서로 승격하고, legacy에 든 이름은 관문 없이 옛 코드 방식으로 승격한다. 반환 {root, policy, other, models}.
    """
    root = make_root(case)
    policy = make_batch(root, "b2")
    make_batch(root, "b1", "planned")
    other = make_batch(root, "o1", scope=OTHER)
    models = {"base": add_model(root, "base"), "m2": add_model(root, "m2", batches=["b2"]), "m1": add_model(root, "m1", batches=["b1"]),
              "u": add_model(root, "u", batches=["o1"])}
    models["c2"] = add_model(root, "c2", parent=models["m2"])
    models["c1"] = add_model(root, "c1", parent=models["m1"])
    for n, name in enumerate(champions):
        if name in legacy:
            legacy_promote(root, 3.0 + n, models[name])
        else:
            assert champion.promote(root, 3.0 + n, models[name])["ok"], name
    return {"root": root, "policy": policy, "other": other, "models": models}


def sample_of(root, batch):
    """묶음의 감사 표본 라벨 ID 목록."""
    return audit_rate.fold_audit(silver_store.load(root))["batches"][batch]["plan"]["sample_ids"]


def snapshot(root, models):
    """최종 상태 요약(시각·해시 제외): 모델별 (레지스트리 상태, 적격성 사유), Champion, 전환 이력, 정책 상태, 학습 가능 라벨 수, 조건부 기록, 장부 체인."""
    entries = silver_store.load(root)
    state = registry.load(root)
    facts = eligibility.silver_facts(entries)
    manifests = eligibility.manifest_reasons(root, state, facts)
    names = {v: k for k, v in models.items()}
    names[None] = None
    holder = champion.read_current(root)
    return {"models": {n: (state["models"][m]["status"], (eligibility.model_reason(state, facts, manifests, m) or {}).get("reason"))
                       for n, m in models.items()},
            "champion": names[holder["model_id"]] if holder else None, "history": [names[h["model_id"]] for h in state["history"]],
            "pending_switch": state["pending"], "policies": sorted((p["version"], p["scope"]["label_value"], p["status"]) for p in facts["policies"].values()),
            "trainable": len(silver_gate.trainable_labels(root)),
            "conditional": [names[e["data"]["model_id"]] for e in entries if e["event"] == "champion_conditional"],
            "chains": [ledger.verify(os.path.join(root, rel)) for rel in (silver_store.STORE, registry.REGISTRY, "ledger.jsonl")]}


def run_point(case, root, point, call):
    """KILL 하위 프로세스를 point에서 죽인다. point가 "none"이면 끝까지 실행하고 지나간 지점 목록을 돌려준다."""
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-c", KILL, root, point, json.dumps(call)], cwd=REPO, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if point == "none":
        case.assertEqual(0, proc.returncode, proc.stderr)
        return json.loads(proc.stdout)
    case.assertEqual(-signal.SIGKILL, proc.returncode, (point, proc.stdout, proc.stderr))
    return None

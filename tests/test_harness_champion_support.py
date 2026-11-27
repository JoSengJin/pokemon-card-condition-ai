"""Champion 시험 공용 도구(시험 없음). 합성 모델 등록(학습 manifest를 CAS에 함께 보관)·하위 프로세스 실행·장부 읽기."""
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile

from harness import cas, eligibility, registry, silver_store

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENOM = "defect-zones:n=120"
# 하위 프로세스가 ledger.append·os.replace·os.fsync를 감싸 지정 지점에서 스스로 SIGKILL을 보낸다
KILL = r'''
import os, signal, sys
import json
from harness import champion, ledger, withdrawal
root, arg, point, mode = sys.argv[1:5]
real_append, real_replace, real_fsync = ledger.append, os.replace, os.fsync
armed = {"on": False}
def die():
    os.kill(os.getpid(), signal.SIGKILL)
def append(path, ts, event, data):
    if point == "before_intent" and event == "switch_intent":
        die()
    if point == "before_invalidated" and event == "invalidated":
        die()
    entry = real_append(path, ts, event, data)
    armed["on"] = armed["on"] or event == "switch_intent"
    if (point, event) in (("after_intent", "switch_intent"), ("after_switched", "switched"), ("after_invalidated", "invalidated"),
                          ("after_main_ledger", "champion_promoted"), ("after_main_ledger", "champion_restored")):
        die()
    return entry
def replace(src, dst):
    if point == "before_materialize_replace" and dst.endswith("weights"):  # 복원 중 CAS 꺼내기
        die()
    if not dst.endswith("champion.json"):
        return real_replace(src, dst)
    if point == "before_replace":
        die()
    real_replace(src, dst)
    if point == "after_replace":
        die()
def fsync(fd):
    if point == "before_pointer_fsync" and armed["on"]:
        die()
    real_fsync(fd)
ledger.append, os.replace, os.fsync = append, replace, fsync
if mode == "promote":
    champion.promote(root, 9.0, arg)
elif mode == "restore":
    champion.restore_last_verified(root, 9.0, regression="killed regression", model_id=arg)
else:  # withdraw: arg는 withdrawal.withdraw의 키워드 인자 JSON
    withdrawal.withdraw(root, 9.0, **json.loads(arg))
print("SURVIVED")
'''


def make_root(case):
    root = tempfile.mkdtemp(prefix="champion-")
    case.addCleanup(shutil.rmtree, root, True)
    return root


def add_model(root, name, layer="sealed", denominator=DENOM, seal="seal-v1", batches=(), parent=None,
              grade="Challenger", config=None, now=1.0, manifest=None):
    """합성 모델 하나를 등록하고 모델 ID를 돌려준다. 가중치는 이름에서 만든 고정 바이트다.

    학습 manifest(eligibility.MANIFEST_FORMAT)를 CAS에 넣고 그 SHA를 data_manifest_sha로 쓴다. manifest를 안 주면 선언한 묶음의 Silver 라벨
    (저장 당시 등급 Silver) 전부로 학습했다고 적는다(등록 시점의 Silver 장부 기준). dict는 JSON으로, bytes는 그대로 쓴다(불일치 시험용).
    """
    src = os.path.join(root, "incoming", name)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, "wb") as handle:
        handle.write(("weights-" + name).encode())
    if manifest is None:
        ids = sorted(e["data"]["label_id"] for e in silver_store.load(root) if e["event"] == "silver_label" and e["data"]["batch_id"] in batches)
        manifest = {"format": eligibility.MANIFEST_FORMAT, "silver_batches": sorted(set(batches)), "silver_label_ids": ids}
    with open(src + ".manifest", "wb") as handle:
        handle.write(manifest if isinstance(manifest, bytes) else json.dumps(manifest, sort_keys=True).encode())
    result = registry.register(
        root, now, src, hashlib.sha1(name.encode()).hexdigest(), cas.put(os.path.join(root, "cas"), src + ".manifest"),
        config or {"lr": 0.001, "name": name},
        {"layer": layer, "denominator": denominator, "seal_version": seal, "metrics": {"miss": 0.2}},
        list(batches), parent=parent, grade=grade)
    assert result["ok"], result
    return result["model_id"]


def read_events(root, rel=registry.REGISTRY):
    """해시 체인 JSONL의 이벤트 목록(없으면 빈 목록)."""
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle.read().splitlines()]
    except FileNotFoundError:
        return []


def pointer_model(root):
    try:
        with open(os.path.join(root, registry.POINTER), "r", encoding="utf-8") as handle:
            return json.load(handle)["model_id"]
    except FileNotFoundError:
        return None


def kill_at(case, root, point, mode, arg):
    """실제 하위 프로세스가 지정한 지점에서 스스로 SIGKILL을 맞게 한다(mode: promote|restore|withdraw, arg: 모델 ID 또는 withdraw 인자 JSON)."""
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-c", KILL, root, arg, point, mode], cwd=REPO, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    case.assertEqual(-signal.SIGKILL, proc.returncode, (point, proc.stdout, proc.stderr))
    case.assertNotIn("SURVIVED", proc.stdout)


def assert_consistent(case, root, allowed):
    """kill -9 뒤의 불변식: 장부 체인 정상, 포인터는 allowed 중 하나의 유효한 Champion을 완전하게 가리킨다(없으면 allowed에 None)."""
    from harness import champion, ledger  # 순환 import 방지: support는 registry 쪽만 먼저 읽는다
    state = registry.load(root)
    case.assertEqual([], ledger.verify(os.path.join(root, "ledger.jsonl")))
    holder = champion.current(root, state)
    case.assertIn(holder["model_id"] if holder else None, allowed)
    if holder is not None:
        case.assertTrue(holder["valid"])
        case.assertTrue(cas.has(os.path.join(root, "cas"), state["models"][holder["model_id"]]["weights_sha"]))
    return state


def bad_copy(cas_root, sha, dest):
    """CAS가 이름과 다른 내용을 내주는 경우(복사 중 변조 모사). cas.get(cas_root, sha, dest)을 그대로 대체한다."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as handle:
        handle.write(b"not the weights")

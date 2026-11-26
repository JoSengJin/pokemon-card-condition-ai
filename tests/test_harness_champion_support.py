"""Champion 시험 공용 도구(시험 없음). 합성 모델 등록·하위 프로세스 실행·장부 읽기."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

from harness import registry

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DENOM = "defect-zones:n=120"


def make_root(case):
    root = tempfile.mkdtemp(prefix="champion-")
    case.addCleanup(shutil.rmtree, root, True)
    return root


def add_model(root, name, layer="sealed", denominator=DENOM, seal="seal-v1", batches=(), parent=None,
              grade="Challenger", config=None, now=1.0):
    """합성 모델 하나를 등록하고 모델 ID를 돌려준다. 가중치는 이름에서 만든 고정 바이트다."""
    src = os.path.join(root, "incoming", name)
    os.makedirs(os.path.dirname(src), exist_ok=True)
    with open(src, "wb") as handle:
        handle.write(("weights-" + name).encode())
    result = registry.register(
        root, now, src, hashlib.sha1(name.encode()).hexdigest(), hashlib.sha256(b"data-" + name.encode()).hexdigest(),
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


def run_py(code, *args):
    """실제 하위 프로세스(경로는 저장소 루트 기준). 종료 코드와 표준 출력을 함께 돌려준다."""
    env = dict(os.environ, PYTHONPATH=REPO, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run([sys.executable, "-c", code] + [str(a) for a in args], cwd=REPO, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return proc


def assert_consistent(case, root, allowed):
    """kill -9 뒤의 불변식: 장부 체인 정상, 포인터는 allowed 중 하나의 유효한 Champion을 완전하게 가리킨다(없으면 allowed에 None)."""
    from harness import cas, champion, ledger  # 순환 import 방지: support는 registry만 먼저 읽는다
    state = registry.load(root)
    case.assertEqual([], ledger.verify(os.path.join(root, "ledger.jsonl")))
    holder = champion.current(root, state)
    case.assertIn(holder["model_id"] if holder else None, allowed)
    if holder is not None:
        case.assertTrue(holder["valid"])
        case.assertTrue(cas.has(os.path.join(root, "cas"), state["models"][holder["model_id"]]["weights_sha"]))
    return state


def bad_copy(dest):
    """CAS가 이름과 다른 내용을 내주는 경우(복사 중 변조 모사). cas.get 대체용 lambda가 부른다."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as handle:
        handle.write(b"not the weights")

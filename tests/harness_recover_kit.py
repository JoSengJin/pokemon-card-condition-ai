"""B5-1(VS6) 철회 복구 시험 공용 도구(시험 없음): 끊긴 철회 장면, root 파일 비교, 결함 판정, 실제 진입점 1회차 실행. 합성 root만 쓴다."""
import json
import os
import subprocess

from harness import champion, eligibility, registry, silver_store
from tests.test_harness_champion_support import REPO
from tests.test_harness_supervisor_kit import SUPERVISOR
from tests.test_harness_withdrawal_support import run_point, sample_of, scenario

RESTORE = {"champions": ("base", "m2", "m1"), "legacy": ("m1",)}  # m1 철회 → m2는 보류라 제외 → base로 복원
CLEAR = {"champions": ("m2", "m1"), "legacy": ("m1",)}  # 적격 후보 없음 → Champion 없음


def call_for(s, fn):
    """장면 s의 철회 호출: withdraw = 수동 철회 batch_label_error [b1], verdicts = b1 감사 표본 오류(자동 철회)."""
    if fn == "withdraw":
        return {"fn": "withdraw", "kw": {"policy_id": s["policy"], "reason": "batch_label_error", "batches": ["b1"]}}
    return {"fn": "verdicts", "batch_id": "b1", "verdicts": {sample_of(s["root"], "b1")[0]: "incorrect"}}


def interrupted(case, setup=CLEAR, point="after:policy_withdrawn:1", fn="withdraw"):
    """setup 장면을 만들고 철회를 point에서 실제 SIGKILL로 끊는다. 장면 dict."""
    s = scenario(case, **setup)
    run_point(case, s["root"], point, call_for(s, fn))
    return s


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
    """실제 진입점 `python -m harness.supervisor --max-cycles 1` 한 번(별도 프로세스). 출력 요약 dict."""
    proc = subprocess.run(SUPERVISOR + ["--root", root, "--max-cycles", "1", "--poll", "0"], cwd=REPO,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          universal_newlines=True)
    case.assertEqual(0, proc.returncode, proc.stderr)
    return json.loads(proc.stdout.strip().split("\n")[-1])

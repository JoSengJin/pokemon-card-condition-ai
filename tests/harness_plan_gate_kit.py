"""VS3 PLAN_GATE 시험 공용 도구(시험 없음). 합성 원본 저장소·대조 실험 계약·가짜 실험 executor·완료된 Claude 분석 흉내.

- 실제 ./experiment·실제 claude·모델·네트워크를 부르지 않는다. 가짜 실험 executor(EXECUTORS)는 원본 저장소에 미리 심은 동결 기록
  artifacts/experiments/<experiment_id>/를 읽어 산출물로 옮길 뿐이다(sandbox 안에서도 돈다: 원본 쓰기 없음). 실험 폴더 이름은 가설 ID로 정한다.
- 이 모듈은 sandbox 자식이 executor 표로 가져오므로 가져올 때 파일을 쓰지 않는다(git 도구는 world 안에서 가져온다).
"""
import functools
import hashlib
import json
import os
import shutil
import tempfile

from harness import contract as ct
from harness import cas, experiment_exec, lease, manifest, queue, runner
from harness.jsonio import read_json, write_json

NOW = 1_894_000_000.0  # 2030-01(주 경계와 멀다)
PARAM = {"name": "lr", "baseline": 0.5, "value": 0.6, "scope": "head"}
ACCEPT = {"max_fp": 3, "max_fn": 2, "no_new_errors": True, "require_actual_point_guard": False}


def world(case):
    """(하네스 root, 원본 git 저장소, HEAD). 원본의 artifacts/는 추적하지 않는다(./experiment 기록 자리)."""
    from tests.test_harness_git_kit import git, git_source  # 가져올 때 임시 git 저장소를 만드는 모듈(sandbox 자식에서는 가져오지 않는다)
    base = tempfile.mkdtemp(prefix="vs3-")
    case.addCleanup(shutil.rmtree, base, True)
    root, src = os.path.join(base, "root"), os.path.join(base, "src")
    git_source(src)
    with open(os.path.join(src, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("artifacts/\n")
    git(src, "add", ".gitignore")
    git(src, "commit", "-q", "-m", "ignore artifacts")
    return root, src, git(src, "rev-parse", "HEAD")


def control(head, value=0.6, hid="H1", **plan):
    """사람이 등록하는 대조 실험 계약(experiment_parameter 관례, 수치 기준·기준 결과·code_changes 포함). plan 키워드로 plan을 덮어쓴다(None = 삭제)."""
    body = {"experiment_parameter": dict(PARAM, value=value), "reference_result": "artifacts/ref/result.json", "acceptance": dict(ACCEPT),
            "code_changes": [{"path": "card_condition/head.py", "baseline": None}]}
    body.update(plan)
    return {"task_type": "experiment", "inputs": {}, "outputs": list(experiment_exec.OUTPUTS), "depends_on": [], "needs_llm": False,
            "needs_vision": False, "risk": "high", "retry_policy": {}, "escalation_level": 0,
            "run_conditions": {"command": ["python", "-m", "card_condition.worker"], "code_sha": head, "seed": 1,
                               "config": {"plan": {k: v for k, v in body.items() if v is not None}}, "hypothesis_id": hid,
                               "description": {"hypothesis": "학습률이 누락에 영향", "change": "lr 하나", "success_criterion": "fn<=2",
                                               "failure_criterion": "fn>2"}}}


def seed(src, hid):
    """원본 저장소에 가설 hid의 동결 기록(./experiment가 남기는 record·result·plan)을 심는다. 실험 폴더 경로."""
    folder = os.path.join(src, "artifacts", "experiments", "20300101T000000-" + hashlib.sha256(hid.encode()).hexdigest()[:8])
    os.makedirs(folder, exist_ok=True)
    for name, body in (("plan.json", {"hypothesis_id": hid, "schema_version": 1}), ("result.json", {"rows": [], "scores": [0.1]})):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            json.dump(body, handle)
    sha = {n: cas.sha_file(os.path.join(folder, n)) for n in ("plan.json", "result.json")}
    with open(os.path.join(folder, "record.json"), "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 1, "experiment_id": os.path.basename(folder), "hypothesis_id": hid, "status": "completed",
                   "files": sha}, handle)
    return folder


def fake_experiment(task, out_dir):
    """가짜 실험 executor: runner가 넣은 원본 경로(HARNESS_SOURCE_ROOT)의 심은 기록을 산출물로 옮긴다. 하위 프로세스·원본 쓰기 없음."""
    hid = task["run_conditions"]["hypothesis_id"]
    folder = os.path.join(os.environ[experiment_exec.SOURCE_ENV], "artifacts", "experiments",
                          "20300101T000000-" + hashlib.sha256(hid.encode()).hexdigest()[:8])
    write_json(os.path.join(out_dir, "plan.json"), experiment_exec.build_plan(task))
    for name in ("record.json", "result.json"):
        shutil.copyfile(os.path.join(folder, name), os.path.join(out_dir, name))
    return list(experiment_exec.OUTPUTS)


EXECUTORS = {"experiment": fake_experiment}


def verified(root, src, task):
    """task를 등록하고 기록을 심은 뒤 가짜 executor로 실행해 VERIFIED로 만든다(sandbox 없는 drain). task_key."""
    seed(src, task["run_conditions"]["hypothesis_id"])
    key = queue.enqueue(root, task, NOW, source_root=src)
    runner.drain(root, EXECUTORS, now_fn=functools.partial(float, NOW), source_root=src)
    return key


def proposal(parent, value=0.7, **over):
    """Claude가 쓸 next_plan.json 내용: 대조 plan의 value만 바꾼 적격 제안. over로 키를 덮어쓴다(None = 삭제)."""
    plan = json.loads(json.dumps(parent["run_conditions"]["config"]["plan"]))
    plan["experiment_parameter"]["value"] = value
    body = {"hypothesis_id": "H-next", "hypothesis": "lr를 더 올리면 누락이 준다", "change": "lr 0.6→0.7",
            "variable": "experiment_parameter.value", "plan": plan}
    body.update(over)
    return {k: v for k, v in body.items() if v is not None}


def finish(root, key, files):
    """등록된 Claude 작업이 산출물 files({경로: 내용 dict 또는 글자})를 쓰고 완료된 것처럼 큐에 반영한다(가짜 claude 없이 VERIFIED)."""
    task_dir = os.path.join(root, "tasks", key)
    for rel, body in files.items():
        os.makedirs(os.path.dirname(os.path.join(task_dir, "out", rel)), exist_ok=True)
        with open(os.path.join(task_dir, "out", rel), "w", encoding="utf-8") as handle:
            handle.write(body if isinstance(body, str) else json.dumps(body))
    outputs = read_json(os.path.join(task_dir, "contract.json"))["outputs"]
    write_json(os.path.join(task_dir, ct.COMPLETION), {"task_key": key, "outputs": manifest.build(os.path.join(task_dir, "out"), outputs)})
    res = queue.claim(root, key, os.getpid(), lease.boot_id(), NOW)
    queue.complete(root, key, res["run_id"], res["lease"], NOW)

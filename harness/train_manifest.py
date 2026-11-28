"""학습 manifest v2를 하네스가 만든다(B5-7, b924753 결함 ②의 선언 쪽). executor·학습 코드가 쓴 manifest는 믿지 않는다.

입력은 학습 작업 계약의 inputs({상대 경로: sha256})와 작업 폴더 in/의 사본(runner가 실행 직전 SHA를 확인해 만든 것), Silver 장부 사실
(eligibility.silver_facts), 레지스트리 모델 목록뿐이다. 계약 입력 경로 규칙(pre-b5 결정 7은 미정이라 승인 범위 안 기본값으로 정했다: 계약 필드·
dedupe 논리 키를 바꾸지 않는 안, 근거는 task 문서):
- parents/<모델 ID 64자>/<파일>: 학습 시작 가중치. 많아야 하나. 그 입력 SHA가 그 모델의 weights_sha와 같아야 한다. 없으면 처음부터 학습(None).
- silver/labels.json: 학습에 쓴 Silver 라벨 목록. silver_gate.trainable_labels 출력 형식(label_id를 가진 dict 목록)을 그대로 쓴다.
  label_id만 읽고 묶음·등급은 파일이 아니라 Silver 장부에서 찾는다. silver/ 아래 다른 입력은 거절(어느 것이 라벨인지 판별 불가).
- 그 밖의 입력 중 SHA가 등록 모델의 가중치와 같은 것은 거절(undeclared_parent_weights: 부모를 생략하고 가중치를 다른 이름으로 넣는 경로).
모든 입력 사본은 다시 해시해 계약 SHA와 대조한다(다르거나 없거나 링크면 input_copy_mismatch). 거절은 TrainManifestError(args[0] = 사유).
한계: 학습 코드가 inputs 밖(원본 경로·네트워크)에서 가중치·라벨을 읽는 것은 여기서 알 수 없다(runner 한계와 같다). 가중치 바이트가 같은
두 모델은 구분하지 못한다.
호출 깊이: build → check_copies → cas.sha_file (2). parent_of·silver_of는 말단(silver_of는 json만 쓴다).
"""
import json
import os
import re

from . import cas
from .eligibility import MANIFEST_FORMAT

SILVER_INPUT = "silver/labels.json"
PARENTS = "parents"
_HEX64 = re.compile(r"[0-9a-f]{64}")


class TrainManifestError(Exception):
    """args = (사유, 설명). 사유는 apply_train 결과의 reason이 된다."""


def check_copies(task_dir, inputs):
    """in/ 사본이 모두 일반 파일이고 SHA가 계약과 같은지(대소문자 무시) 확인한다. 안전하지 않은 경로는 input_path."""
    base = os.path.realpath(os.path.join(task_dir, "in"))
    for rel, want in sorted(inputs.items()):
        parts = rel.split("/")
        if rel.startswith("/") or any(p in ("", ".", "..") for p in parts):
            raise TrainManifestError("input_path", rel)
        path = os.path.join(base, *parts)
        if os.path.islink(path) or not os.path.isfile(path) or os.path.commonpath([base, os.path.realpath(path)]) != base \
                or cas.sha_file(path) != str(want).lower():
            raise TrainManifestError("input_copy_mismatch", rel)


def parent_of(inputs, models):
    """(부모 모델 ID 또는 None, 시작 가중치 SHA 또는 None). 말단."""
    weights = {rec["weights_sha"] for rec in models.values()}
    declared = [(rel, str(sha).lower()) for rel, sha in sorted(inputs.items()) if rel.split("/")[0] == PARENTS]
    stray = sorted(rel for rel, sha in inputs.items() if rel.split("/")[0] != PARENTS and str(sha).lower() in weights)
    if stray:
        raise TrainManifestError("undeclared_parent_weights", stray)
    if len(declared) > 1:
        raise TrainManifestError("parent_ambiguous", [rel for rel, _ in declared])
    if not declared:
        return None, None
    rel, sha = declared[0]
    parts = rel.split("/")
    if len(parts) < 3 or not _HEX64.fullmatch(parts[1]):
        raise TrainManifestError("parent_path", rel)
    if parts[1] not in models:
        raise TrainManifestError("unknown_parent", parts[1])
    if models[parts[1]]["weights_sha"] != sha:
        raise TrainManifestError("parent_weights_mismatch", parts[1])
    return parts[1], sha


def silver_of(task_dir, inputs, facts):
    """(묶음 목록, 라벨 ID 목록) 둘 다 정렬. 라벨 입력이 없으면 빈 목록. 말단."""
    named = sorted(rel for rel in inputs if rel.split("/")[0] == SILVER_INPUT.split("/")[0])
    if named and named != [SILVER_INPUT]:
        raise TrainManifestError("silver_ambiguous", named)
    if not named:
        return [], []
    try:
        with open(os.path.join(task_dir, "in", *SILVER_INPUT.split("/")), "r", encoding="utf-8") as handle:
            rows = json.load(handle)
    except (OSError, ValueError) as exc:
        raise TrainManifestError("silver_format", str(exc))
    if not isinstance(rows, list) or not all(isinstance(r, dict) and isinstance(r.get("label_id"), str) for r in rows):
        raise TrainManifestError("silver_format", "label_id(문자열)를 가진 dict 목록이어야 한다")
    ids = [r["label_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise TrainManifestError("silver_duplicate_label", sorted({i for i in ids if ids.count(i) > 1}))
    unknown = sorted(i for i in ids if i not in facts["labels"])
    if unknown:
        raise TrainManifestError("silver_unknown_label", unknown[:5])
    return sorted({facts["labels"][i]["batch_id"] for i in ids}), sorted(ids)


def build(task_dir, task, facts, models):
    """학습 작업 계약 → (manifest v2 dict, 부모 모델 ID 또는 None). 거절은 TrainManifestError."""
    check_copies(task_dir, task["inputs"])
    parent, start = parent_of(task["inputs"], models)
    batches, ids = silver_of(task_dir, task["inputs"], facts)
    return {"format": MANIFEST_FORMAT, "silver_batches": batches, "silver_label_ids": ids, "start_weights_sha": start}, parent

# eBay 수집 f·g·h 라벨의 기존 manifest 절차 편입

- task_id: label-intake-adoption-fgh-20261031
- owner: Claude (Codex 토큰 만료 기간 대행; 사용자 지시 2026-10-31 "라벨저장이 다른 방향으로 가는 게 문제가 될까봐")
- status: assigned (계약 확정 전 구현 없음)
- base_sha: 819af83 (main)
- approval: 사용자 요청은 라벨 저장 방식을 기존 방향으로 맞추는 것. 새 정답·분할·모델 학습/추론은 승인되지 않음. 기존 정상/결함 라벨 변경 없음.

## 현재 상태 (실측)
- f·g·h 사람 답은 intake 폴더의 원본 텍스트(`pairing-answers.txt`, `back-edge-answers.txt`, `corner-answers.txt`, `region-answers.txt`)에만 있고 개발 manifest(`development-manifest-20261030c`)에는 0건이다.
- 앞뒤 선택은 f에서 쓰던 `ebay_pair_selection/v0` JSON 형식으로 g·h를 추가 기록했다(`pair-selection.20261030.json`, `pair-selection.20261031.json`; Git 제외 artifacts, 데이터만).
- 기존 채택 절차: 검토 행(JSONL, `side_annotations`·`region_labels`·`box_reviewed`·`reviewed_by`) → `tools/freeze_dev_manifest.py`(새 val 행만 채택, 기준 manifest SHA 고정, 감사·coverage 재생성). 새 manifest는 새 폴더이며 기존 것은 덮어쓰지 않는다.

## 결정이 필요한 것 (구현 전 확정)
1. 분할: `freeze_dev_manifest.py`는 val 행만 채택한다. h는 val(3차 head 첫 평가에 쓴 사진)이 자연스럽다. f·g는 학습에 쓴 실험이 있어 val/train 어느 쪽에 둘지 정책이 없다.
2. 모서리 4점(g·f 일부)은 manifest에 대응 필드가 없다. 보류하고 원본 파일로 보존할지, 필드를 새로 만들지(스키마 변경)를 정해야 한다.
3. 중복: `ebay-pair-270a6a12881028`은 g와 h에 모두 있다(같은 사진 해시). 한 번만 채택한다.
4. 사진 위치: 기존 행은 `learn/<id>/front·back` 경로를 쓴다. intake 폴더 경로를 그대로 쓸지 learn으로 복사할지 정해야 한다.

## 구현 범위 (확정 후)
allowed_files(안): `tools/adopt_intake_answers.py`(새), `tests/test_adopt_intake_answers.py`(새), 이 문서. 기존 파일 수정 없음.
structure(안): 새 파일 함수 7개 이하, 호출 깊이 4 이하. 검사: 합성 fixture로 라벨 불변·해시 일치·중복 거절, 실제 h 변환 후 원본 텍스트와 건수 대조.
forbidden: 기존 manifest·라벨 파일·Codex 소유 미추적 도구 수정, 학습·추론·API 호출.

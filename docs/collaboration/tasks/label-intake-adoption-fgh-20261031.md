# eBay 수집 g·h 라벨의 기존 검토 UI·manifest 절차 편입

- task_id: label-intake-adoption-fgh-20261031
- owner: Claude (Codex 토큰 만료 기간 대행. 사용자 지시 2026-10-31: Codex의 개발 방식대로 진행, 역할 대행이 아니라 절차를 따를 것)
- status: implementing
- base_sha: 64ac22b (main)
- approval: 라벨 저장을 기존 방식으로 맞춤. 새 정답 생성·모델 학습/추론·API 호출 승인 아님. 기존 라벨 변경 없음.

## 근거 (실측, 2026-10-31)
- Codex a~e 배치 절차: 앞뒤 선택 JSON(`ebay_pair_selection/v0`) → 각 intake 폴더의 `convert_pairs.py` → `val-candidates-*.jsonl`(split=val, labels null, pair_verified, reviewed_by) → `build_inventory.py`+`autobox.py` → `review/labels-review.jsonl` → `card_condition/review.py` 서버와 `review.html`에서 사람이 상자·구역·점·빛 반사·관찰 제한을 저장 → `tools/freeze_dev_manifest.py` 채택.
- g·h의 선택 JSON은 이미 같은 스키마다. 따라서 위 도구를 그대로 쓴다. 새 변환 도구는 만들지 않는다.
- 이전에 만든 텍스트 답(`region-answers.txt` 등)은 구역 종류·빛 반사·관찰 제한·점이 없어 학습 라벨과 의미가 달라 변환하지 않는다(`point_dataset.py`·`regions.py::validate_annotations` 대조). 같은 사진을 `review.html`에서 다시 확인받는다.

## 결정 (근거 포함)
1. 분할: a~e와 같게 `val`. 후보 notes에 "학습·D1 사용 금지"가 붙는다. 근거: `ebay-intake-20261027-e/convert_pairs.py`.
2. 모서리 4점: manifest에 대응 필드가 없다. 스키마를 바꾸지 않고 원본 파일로 보존한다.
3. 중복 `ebay-pair-270a6a12881028`: g에 두고 h 선택 사본에서는 `exclude`로 한다. 원본 선택 파일은 바꾸지 않는다.
4. 사진 경로: a~e와 같이 intake 폴더 경로 그대로 쓴다.

## 범위
allowed_files: 이 문서. artifacts(Git 제외)의 `ebay-intake-20261030-g/`, `ebay-intake-20261031-h/` 아래 새 파일(복사한 `convert_pairs.py`·`build_inventory.py`·`autobox.py`, `val-candidates-*.jsonl`, `review/`). 코드 파일 수정 없음.
forbidden: 기존 manifest·`labels-review.jsonl`·Codex 도구 원본 수정, 학습·추론·API 호출, 사람이 입력하지 않은 라벨 생성.
structure: 새 소스 파일 없음(함수 수 변경 0, 호출 경로 변경 0).
checks: `convert_pairs.py`가 `load_manifest` 검증과 중복 거절을 통과하는지, 인벤토리가 `validate_annotations`를 통과하는지, 행 수가 선택 JSON의 pair 수와 일치하는지.
experiment: 없음.
handoff(작성 예정): 행 수, 해시, 실행 로그 경로, 사람 확인이 필요한 항목(상자·구역·점), 미검증, 롤백(새 파일 삭제).

# 검토 완료 train 배치를 새 개발 manifest로 편입하는 도구

- task_id: adopt-train-batches-20261031
- owner: Claude (Codex 토큰 만료 기간 대행)
- status: assigned
- base_sha: 5405595 이후 main (구현 시 `git rev-parse main`으로 기록)
- branch: claude/adopt-train-batches-20261031
- approval: 사용자 "남은 문제 토대로 진행해"(2026-10-31). 학습·추론·외부 호출·라벨 생성 승인 아님.

## 배경
`tools/freeze_dev_manifest.py`는 val 배치만 받는다(24행). eBay k 수집분 7쌍은 train 후보(`artifacts/ebay-intake-20261031-k/train-candidates-20261031-k.jsonl`)이고 사람 라벨이 끝나도 편입 경로가 없다. val 보호 장치는 느슨하게 하지 않고 train 전용 별도 도구를 만든다.

## 목표
검토 완료 train 배치 + 기존 manifest → 새 manifest 폴더. 기존 행·val 분모는 불변. 학습·검증 교차 방지 유지.

## 계약
- 입력: `--base`(경로)·`--base-sha256`·`--source`(train 배치, 반복)·`--output`(새 폴더, 존재하면 실패)·`--decided-by`.
- 거절: 기준 SHA 불일치, 소스에 split!=train 행, id 중복, 같은 group이 다른 split로 걸침, 소스 사진의 raw/decoded SHA가 기준 manifest에 이미 있음(교차 누수), 소스에 사람이 상자를 확인한 면(`box_reviewed`)이 하나도 없음.
- 불변 검증: 새 coverage의 val 셀이 기준 coverage의 val 셀과 같아야 한다(다르면 실패).
- 출력: `combined-reviewed.jsonl`, `coverage.json`, `audit.json`(freeze의 `audit` 재사용, train 오류는 공개만), `ADOPTION.json`(schema `development_manifest_adoption/v1-train`, labels_modified=false, training_calls=0, d1_use=false).

## 구조
- 새 파일 `tools/adopt_train_batches.py`: 함수 5개 이하, 호출 깊이 3 이하(`main→adopt→combine_train→leak_check`). `freeze_dev_manifest.py`는 수정하지 않고 `audit`만 import.
- 새 파일 `tests/test_adopt_train_batches.py`.

allowed_files: 위 새 파일 2개와 이 문서. forbidden: 기존 도구·manifest·라벨·review.html·모델 코드.

## checks
거절 6건과 val 불변 검사를 단위 테스트로 확인하고, 실제 데이터로는 k 라벨 완료 전이라 dry run 하지 않는다(소스에 확인된 상자가 없으면 실패하는 것이 정상).

## 롤백
새 파일 3개 `git revert`/삭제.

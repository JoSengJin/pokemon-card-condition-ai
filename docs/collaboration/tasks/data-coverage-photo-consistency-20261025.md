# 감사 입력 사진의 단계 간 일관성 — Codex

- task_id: `data-coverage-photo-consistency-20261025`
- owner: Codex
- status: implementing
- base_sha: `06db1cfb0b56a92db19db113fce2859158e13d53`
- branch: `codex/data-coverage-photo-consistency-20261025`

## 재현·목표

`coverage_report`의 첫 manifest 로딩과 `point_rows` 내부 두 번째 로딩 사이에 같은 경로의 사진 픽셀을 바꾸면, manifest SHA는 같지만 보고서에 첫 읽기의 사진 해시가 남는 반례를 합성 fixture에서 재현했다. 두 읽기에서 관측한 사진의 디코딩 해시가 같을 때만 감사를 저장한다. 사진 원본 파일을 잠그거나 실행 전체의 모든 순간에 불변임을 보증하는 범위는 아니다.

## allowed_files

- `card_condition/data_coverage.py`
- `card_condition/point_dataset.py`
- `tests/test_data_coverage_photo_consistency.py` (신규)
- `docs/collaboration/tasks/data-coverage-photo-consistency-20261025.md`
- `docs/collaboration/reports/data-coverage-photo-consistency-20261025.md` (신규)

Claude의 `provenance-source-followup-20261025` 문서 2개와 `pair-control` 소스는 읽기 전용이다. 기존 사람 라벨·원본 사진·모델·과거 artifacts·기준·진척률·운영 소비 코드는 수정하지 않는다.

## 최소 변경 계약

point_rows가 기존에 읽은 train/val 입력의 카드 ID·면별 디코딩 해시를 결과 메타데이터에 추가한다. coverage_report는 자신의 첫 입력 해시와 이 값을 비교하고 다르면 ValueError로 종료한다. 구역 투영이 없는 면도 비교 대상이다. test split은 계속 읽지 않고 excluded 레코드는 집계 대상에서 제외한다. 새 사진 디코딩·학습·추론·외부 모델 호출은 추가하지 않는다. patch·점·정상/결함·분모는 변경하지 않는다.

## checks·수용 기준

- 실제 픽셀 변경을 두 읽기 사이에 주입하는 합성 검사에서 거절하고 출력 파일이 생성되지 않아야 한다.
- 구역 patch가 없는 면의 사진 변경도 거절해야 한다.
- 파일 bytes가 달라도 디코딩 픽셀이 같으면 기존 디코딩 해시 계약대로 허용한다.
- 사진 메타데이터는 train/val만 포함하고 봉인된 test 라벨·사진을 해석하지 않는다.
- 기존 44개 감사·구역·검토 검사와 신규 검사, point_dataset 결과 메타데이터를 소비하는 point_comparison 회귀를 실행한다.
- 실제 개발/live manifest 재감사에서 기존 cells·units·typed_points·skipped·projection_skipped가 같고 manifest SHA가 유지돼야 한다. 새 출력 경로만 사용한다.
- source/worker 편집과 통합은 ./develop 잠금 안에서 진행한다. 통합 브랜치 검사 통과 후 main으로 fast-forward한다.

실패하면 main을 갱신하지 않고 실제 오류를 기록한다. 롤백은 후속 변경·실행 중 작업을 확인한 뒤 이 task의 수정 커밋을 ./develop 안에서 revert한다. 일반 학습·추론의 정책은 변경하지 않는다.

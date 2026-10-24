# 같은 구역의 종류별 정답 투영 계약 — 2026-10-25

개발 진척률 30/100 유지. 생산 소스 수정 없이 실제 누락 가능성 두 가지를 합성 입력으로 확인하고 회귀 검사를 추가했다. 모델 정확도 개선이나 실물 데이터의 정답 검증이 아니다.

## 확인한 계약

- 같은 좌표에 corner/edge/surface 세 종류의 사람점이 있어도 각 종류의 양성 구역 1·실물 1·실제점 1을 모두 보존한다. 점 입력 순서 여섯 가지를 대조했다.
- 한 구역의 edge 양성점과 명시적 surface 정상은 각각 1과 0으로 보존하고, 미확인 corner를 정상으로 만들지 않는다. 표면 정상 구역은 정상 점 좌표로 변환하지 않는다.
- 최초에 의심한 `data_coverage.py`의 구역별 dictionary가 다른 종류의 점을 덮어쓰는 문제는 재현되지 않았다. `point_rows(grid=True)`가 종류별 labels와 point_by_label을 병합한 결과를 반환하므로 기존 구현을 유지했다.

## 변경·검증

변경 파일은 신규 `tests/test_data_coverage_projection_contract.py`와 이 보고서다. 기존 42개 + 신규 2개 총 44개가 통과했고, 세 종류의 점 순서 검사는 6개 subtest를 포함한다. 최종시험 행의 라벨과 사진은 봉인된 합성 값으로 두어 해석하지 않는 경계도 유지했다.

실행: `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions test_review test_data_coverage_provenance test_data_coverage_projection_contract -q`.

로컬 근거: `artifacts/data-coverage-projection-contract-20261025T011150/tests.log`, `verification.json`. 학습·실제 모델 추론·외부 AI 호출은 없으며, 모델·라벨·실험 기준·생산 소스는 변경하지 않았다.

## 남은 의존성과 롤백

면·정정 이력의 근거 충족 여부는 별도 Claude task `provenance-source-followup-20261025`의 감사 결과를 받아야 판단한다. 이번 합성 검사가 그 출처 매핑을 증명하지 않는다. 후속 변경과 실행 중 작업을 확인한 뒤 이 테스트/문서 커밋만 revert하면 롤백된다. 원본 데이터·모델 복원은 필요 없다.

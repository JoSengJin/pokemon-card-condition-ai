# 반사 위치별 오류 평가 연결 — 2026-10-09

## 구현과 검증
- side_rows가 선택적 glare_areas를 보존한다.
- side-experiment와 reslice-visibility가 공통 집계 함수로 위치별 분포, validation 혼동행렬, 미확인 라벨 수, 위치 미지정 면 목록을 출력한다.
- 반사 위치는 진단용이다. 모델 입력·가중치·결함 정답·Gemini 분기에는 사용하지 않는다.
- 전체 27개 테스트 통과. 위치를 변경해도 학습 가중치/예측이 같고, 위치 재집계가 기존 전체 예측/지표를 보존하는지 검증했다. 미확인 표면을 정상으로 계산하지 않으며 test는 위치별 집계에서도 제외한다.

## 실제 데이터 결과
기준 모델 visibility-baseline-20261009의 report/model과 일치하는 visibility-labeled-20261009.jsonl을 기준으로, visibility-complete-20261009.jsonl의 진단 정보를 재집계했다. 잘못된 기준 snapshot은 해시 검사에서 차단됐다.

- train 40면 / val 18면의 기존 예측 사용. 재학습·test 평가 없음.
- 반사 사유 train 4면 / val 4면, 위치 지정 0면. 위치별 성능은 아직 계산할 수 없다.
- 반사 val 4면의 gradable: TP 1 / TN 0 / FP 3 / FN 0. 평가 불가 3면을 모두 평가 가능으로 오판했다.
- 원본 53개 묶음에는 반사 사유가 9면 있지만 고정 개발 자료에는 8면이 들어 있다. 원본 수와 개발용 수를 혼용하지 않는다.
- 예측과 전체 지표는 그대로이며 실제 Gemini 절감은 0건이다.

결과: artifacts/glare-location-audit-20261009.json. 사람이 위치를 지정한 뒤 기존 분할을 보존한 snapshot으로 reslice-visibility를 실행하면 위치별 실패를 확인할 수 있다. 위치만 수정하면 재학습이 필요하지 않다.

## 변경 파일과 롤백
card_condition/side_experiment.py, card_condition/reslice.py, tests/test_side_experiment.py, tests/test_reslice.py, README.md 및 이 기록. PokeCollector 운영 코드는 변경하지 않았다.

롤백은 side_rows의 glare_areas와 위치별 집계 함수를 제거하고 두 보고서 생성 경로의 기존 visibility 집계를 복원한다. 원본 라벨과 모델 파일은 유지한다. 새 진단 보고서는 소비 앱과 연결되지 않아 별도 보관하거나 삭제할 수 있다.

## 한계와 다음 순서
3×3 위치는 정확한 반사 마스크가 아니며 다중 위치 집계는 중복될 수 있다. 표본 4면의 수치를 일반화하지 않는다. 다음은 사람이 지정한 위치별 오류 원인 확인과 결함 위치 데이터 확보다. 현재 근거로 OpenCV/timm 추가나 운영 자동 통과를 결정하지 않는다.

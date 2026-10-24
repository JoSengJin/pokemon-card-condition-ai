# 신규 val 위치 진단 명령 — 2026-10-10

기존 ㄱ 검증 임시 스크립트를 `point-probe` 정식 CLI로 구현했다. 신규 사람이 확인한 val 카드로 모델을 같은 입력에서 비교하고, 학습을 반복하거나 완료한 라벨을 다시 요구하지 않는 것이 목적이다. 모델 정확도가 개선됐다는 변경은 아니다.

## 변경 파일과 핵심 diff

- `card_condition/point_probe.py`: 명시적 val 카드 선택, 기존 point_rows 고정3×3 재사용, 구역/좌표 모델 고정 추론·혼동행렬. 기본 학습·최종평가 경로에는 연결하지 않는다.
- `card_condition/cli.py`: point-probe 명령, 반복 --card/--history와 복수 체크포인트 입력.
- `tests/test_point_probe.py`: 합성 고정 head로 정상/결함 오판 비교, 원본/가중치 불변, 중복 이력/누락 metadata 차단, train/test/미존재 카드 거부, 반사로 제한된 정상 제외, NaN 결과 저장 차단.
- `pyproject.toml`: 0.4.15. `README.md`: 명령과 해석 범위.
- 마스터 `CONDITION_ANALYSIS_TODO.md`: 완료 기능·검증 근거 갱신.

검증 입력·모델·이력 파일 해시를 시작/종료 때 비교한다. 출력은 새 파일에만 기록한다. 모든 모델이 성공하기 전 보고서를 저장하지 않는다. 모델 가중치·원본 라벨·분할은 변경하지 않는다. 기본 RegionAnalyzer는 point_grid 체크포인트를 계속 거부한다.

## 실제 재현 결과

입력 `artifacts/point-evidence-20261010-round9.jsonl`, 카드 ㄱ만 선택, ㄱ 이전 개발 이력4개 제공. 결과 `artifacts/point-probe-korean-g-20261010.json`. 이전 임시 진단 `artifacts/korean-g-front-back-frozen-model-probe-20261010.json`과 두 모델의 혼동행렬·예측 확률 일치 확인.

| 고정 모델 | 정상 앞면 표면 TN/FP | 뒷면 모서리 TP/FN | 뒷면 표면 TP/FN |
|---|---|---|---|
| 기존 round6 | 9/0 | 2/0 | 1/0 |
| 좌표 보강 round8 | 0/9 | 2/0 | 1/0 |

실물1개·12구역이며 독립 실물12개가 아니다. 재현 실행으로 표본 수가 늘지 않는다. 좌표 보강 모델 채택 보류, 재학습·임계값 조정·운영 적용·Gemini 호출 절감 없음.

## 검증

- 전체 Python55개 통과: `/private/tmp/condition-point-probe-tests.log`.
- 신규 테스트4개 포함. 합성 test 사진 경로를 존재하지 않는 파일로 지정해 test를 열지 않음을 검증.
- 실제 CLI 실행 로그: `/private/tmp/condition-point-probe-run.log`.
- 0.4.15 wheel 빌드 성공: `/private/tmp/condition-point-probe-wheel.log`. wheel의 point_probe.py·cli.py가 현재 소스와 바이트 단위 일치.
- 기존 임시 진단과 두 모델 혼동행렬 일치·알려진 라벨의 확률 최대 차이0 확인. 원본 data/learn-review.jsonl SHA256도 이전 확인 영수증과 일치.
- `point-probe --help` 실행 확인. 별도 새 환경 설치와 운영 연동은 수행하지 않았다.

## 리스크·롤백

완전한 과거 개발 이력과 같은 실물의 group 지정은 호출자 책임이다. 픽셀 해시는 다른 크롭/재촬영 사진의 동일 실물을 자동 보장하지 않는다. 신규 val 진단은 최종 성능 증거가 아니며, 반복 검증을 독립 평가로 세면 안 된다. CPU 전용이며 속도·메모리 벤치마크는 수행하지 않았다.

롤백은 point_probe.py·신규 테스트를 제거하고 cli.py의 point-probe 등록/분기, README 신규 절, 버전을 이전으로 되돌린다. 기존 모델과 사람이 저장한 라벨은 복원하거나 삭제할 필요가 없다. 이번 보고서만 제거해도 기존 경로에는 영향이 없다.

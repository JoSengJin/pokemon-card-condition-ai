# 구역 최종평가 도구 및 완료 라벨 재학습 (2026-10-09)

## 변경 파일과 핵심 diff
- card_condition/region_evaluation.py: 새 region-evaluate. test-only manifest, 전체 개발 이력 필수, 카드 ID/그룹/디코딩 사진 해시 누수 차단. 가중치와 임계값을 변경하지 않는다.
- card_condition/region_dataset.py: 호출자가 test 분할을 명시해 읽을 수 있게 확장; 기본 train/val 격리 유지. 학습·추론용 card_box를 보존.
- card_condition/cli.py: 구역 최종평가 명령 연결.
- tests/test_region_evaluation.py: 독립 카드 평가, null 미채점, 결과 덮어쓰기 차단, ID/그룹/사진/과거 실험 누수 차단 검증.
- pyproject.toml: 0.4.2. README.md: 명령·독립 평가 한계 설명.
- REGION_HUMAN_REVIEW_20261009.md와 PokeCollector의 CONDITION_ANALYSIS_TODO.md: 완료된 위치 재확인 요구 제거, 최신 학습·다음 사람 확인 반영.

## 실제 저장 자료 재학습
사용자 원본 data/learn-review.jsonl을 변경 없이 artifacts/regions-labeled-20261009-complete.jsonl에 복사했다. 구역96개(train58/val38), 결함 위치 미지정0개. 분할 미지정 t는 학습하지 않았다. train 정상 구역은 세 결함 각각1개다. 이전 실험/모델은 유지했다.
MobileNetV3 Small 고정 특징 + head, seed42, epochs5, crop224, MPS. 선택 epoch2, 처리 약3.89초(초기 backbone 준비 제외).

| 결함 | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| 모서리 | 8 | 2 | 4 | 0 |
| 엣지 | 12 | 4 | 8 | 3 |
| 표면 | 16 | 2 | 10 | 2 |

보고서: artifacts/region-baseline-20261009-complete/report.json. snapshot/모델 hash 기록. 서로 다른 실물의 정상 사례가 부족하고 정상 오탐이 많아 채택 보류. 이전 라운드와 라벨이 달라 개선률을 주장하지 않는다.

## 검증
전체 Python36개 테스트 및 JS 검토 UI 회귀검사 통과. 최초 sandbox 실행은 임시 테스트 서버 bind 권한 때문에 실패했으며 권한 부여 후 전체 재실행으로 통과했다. 구역 테스트 추가 재실행 및 0.4.2 wheel 빌드도 수행했다.
실제 신규 최종평가 자료는 없어서 실카드 최종평가를 수행하지 않았다. 합성 테스트는 평가 경로의 동작 검증이며 실서비스 성능 근거가 아니다.

## 위험 및 롤백
관찰 불가를 정상/결함으로 대체하지 않는다. 최종평가 자료의 다른 촬영본은 사람이 실물 그룹으로 묶어야 하며 제출한 개발 이력이 완전한지 도구가 보증할 수 없다. 패치 정확도는 카드 전체 상태나 구매 판단 정확도가 아니다. 운영 변경과 실제 Gemini 절감은0건.
라벨 원본·서버·PokeCollector 런타임은 수정하지 않았다. 롤백은 기존0.4.1 wheel과 이전 region-baseline-20261009-next/model.pt를 사용하면 된다. 새 실험 폴더는 별도 보존돼 기존 모델을 덮어쓰지 않았다.

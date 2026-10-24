# 구역 모델 첫 실험 — 2026-10-09

## 결과와 범위
저장된 사람 라벨로 3×3 구역 모델 학습을 구현하고 실행했다. Gemini 호출 절감·운영 채택은0건이다. 전체 카드 등급이나 상태 점수를 출력하는 모델이 아니며, 사람이 지정한 구역의 명시적 결함 라벨만 학습한다.

자료: artifacts/regions-labeled-20261009-1211.jsonl, SHA256 084b32c5891d1019bd76e29a4caf765cf83038e2bd2b82b77251a1276c8607df. train33구역 / val35구역. 원본 data/learn-review.jsonl을 수정하지 않고 고정했다. split 미지정 t 및 제외 자료는 실험에 포함하지 않았다. test 이미지/라벨은 읽지 않는다.

| 항목 | train 정상/결함/미확인 | val 정상/결함/미확인 | val TP/TN/FP/FN |
|---|---|---|---|
| 모서리 | 1/9/23 | 6/7/22 | 7/2/4/0 |
| 엣지 | 1/11/21 | 12/11/12 | 8/4/8/3 |
| 표면 | 2/24/7 | 12/18/5 | 16/2/10/2 |

MobileNetV3 Small ImageNet 고정 특징, 구역 crop224, 3출력 head, AdamW lr.001, epochs5, seed42, MPS. 미확인/null은 loss와 지표에서 제외한다. train에서 두 클래스가 있는 출력만 학습하며 val에도 두 클래스가 필요하다. 최저 unweighted val BCE 회차2, BCE0.67266649. 비교 실험을 바로 과거 면별 지표와 비교할 수 없다: 입력 구역과 정답 단위가 다르다.

## 사람 확인
정상 사례가 극도로 적으며 반복 구역은 독립 실물 표본이 아니다. 학습용 정상 구역을 서로 다른 실물에서 보강하는 것이 우선이다. 결함 위치 미지정20건과 t 분할 미지정은 REGION_HUMAN_REVIEW_20261009.md에 준비했다. 기존 결함이 보이지 않으면 정답을 억지로 만들지 않고 사람이 재확인해야 한다. 모델 오류가 있다고 사람 라벨을 모델 쪽으로 바꾸지 않는다.

## 검증·산출물
- 최종 코드 전체35개 unittest 통과. 체크포인트 재로딩 예측 일치, 최저 val 회차 저장, 지원하지 않는 출력/null, test 이미지·라벨 격리, 덮어쓰기 차단 확인.
- node tests/review_validation.test.cjs 통과.
- 독립0.4.0 wheel 로컬 no-index/no-deps/no-build-isolation 빌드 및 새 모듈/CLI 포함 확인. artifacts/dist-regions-20261009/pokemon_card_condition-0.4.0-py3-none-any.whl. 별도 머신 설치는 미검증.
- 최종 실행 artifacts/region-baseline-20261009-v2/model.pt 및 report.json. 초기 실행 artifacts/region-baseline-20261009-1211도 보존. 두 실행의 지표 동일.
- 초기 실행 error-review.html: 빨간 박스 구역과 사람/모델 차이27항목을 표시. 사람이 검토할 자료이며 라벨 수정 없음.
- 체크포인트에 개발 그룹·카드ID·이미지 해시 기록. 사전학습 torchvision 공식 가중치 다운로드 외에 Gemini/eBay 호출 없음.

## 변경 파일과 롤백
새 card_condition/region_experiment.py, tests/test_region_experiment.py. card_condition/region_dataset.py에 카드ID/면/원본 이미지 해시 추가. CLI에 region-experiment 등록. README.md, pyproject.toml(0.4.0), 이 문서, 사람 확인 문서, CONDITION_ANALYSIS_TODO.md 갱신.

기존 모델·원본 라벨·PokeCollector runtime/DB는 보존했다. 롤백은 새 CLI 분기와 region_experiment 모듈·테스트를 제거하고 버전을0.3.1로 복원한다. 실험 산출물은 별도 보관하면 된다. 3×3 원근 오차와 편향된 작은 데이터 때문에 운영 성능·일반화 개선은 주장하지 않는다. 전용 추론 API와 최종평가 연결은 아직 구현하지 않았다.

# 엣지 누락 우선 재검토 — 0.4.84

사용자가 누락 감소를 우선하고 추가 의심을 재검토하는 방향을 선택했다. 독립 모델의 선택 옵션으로 연결했다. 소비 프로젝트의 운영 호출/구매 제외는 변경하지 않았다.

## 실험

동일 round21 자료, seed42/20epoch/균형 선택/고정 MobileNet/2×2 타일/판정0.5를 유지하고 입력224→448만 변경했다. 기존 검증27정답 구역(7실물, 결함15/정상12)에서:

| 방식 | TP | TN | FP | FN |
|---|---:|---:|---:|---:|
| 기존224 |12|8|4|3|
| 새448 |14|5|7|1|
| 둘 중 하나 의심 시 재검토 |14|5|7|1|

누락률20→6.67%(-13.33%p), 정상 오탐률33.33→58.33%(+25%p). 정확도74.07→70.37%로 낮아진다. 이 숫자는 재사용 검증 자료의 엣지 의심 검출이며 독립 일반화/불량 확정 정확도가 아니다. 표면·모서리 개선 주장은 하지 않는다.

복구한 누락: e/back 상단 중앙, w/front 좌측 하단. 기존 검출을 새로 놓친 곳0, 계속 놓친 곳 ebay-7db839f540a696/back 하단 중앙1. 심각도 정답이 없으므로 모든 결함에 임의 중요도 등급을 매기지 않았다.

448 단독 교체는 오탐 비증가 기준 실패로 미채택. 학습20시점 모두 FP>4여서 선택 시점만 바꿔 해결되지 않는다. 양성 train타일144개의 원본 긴축 중앙값99px,224초과12개로 확대가 원본 정보를 복원한다고 주장하지 않는다.

## 구현과 검증

- `card_condition/defect_regressions.py`, `comparison.py`: 같은 정답/사진/좌표 검증 후 새 누락·회복·지속 누락을 분리. 총 정확도 개선이 새 결함 누락을 숨기지 않도록 표시.
- `card_condition/recall_review.py`, `listing_model.py`: 선택적 `recall_checkpoint`의 의심 합집합을 `recall_review.candidates`에 출력. 기존 predictions와 readiness를 유지하며 review_required만 추가. 같은 지원 결함 종류 요구, 미확인/반사/사진 누락 구역 제외.
- `card_condition/cli.py`: `listing-predict --recall-checkpoint <model.pt>`.
- `tests/test_defect_regressions.py`, `tests/test_recall_review.py`: 새 누락 상쇄 금지, 종류 분리, 동점/미확인/기존 검출 유지 검증.
- `pyproject.toml`, `README.md`, 이 문서, 소비 TODO: 버전·근거·진행 갱신.

전체164테스트 통과(47.649초). 실제 9사진 묶음/27정답 구역의 API 검산에서 TP14/TN5/FP7/FN1, 가려진 면·관찰 미확인 면 후보0 확인. 단일448 API 점수와 학습 보고서 최대차1.79e-7. 입력55파일 hash 보존. 근거는 `artifacts/edge-resolution-20261012/`의 plan, verification, comparison, recall-api, recall-tests 로그.

재검토 후보는 결함 확정·자동 제외가 아니다. 실제 Gemini 호출을 보내지 않았고 절감0. 추가 모델 추론 시간/메모리와 검토 건수가 늘어나는 리스크가 있다. 새 독립 자료에서 일반화 검증이 남았다. 기반4/6(약67%) 유지.

## 사용·롤백

Python `ListingAnalyzer(existing_model, recall_checkpoint=candidate448_model)` 또는 CLI 선택 옵션을 사용한다. 옵션을 생략하면 기존 출력/모델 경로다. 코드 롤백은 `.backups/recall-routing-0484/`에서 listing_model.py·cli.py·pyproject.toml 복원 후 새 recall helper/tests 제거. 비교 기능까지 되돌리려면 `.backups/edge-recall-0483/`의 comparison.py 사용. 사람 라벨과 사진은 변경하지 않았다.

다음은 아직 사용하지 않은 새 실물의 엣지 결함/정상 구역을 통한 독립 검증이다. 완료 라벨 재작업 없이 새 자료가 제공되면 고정한 두 모델·0.5 기준으로 실행한다.

에튜: 두 모델의 의심 결과를 OR로 합치면 기존 검출을 취소하지 않아 누락을 줄일 수 있지만 오탐은 늘 수 있다. 그래서 최종 불량 판정 대신 재검토 목록에 사용한다.

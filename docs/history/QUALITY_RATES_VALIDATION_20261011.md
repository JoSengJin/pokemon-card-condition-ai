# 0.4.64 성능 변화 보고 자동화

개발 기반4/6(67%) 유지. 이번 변경의 AI 정확도 상승0%p: 모델·추론·라벨 변경 없이 기존 평가 지표의 분모와 변화량을 제공한다. 실제 Gemini 절감0건.

## 변경 파일 / 핵심 diff

- card_condition/quality_rates.py 신규: 검증된 혼동행렬에서 positive/negative/scored 분모·누락률·오탐률·정답률 및 candidate-reference %p 계산. 0분모 null, 음수/실수/bool count 거부. 같은 분모인지 검사하지만 입력 동일성 자체는 기존 상위 비교기가 확인한다.
- card_condition/score_diagnostics.py: 동일 알려진 라벨의 rates_at_05 추가. 기존 순위·보류·선택 정책 유지.
- card_condition/visibility_compare.py: quality_summary rates와 같은24면 대조 %p 제공. 기존 사진/box/group/정답/해시 대조 이후에만 계산.
- card_condition/comparison.py: 기존 전체면/구역/point 비교에 각 종류별 rates와 첫 모델 기준 %p. 기존 metric 검산·사진/영역/정답 동일성 검사 유지.
- card_condition/observation_crossfit.py: 기존 train 제외 검증 summary에 rates 추가, fit/threshold 불변.
- tests/test_quality_rates.py 신규, tests/test_score_diagnostics.py·test_visibility_compare.py·test_point_comparison.py: 분모·tradeoff·미확인·동일결과·잘못된 입력 거부 검증.
- pyproject.toml 0.4.64, AGENTS.md 정확도 보고 선호 영속, README.md·본 문서·artifacts/quality-rates-20261011와 마스터TODO.

## 기존 성과 재계산 — 이번 턴의 새 성능 상승이 아님

|항목|분모|이전→현재 누락률|이전→현재 오탐률|알려진 라벨 정답률|
|---|---|---|---|---|
|관찰 제한 공통→면별 centroid|제한7/비제한17면|57.14→42.86% (-14.29%p)|41.18→11.76% (-29.41%p)|54.17→79.17%|
|엣지 round20→round21|결함15/정상12구역|20→20% (0%p)|41.67→33.33% (-8.33%p)|70.37→74.07%|

관찰 제한과 카드 하자는 다른 타깃이다. 표의 수치는 재사용된 개발 val이며 독립 최종 성능/매물 전체 정확도/구매 판단이 아니다. 반복 검증에 의한 선택 편향은 여전히 남는다. 새 모델을 학습하거나 채택하지 않았다.

## 검증

전체133테스트 통과40.802초, 통합 assertion 보강 후 관련8테스트 통과. 실제 visibility-compare·point-compare CLI로 기존 보고서 재계산. 첫 point-compare에 패치 inputs.jsonl을 원본 manifest로 잘못 전달해 스키마가 거부했으며, 기존 비교 기록의 point-evidence-round20 원본 경로로 수정 후 성공. 사용자 라벨을 바꾸지 않았다.

설치본 테스트·동일 매물 CPU 추론·wheel 소스 및 원본/model/live 보존 결과는 artifacts/quality-rates-20261011/checks.json에 기록한다.

## 리스크 / 롤백

JSON에 부가 필드가 추가되어 전체 dict를 고정 비교하는 외부 소비자는 스냅샷 갱신이 필요할 수 있다. 운영 소비 코드는 변경하지 않았다. 단순 정답률은 클래스 불균형을 가릴 수 있어 누락·오탐·분모와 함께 제공한다. 한 클래스가 없으면 측정 불가율 null을0으로 바꾸지 않는다.

.backups/quality-rates-0464 아래 수정 전 파일을 같은 상대 경로로 복원하고 신규 quality_rates.py 및 test_quality_rates.py를 제거/보관하면0.4.63 경로로 돌아간다. 사용자 정확도 보고 선호는 AGENTS에서 보존한다. 모델과 라벨은 롤백 대상이 아니다.

에튜: 퍼센트포인트는 비율의 뺄셈이다. 오탐률41.67→33.33%는8.33%p 감소이며 상대적으로20% 감소다. 이번 코드는 혼동을 막기 위해 변화 필드를 change_percentage_points로 명시하고 정답률만 올랐을 때 오류 tradeoff를 숨기지 않는다.

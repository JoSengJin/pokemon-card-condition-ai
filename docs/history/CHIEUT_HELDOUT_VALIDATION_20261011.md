# 독립 앞면 반사 시험·실물별 평가 — 0.4.79

개발 기반4/6완료·독립 품질검증 진행. 고정 관찰 모델 독립3실물4면 TP0/TN3/FP0/FN1. 제한 누락1/1(100%), 정상 오탐0/3(0%). 면 정확도75%는 모든 면을 제한 없음으로 판정한 결과이므로 성공으로 해석하지 않는다. 앞면만 정상1/반사1 중 반사를 놓쳐 정확도50%. 양성은1실물뿐이고 다른 제한 종류 시험 지원은0. 같은 시험의 이전 결과가 없어 상승/%p 개선을 주장하지 않는다. 모델 변경 없음·Gemini절감0.

ㅊ-light-test 점수0.4957570433616638, 고정0.5 기준 누락. 시험 후 임계값 조정·학습 편입 없음. ranking_points는 사후 진단이며 기준 선택에 사용하지 않는다. 최초 evaluation/report.json은 수정하지 않고 SHA 5a2775ff7b6545e6a3698aeb7ed438678170526c82eee0ff8fa18b38634e5ff7로 보존했다.

## 실제 API 검증

ListingAnalyzer CPU batch 점수와 시험 점수 차이0.0. 사람 중앙 glare 표시는 모델 점수와 무관하게 observation_limited/unknown/score=null 보존. 뒷면 없음은 missing_photo, 관찰 정보 생략은 observation_not_reviewed. requires_gemini=true·production_ready=false. 이는 안전 경로 검증이며 자동 반사 판별 향상이 아니다.

## 변경·검증

- card_condition/observation_heldout.py: 기존 region_thresholds.group_error_rates 재사용, by_group·group_error_rates_at_05 추가. 추론/기준/정답 불변.
- tests/test_observation_heldout.py: 정상 두 면인 실물과 정상 한 면인 실물의 가중 차이 검증. 면 오탐2/3과 실물 평균1/2 구별·양성 없는 실물을 누락0으로 세지 않음.
- pyproject.toml 0.4.79, README.md, 준비/본 문서, 소비 CONDITION_ANALYSIS_TODO.md 상단.
- artifacts/chieut-heldout-20261011/: 최초 test-source.jsonl·evaluation/report.json, verify_api.py·api.json·checks.json·tests.log. checks.json에 기존 시험 예측의 실물별 보충 집계.

heldout 회귀6개 통과(1.377초), 전체152개 통과(48.859초). 실제 API 점수 일치·마스킹·미확인 보존과 모델/사진/live/기존 독립 라벨 해시 불변 검산 통과. 사용자 라벨 읽기만 수행. 전체/면별 결함 값의 해석은 이번 관찰 시험에 사용하지 않음. 패키지 빌드·설치 검증은 이번에 수행하지 않았다.

## 다음 단계·리스크

동일 시험에 맞춰 후보/기준을 선택하지 않는다. 기존 train-only 반사 앞면3실물/정상20실물에서도 nested FN2/3이 남았고 val에서는 FP감소 대신 FN증가로 미채택. 다음 자료 보강은 시험 카드가 아닌 별도 실물의 학습용 반사 앞면이다. 같은 사진 반복 학습·완료 라벨 재요청을 하지 않는다. 표본1개의100%누락을 전체 반사 일반 누락률로 주장할 수 없다.

실물별 집계는 보고 구조 추가로 학습/서비스 동작 변화 없음. 소비 운영 코드 수정 없음. 롤백은 .backups/heldout-groups-0479/의 observation_heldout.py·test_observation_heldout.py·pyproject.toml·README.md를 후속 변경 확인 후 원래 경로로 복원. 시험 artifacts는 증거 보존, 사용자 라벨·사진은 롤백하지 않는다.

에튜: 실물별 macro 평균은 앞뒤 두 사진을 제공한 카드가 한 면만 있는 카드보다 두 배 영향력을 갖지 않게 한다. A카드 두 면 모두 오탐, B카드 한 면 정상이면 면 오류2/3, 카드 평균(1+0)/2다. 기존 함수를 재사용해 계산하며 모델을 바꾸지 않는다.

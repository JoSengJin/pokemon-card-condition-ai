# 반사 학습 보강·분류 가설 검증 — 0.4.80

기반4/6완료·품질검증 진행. 사용자 img_2.png의 카드 영역 저장을 확인하고 실제 학습 실험을 실행했다. 원본 라벨을 다시 요청하거나 변경하지 않았다. 운영 Gemini 절감0·기존 모델 교체 없음.

## 결과를 분리해서 해석

추가 사진 전후 **동일 기존23학습면**(반사3/정상20)의 실물 제외 평가: 고정0.5 centroid FP2/FN2→FP5/FN3. 누락66.67→100%(+33.33%p), 오탐10→25%(+15%p). nested는 FP1유지/FN2→3. 신규 사진을 포함한24면의 오류와 기존23면 결과를 직접 비교하지 않았다.

추가 사진 전후 **동일 기존val11면**(반사2/정상9): centroid TP1/TN8/FP1/FN1→TP2/TN8/FP1/FN0. 누락50→0%(-50%p), 오탐11.11%유지, 정확도81.82→90.91%(+9.09%p). card/group/truth와 파일해시 동일 검산. 오랫동안 재사용한 검증이며 양성2실물뿐이다. 학습 실물 제외와 방향이 달라 일반화 개선/운영 채택을 주장하지 않는다. 기존 독립 시험 사진으로 새 후보를 평가하지 않았다.

## 단계별 단일 가설

같은24학습면(반사4/정상20)의 실물 제외 평가:

| 방식 | FP | FN | 판단 |
|---|---:|---:|---|
| 기존 MobileNet 단일 centroid |5|4|기준선|
| 특징별 크기 대신 사진별 unit L2 |6|4|미채택|
| 기존 공식 캐시 DINOv2 CLS |2|4|반사 전부 누락·미채택|
| 기존 로지스틱 함수·반사전용 학습 |4|4|반사 전부 누락·미채택|
| 다중 대표 최근접 거리 |3|2|학습 연구에서는 개선·검증 실패로 미채택|

DINOv2와 로지스틱의 FP감소만 보고 성공으로 판단하지 않았다. 최근접 대표 방식의 동일val11면은 centroid FP1/FN0 대비 FP3/FN1, 오탐+22.22%p·누락+50%p로 악화했다. 연구 함수와 최초 실험24면 점수 재생 차이0.0.

새 사진 특징 norm14.375는 정상 사진 범위12.603~15.745 안이다. 새 사진의 이전 반사 평균 cosine0.811·정상 평균0.886. 해당 특징에서 정상 대표와 가깝다는 기술적 진단이지 카드 정상/라벨 오류 판정이 아니다. 사진1장의 norm 이상이 원인이라는 가설은 지지되지 않았고, L2 역시 실패했다.

## 코드 변경

- card_condition/observation_prototypes.py: 연구용 최소 최근접 클래스 거리 계산. fit은 train만·두 클래스 필수·query실물 제외·query정답 미참조·유한 특징/거리 검사. 기본 학습/추론에 연결하지 않음.
- tests/test_observation_prototypes.py: 수식·query정답 독립·중복 대표 영향 없음·실물 누수/비학습 입력/비유한 거리 차단.
- card_condition/visibility_model.py: 선택적 supported_sides 메타데이터 검증. 명시된 앞면 전용 체크포인트의 뒷면/면생략 입력 거부. 필드 없는 구형 모델 그대로 동작.
- tests/test_finite_logits.py: __new__로 만든 수동 fixture의 supported_sides=None 초기화. 실제 모델 검증을 약화시키지 않음.
- tests/test_visibility_model.py: 구형 점수 보존·앞면 동일 점수·뒷면/면생략·잘못된 지원면 거부 회귀.
- pyproject.toml0.4.80, README.md, 준비/본 문서, 소비 CONDITION_ANALYSIS_TODO.md상단.
- artifacts/chieut-glare-train-20261011/: 동결 train-source, 가설별 plan/run/report, audit-and-val-comparison, candidate-freeze, old-test-reuse-guard, 테스트 로그. 실제 사용자 라벨 파일은 읽기만 했음.

## 고정 연구 후보

front-centroid-candidate.pt SHA256: 72bfb760b1e01bb951966d0bc44535fa35c4af631c64f316a1e749fe3d4b307b. 기존 MobileNet + train24앞면 class/group균등 centroid·고정0.5. 지원 front·양성사유 glare에 한정한 연구 후보, selected_for_production=false. val11면 재추론 차이0.0·실제 뒷면 입력 거부.

기존 모델의 개발 이력과 이번 학습/검증 자료, 이미 확인했던 독립 시험 이력을 제외 목록에 합쳤다. 과거 시험 사진은 fitting에 쓰지 않았다. 새 후보의 독립 시험으로 재사용하면 안 되므로 이력만 보존했다. 실제 evaluate_heldout로 과거 시험 재사용 거부·출력 디렉터리 미생성 확인. 새 미사용 반사 앞면1/관찰 가능한 앞면1이 다음 사람 자료 의존이다. 완료 카드 재라벨링·과거 test→train 이동 없음.

## 검증·리스크·롤백

새 함수3테스트·중첩2·로지스틱1·지원면 포함 visibility7테스트 통과. 초기 tests-final.log는 지원면 계약 추가 뒤 수동 mock에 supported_sides가 없어6오류가 발생했다. 테스트 fixture만 초기화해 수정했고 tests-fixture-fixed.log에서 전체156테스트 통과(43.960초). 모델/원본사진/live라벨/기존 독립라벨/최초 시험보고 hash 불변. 신규 사진 학습은 실제 실행됐지만 운영 분석 모델은 바꾸지 않았다. wheel 빌드/설치·운영 브라우저 저장 재검증은 이번 범위 밖.

작은 양성 표본·반복 검증·여러 연구 가설 검토로 선택 편향 위험이 있다. val+9.09%p를 전체 서비스 정확도 상승으로 말하지 않는다. supported_sides 필드가 있는 새 체크포인트만 명시적인 side를 요구하므로 호출자가 생략하면 안전하게 실패하고 Gemini로 보내야 한다.

롤백: .backups/prototype-0480/의 visibility_model.py·test_visibility_model.py·pyproject.toml·README.md를 후속 변경 확인 후 복원하고 신규 observation_prototypes.py·test_observation_prototypes.py를 제거한다. 신규 연구 후보를 소비 설정에 넣지 않았으므로 운영 모델 복구는 필요 없다. 실험 artifacts는 증거로 보존. 사용자 라벨/사진 롤백 금지.

에튜: 단일 centroid는 반사 사진들의 특징을 한 점으로 평균내지만, prototype은 여러 대표를 남겨 가장 가까운 점과 비교한다. 학습에서 좋아도 검증에서는 나빠질 수 있으므로 같은 자료 재생 검사와 분리 검증을 함께 했다. 지원면 메타데이터는 모델이 배운 범위를 코드 계약으로 만들어 뒷면 오용을 막는다.

# 0.4.57–0.4.59 관찰 제한 오류 개선 가설 검증

## 결과 / 진척
개발 기반4/6단계(67%, 정확도 아님) 유지. 분류기 교체와 촬영 맥락 추가를 서로 다른 가설로 실제 실행했다. 두 후보 모두 오탐 감소 대신 누락 증가가 발생하여 채택하지 않았다. 기존 모델·사람 라벨·원본 유지, 실제 Gemini 절감0건. 완료 라벨 재요청이나 같은 설정 재학습 반복 없음.

## 사전 고정 실험
공통: 동결 source의 train46면/25실물, 동일25개 실물 전체 제외fold, 제외fold0. MobileNet576 고정 특징·앞뒤 구분·클래스/실물 균등 가중치·임계값0.5 유지. val/test 미사용. 연구 채택 조건은 AUROC/AP 모두 엄격 개선, FP/FN 모두 비증가·최소 하나 감소. BCE는 미교정 진단값이며 채택 근거 단독 사용 금지.

1. Ridge: 같은 특징에서만 고정λ1 분류기 교체. -1/+1 목표의 가중 평균 MSE+λ||w||², bias 비정규화, CPU float64 solve. 특징 표준화·λ검색·온도/임계값 교정 안 함.
2. Context: centroid를 유지하고 카드 crop576에 원본 전체 사진576을 연결. 양쪽 모두 같은224px 패딩 전처리. 원본 맥락이 잘림/가림 등의 근거를 보충하는지 검증하며 배경 shortcut 위험을 사전 명시.

각 plan.json은 해당 실제 CLI 실행 전에 저장했다. 후보 체크포인트는 저장하지 않았다.

| 후보 | FP/FN | AUROC | AP | balanced BCE | 판정 |
|---|---|---|---|---|---|
| 기존 면별 centroid | 6/4 | .783482 | .586989 | .689602 | 유지 |
| 고정λ1 Ridge | 5/7 | .792411 | .583061 | .612701 | 미채택 |
| crop+원본 맥락 centroid | 4/6 | .803571 | .599256 | .688995 | 미채택 |

Ridge에서 v/front 오탐1건 해소 대신 o/back 잘림, ㅈ 그늘/front, ㅈ 반사/front 누락3건 추가. Context는 k/back·z/front 오탐2건 해소 대신 m/back·ㅈ 반사/front 누락2건 추가. 점수 이동만을 분리 능력/확률 교정 개선으로 오해하지 않는다. 같은 개발 자료 연구 결과이며 통계적 우위·독립 일반화 주장은 불가.

## 0.4.58 원인 분해 진단
`reason_support`는 각 시험 사진의 실물을 제외한 뒤 같은 면·같은 제한 사유의 다른 실물이 학습에 남는지 집계한다. 다른 사진만 있는 동일 실물은 지원으로 세지 않는다. 앞뒤도 섞지 않는다. 원래 전체 지표에서 지원 없는 사진을 제외하지 않는다. 복수 사유 사진은 사유 집계에 중복되므로 단순 합산 금지.

실제 결과: cropped/obstruction/perspective/shadow는 각 면에서 동일 사유의 다른 학습 실물 지원이0이다. glare는 다른 실물 지원이 있지만 기존 면별 모델이 뒷면6개 중2개를 놓친다. 따라서 자료 공백과 입력/표현 한계가 함께 남아 있으며 모든 오류를 자료 부족으로 설명하지 않는다. 이는 사후 진단이며 사유별 모델을 학습한 결과가 아니다. 새 멀티태스크 헤드를 더하는 것만으로 없는 제한 종류의 독립 근거를 만들 수 없다.

## 변경 파일 / 핵심 diff
루트 `.`:
- `card_condition/observation_ridge.py`: 고정 penalty의 면별 Ridge 적합.
- `card_condition/observation_support.py`: 실물/면별 사유 지원과 지원 유무별 누락 진단.
- `card_condition/observation_crossfit.py`: 선택 Ridge/context 동일fold 비교, 공유 finite sigmoid, reason_support 보고. 기본 후보 예측 그대로 유지.
- `card_condition/cli.py`: 선택 --compare-ridge / --compare-context. 기본·운영 추론 경로 변경 없음.
- `tests/test_observation_ridge.py`: 분석적으로 알려진 해·bias·비유한/클래스 누락 거절.
- `tests/test_observation_support.py`: 동일 실물·반대면 제외, 복수 사유·오탐·입력 불변.
- `tests/test_observation_crossfit.py`: 옵션 전후 기준선 동일, held실물 정답 변경 시 해당 예측 불변, val/test 무효 경로 미사용, 후보4개 검사.
- `README.md`, `pyproject.toml`: 연구 계약·최종0.4.59.
- 본 보고서·아래 artifacts, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.

## 실제 검증
- Ridge 구현 단계 전체125테스트 통과(40.597초).
- 최종 전체126테스트 통과(40.082초).
- 두 실험 실제 MPS CLI 성공, 기준선 두 후보 예측은 이전0.4.47·0.4.57·0.4.59 사이 완전 일치.
- source·live 라벨·선택 구역/관찰 모델2개·실제 입력 사진 해시 보존. checks.json 확인.
- 외부 다운로드 없이0.4.59 wheel 빌드, Python/HTML46파일 소스와 byte 일치.
- `/private/tmp/condition-0459-installed` 설치본을 저장소 밖에서 실행. Ridge의 분석해·지원 진단·실제 CLI 도움말 두 옵션 확인. 첫 smoke가 존재하지 않는 parser함수를 import하여 실패했으며 제품 변경 없이 실제 main/--help 실행으로 검증을 바로잡았다. 설치본 대규모 MPS 재학습을 별도로 반복하지 않았다.
- 근거: `artifacts/observation-ridge-20261011/{plan.json,run/report.json,cli.json,transitions.json,reason-support.json}` 및 `artifacts/observation-context-20261011/{plan.json,run/report.json,cli.json,transitions.json,checks.json}`. 최종 테스트 로그 `/private/tmp/condition-0459-tests.log`.

## 리스크 / 롤백
Ridge CPU float64 solve는 특징 차원의 제곱 메모리·세제곱 연산 비용이 있고 context는 추가 백본 추론/배경 shortcut 위험이 있다. 둘 다 선택 연구 경로로만 제공한다. 진단은 작은 이미 사용한 자료의 기술이며 인과 증명이 아니다. 반복 개발의 선택 편향 때문에 새 실물 독립평가가 필요하다. 생산 라우팅·Gemini 생략은 제공하지 않는다.

이번 묶음 전체를0.4.56으로 복귀: `.backups/observation-ridge-0457/`에 보존한5기존 파일을 원위치 복원하고 신규 observation_ridge.py/observation_support.py와 두 대응 테스트 파일을 제거한다.0.4.56 wheel 사용 가능. 소비 TODO의.57–.59를 롤백으로 표시한다. 모델·라벨·원본은 바꾸지 않았으므로 데이터 롤백 불필요. 실험 artifacts/보고서는 근거로 보존 가능.

## 다음 판단 / 외부 의존성
새 프레임워크 도입 근거 없음. 기존 PyTorch에서 필요한 비교를 수행했다. 새로운 분류기를 무작정 추가하거나 임계값을 기존 오류에 맞춰 조정하지 않는다. 다음 품질 승인에는 현재 개발에 쓰지 않은 실물 자료가 필요하며, 사용자 답변 ‘새 자료 없음’을 유지한다. 기존 train/val을 test로 바꾸거나 완료 라벨/없는 원본을 다시 요청하지 않는다. 자료 확보 전 운영 채택·실제 호출 절감 주장은 보류한다.

에튜: Ablation Study는 한 번에 한 요소만 바꿔 개선 원인을 분리하는 방법이다. 평균 손실 하나보다 오탐과 누락의 동반 변화를 확인해야 실패 비용을 다른 곳으로 옮긴 개선을 걸러낼 수 있다.

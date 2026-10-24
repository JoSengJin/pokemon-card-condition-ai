# 0.4.61–0.4.62 분류 목적과 반사 정답 분리 비교

## 성과와 진척
개발 기반4/6(67%, 정확도 아님) 유지. TODO 완료 후 중단하지 않고 BCE 분류기 비교 → 계산 수렴 보완 → 반사 전용 정답 비교 → 다음 검증의 자료 지원 검산까지 진행했다. 두 후보 모두 누락 증가로 미채택. 기존 모델·사람 라벨·사진 보존, 실제 Gemini 절감0건.

## 0.4.61 분류 목적 가설
동일 MobileNet576 crop224 특징, 면별·클래스/실물 균등 가중치·train25실물 전체 제외fold·임계값0.5 유지. 고정λ1로 평균BCE+λ||w||²를 최소화하고 bias는 비정규화. CPU float64 LBFGS max100·zero start·strong_wolfe, 수렴 기울기 최대1e-6. val/test 및 hyperparameter 검색 없음.

첫 실제 실행은 기울기 수렴 미달로 보고서/체크포인트 미저장, CLI exit1. 이후 성능 결과나 정답을 바꾸지 않고 학습 특징의 가중 평균을 빼 계산 조건을 개선했다. `w(x−mu)+b`는 `wx+(b−w*mu)`와 같으므로 bias를 원좌표로 되돌리면 같은 목적 함수다. train에서만 mu를 계산하며 분산 표준화/특징 선택/검증 자료 학습이 아니다. 초기 실패는 failed-attempt.json에 보존.

수정 후 실제25fold/50개 면별 적합 모두 수렴. 기울기 최대2.883e-7, 반복11~14회. 기존 면별centroid FP/FN6/4 → BCE5/7. AUROC.783482로 사실상 동일, AP.586989→.579493, balanced BCE.689602→.624253. 손실 개선만으로 성공으로 보지 않고 미채택.

## 0.4.62 반사 대상 분리 가설
같은 사진/특징/centroid/실물 제외fold를 사용하되 학습 대상을 명시적glare 양성과 명시적으로 관찰 가능한 음성으로 제한한다. 다른 제한만 있는6면은 미확인으로 남기며 정상 라벨로 바꾸지 않는다. 기존 종합 모델도 후보와 정확히 같은40면/23실물에서 평가한다. 대상 축소 전후 숫자를 직접 비교하지 않는다.

| 같은40면 기준 | FP/FN | AUROC | AP | balanced BCE |
|---|---|---|---|---|
| 기존 종합 제한 모델 | 6/2 | .835938 | .519206 | .688596 |
| 반사 전용 centroid | 1/4 | .890625 | .616173 | .686450 |

40면 모두 평가·거부fold0. 순위 지표와 오탐은 개선됐지만 반사 누락 증가로 사전 기준 미달. 전반적인 관찰 제한 일반화/운영 채택 근거가 아니다. 후보 체크포인트를 저장하지 않는다.

학습 지원 부족으로 fold를 거부하여 시험에 양 클래스가 남지 않는 경우, 오류를 감추거나0점으로 만들지 않고 status=insufficient_scored_support, 요약/변동 진단=null로 기록한다. 거부fold/미평가 수를 보존하고 연구 채택은false다.

## 다음 단계에서 실제 필요한 사람 개입
판정 경계를 시험 카드에 맞추지 않고 내부 실물 제외 예측으로 정하려면 outer/inner 두 실물을 뺀 학습에도 각 면 양 클래스가 남아야 한다. 기존 예측에서 자료 지원만 검산했다. threshold 선택/추가 모델 학습은 하지 않았다.

- 앞면 정상20실물, 앞면 반사2실물(u·ㅈ-빛가려짐).
- 뒷면 정상12실물, 뒷면 반사6실물.
- 23실물의506개 outer/inner 조합 중2개는 앞면 반사 학습 정답이0이 된다.
- 따라서 다음 nested threshold 비교는 앞면 반사 신규 실물 최소1장의 사람 확인이 필요하다. 완료 라벨이나 독립 평가 자료를 재요청하는 것이 아니며, 기존 두 반사 실물을 서로 다른 학습 사례로 복제하지 않는다.
- 근거 artifacts/observation-glare-focus-20261011/nested-readiness.json. 외부 자료를 새로 수집하지 않았으며 사진 정답을 추정하지 않았다.

## 변경 파일 / 핵심 diff
루트 `.`:
- AGENTS.md: 사용자 지정 중단 조건(실제 사람 개입/토큰·컨텍스트 실행 한계) 반영. TODO 완료를 최종 보고 경계로 삼지 않음.
- card_condition/observation_logistic.py: 고정BCE 목적·train 중심화·수렴 검사·원좌표head 반환.
- card_condition/observation_glare.py: 반사/명시적 관찰 가능 대상만 적합·동일 heldface 비교·불충분한 fold를 미측정으로 기록.
- card_condition/observation_crossfit.py, cli.py: 선택 --compare-logistic/--compare-glare-only, 같은 특징/fold 공유. 기본 후보 예측 유지.
- tests/test_observation_logistic.py: 기울기 정지점·bias 이동 동등성·입력 gradient 없음·미수렴/잘못된 입력 거절.
- tests/test_observation_glare.py: 다른 제한을 정상으로 바꾸지 않음·실물 제외·동일 비교 대상·양성 부족fold 기록/미측정.
- tests/test_observation_crossfit.py: 후보5개 및 선택 반사 실험 누수 방지·기본 예측 일치.
- README.md, pyproject.toml: 연구 계약·최종0.4.62.
- 본 문서 및 두 실험 artifacts, 소비 프로젝트 CONDITION_ANALYSIS_TODO.md.

## 검증
최종 전체131테스트 통과(41.204초), 앞선BCE 단계130개(42.609초). 두 실제 MPS 실험의 원래 global/side_aware 예측은 이전 기준선과 완전 일치. plan의 source/live/선택 모델2개 SHA 및 모든 실제 입력 사진 SHA 불변.

외부 다운로드 없는 wheel0.4.62 빌드·Python/HTML49파일 소스 byte 일치. 설치본을 저장소 밖에서 실제 CLI 옵션·BCE 적합·반사 부분 평가로 확인한다. 실제 새 실물 정확도 평가와 소비 운영 연결은 이번 범위가 아니다.

근거: artifacts/observation-logistic-20261011/{plan.json,failed-attempt.json,cli-centered.json,run/report.json,checks.json}, artifacts/observation-glare-focus-20261011/{plan.json,cli.json,run/report.json,checks.json,nested-readiness.json}, /private/tmp/condition-0462-tests.log.

## 리스크 / 롤백
BCE solve는 추가 CPU 비용, 반사 전용 비교는 한 종류에 한정된 작은 표본이라는 제약이 있다. 중심화는수식 동등성이지만 float32로head복사 후 작은 오차가 있을 수 있다. 확률 교정·다른 제한 종류·독립 일반화를 보장하지 않는다. 같은 자료를 반복 개발에 사용했으므로 테스트 자료로 재지정할 수 없다.

.61–.62 전체 복귀는 .backups/observation-logistic-0461의 기존 AGENTS/README/pyproject/observation_crossfit/cli/test_observation_crossfit를 원위치 복원하고 신규 observation_logistic.py·observation_glare.py 및 대응 테스트2개를 제거한다. 사용자 중단 규칙은 코드 복귀와 분리해 유지한다.0.4.60 wheel 사용 가능. 모델/라벨 복원 불필요. 소비 TODO 해당 항목만 롤백으로 표시하고 artifacts는 실패/성공 기록으로 보존한다.

## 에튜: BCE와 수식 재매개변수화
BCE는 제한 사진에 낮은 점수를 줄수록 벌점이 커진다. 정답1에서 점수0.9의 벌점은−log(.9)≈.105, 점수0.01이면≈4.605다. 이번에는 이미지 특징을 그대로 두고 분류 목적만 바꾸는 데 사용했다. 손실 감소가 누락 감소를 보장하지 않는 실제 결과도 확인했다.

재매개변수화는 문제를 바꾸지 않고 계산하기 편한 좌표로 푸는 방법이다. 특징에서 학습 평균mu를 뺀 뒤 bias를 b−w*mu로 되돌리면 같은 예측식이다. 이번 LBFGS의 수렴 실패를 데이터/정답 변경 없이 해결한 기술이다.

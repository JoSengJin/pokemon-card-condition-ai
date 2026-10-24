# 0.4.60 실물 단위 paired bootstrap 진단

## 성과 / 진척
개발 기반4/6(67%, 정확도 아님) 유지. 기존 교차검증 예측을 이용해 두 후보의 개선이 실물 구성에 얼마나 민감한지 진단하는 기능을 추가했다. 새 학습·라벨 수정·임계값/채택 조건 변경 없음. 두 후보의 기존 미채택 결론 유지, 실제 Gemini 절감0건.

## 구현
사진 한 장씩 뽑으면 같은 실물의 앞뒤·여러 사진을 독립 표본으로 오인한다. 따라서 실물 그룹 전체를 복원 추출한다. 동일 추출에서 기준선과 후보의 오류를 함께 계산하는 paired 비교로 표본 구성 차이를 제거한다.

고정 seed42/2000회, 임계값0.5. FPR=FP/정상 정답 수, FNR=FN/제한 정답 수, 차이=후보−면별centroid. 음수는 해당 오류 감소다. 경험적2.5/97.5 percentile은 nearest-rank 방식. 단일 클래스 추출은 비율을 정의할 수 없으므로 제외 횟수를 기록한다. 행 순서를 바꿔도 실물 정렬과 고정seed로 결과 재현.

정답·실물·이미지 hash·box·사유·사진 identity가 같은 예측끼리만 비교한다. train 실물 제외 예측만 허용하며 비유한/범위 밖 점수를 거절한다. 원래 교차검증 전체 지표·채택 조건은 바꾸지 않는다. Bootstrap 결과는 선택에 사용하지 않는다.

## 실제 결과
train46면/25실물의 고정 예측. 후보별2000회 모두 양 클래스 존재하여 제외0회.

| 후보−면별centroid | FPR 차이 | 경험적 변동 범위 | FNR 차이 | 경험적 변동 범위 |
|---|---|---|---|---|
| Ridge | −3.125%p | −11.429~0%p | +21.429%p | 0~+43.750%p |
| crop+원본 맥락 | −6.250%p | −15.152~0%p | +14.286%p | 0~+36.364%p |

기존 오탐 감소/누락 증가 방향과 일치하지만 변동 범위가0에 닿는다. 독립 일반화나 안정적인 개선을 확정하지 않는다. 재표집으로 새 실물 근거를 만들 수 없다. Crossfit 모델끼리 학습 자료를 공유하므로 이 값은 고정 예측의 조건부 민감도이며 학습 알고리즘의 정식 신뢰구간으로 주장하지 않는다.

## 변경 파일 / 핵심 diff
루트 `.`:
- `card_condition/observation_bootstrap.py`: 표준 라이브러리만으로 paired 실물 재표집·입력 일치 검사·오류율 차이 진단.
- `card_condition/observation_crossfit.py`: `paired_group_sensitivity`에 면별centroid 대비 후보별 진단 추가. 예측·채택 기준은 유지.
- `tests/test_observation_bootstrap.py`: 동일 후보 차이0, 입력 순서 재현, 앞뒤 동반 추출, 단일 클래스 횟수·잘못된 pairing/점수 거절3테스트.
- `AGENTS.md`: 에튜를 해당 턴에 실제 사용한 기술의 원리→사용 이유→작은 예시로 가르치는 원칙.
- `README.md`, `pyproject.toml`: 계약과0.4.60.
- 본 문서와 artifacts/observation-bootstrap-20261011/report.json·checks.json.
- 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 실행 근거와 에튜 원칙.

## 검증
- 전체129테스트 통과(41.265초). 이후 실물 정렬로 행 순서 재현성을 보완하고 해당3테스트 통과.
- 실제 Ridge/context 저장 예측2개에 계산, 원본 보고서 SHA 불변. 정렬 보완 후 결과 완전 일치.
- source/live 라벨/선택 모델2개 해시가 이전 고정값과 일치.
- no-index/no-deps wheel 빌드·Python/HTML47파일 소스 byte 일치.
- 저장소 밖 `/private/tmp/condition-0460-installed` 설치본으로 실제 저장 예측 두 비교 재계산, 결과 완전 일치. 큰 모델 재학습/새 정확도 평가를 실행한 검증은 아니다.
- 전체 테스트 로그 /private/tmp/condition-0460-tests.log.

## 리스크 / 롤백
기본 crossfit 보고에2000회 재표집 연산이 추가된다. 실제 서비스 추론 경로에는 적용하지 않는다. 작은 개발 자료에서 얻은 percentile은 가정과 변동성을 전달하는 진단일 뿐 성능 승인 근거가 아니다. 독립 test는 새 자료에 의존하며 없다는 사용자 답변 유지. 완료 라벨을 다시 요청하지 않는다.

`.backups/group-bootstrap-0460/`의 기존 AGENTS.md/README.md/pyproject.toml/card_condition/observation_crossfit.py를 원위치 복원하고 신규 observation_bootstrap.py·test_observation_bootstrap.py를 제거하면0.4.59로 복귀한다. 에튜 지침은 사용자 선호이므로 코드 롤백과 별도로 유지하는 것이 적합하다. 모델·라벨 복원 불필요. 소비 TODO도 해당 실행 항목을 롤백으로 표시한다.

## 에튜
Cluster Bootstrap: 사진이50장이어도25실물의 앞뒤라면 서로 연관된 표본이다. 카드 한 장을 뽑을 때 앞뒤 사진도 같이 뽑아야 표본 수를 부풀리지 않는다. Paired 비교는 같은 카드 묶음을 두 모델에 함께 적용해 ‘모델 차이’와 ‘시험 카드 구성 차이’를 섞지 않는 방법이다. 이번 코드의 `groups`에 실물별 오류를 모으고 한 번의 추출로 기준·후보 차이를 함께 계산하는 이유다.

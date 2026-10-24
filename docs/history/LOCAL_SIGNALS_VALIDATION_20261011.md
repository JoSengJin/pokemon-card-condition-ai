# 국소 색·질감 입력 검증 — 0.4.44

## 결과
사전 계획 LOCAL_SIGNALS_PLAN_20261011.md에 따라 단일 입력 가설을 실행했다. 후보 채택 보류, 기존 모델·운영 Gemini fallback 유지, 실제 호출 절감0건. 사진의 관찰 제한을 검출하는 실험이며 카드 상태가 좋거나 나쁨을 판정한 결과가 아니다.

| 지표 | 기존576차원 | 후보612차원 |
|---|---:|---:|
| 관찰 제한 오탐 / 누락 | 7 / 4 | 7 / 4 |
| AUROC | 0.487395 | 0.487395 |
| AP | 0.426233 | 0.426233 |
| 클래스·실물 균등 BCE | 0.698560 | 0.698196 |
| 같은 FP예산7에서 TP(사후 진단) | 3 | 3 |

BCE는 여전히 무정보 기준 ln2=0.693147보다 나쁘고 순위·오류 감소가 없어 사전 채택 조건 미달이다. 재사용 검증24면이므로 독립 일반화 근거로 쓰지 않는다.

## 변경과 검증
- card_condition/observation_signals.py 신규: 기존 audit의 픽셀·공간 신호 함수를 그대로 이동하고 3×3 고정 descriptor 추가. 각 셀의 평균 밝기, 인접 밝기 차, HSV 채도, min(R,G,B)를 /255. 라벨 추정·학습 scaler 없음.
- card_condition/observation_audit.py: 공용 신호 함수 import로 전환, 기존 진단 동작 유지.
- card_condition/visibility_model.py: local_signals 선택 특징 연결·체크포인트 복원/정책 검증. 입력576→612. 기본 False이며 기존 체크포인트도 호환.
- card_condition/cli.py: --local-signals, pyproject.toml: 0.4.44, README.md: 사용법·결과.
- tests/test_observation_signals.py 신규3검증: 구역 위치/36값, 체크포인트 재추론·검증 정답 교체 시 학습값 동일, 혼합 가설/잘못된 정책 거절.
- AGENTS.md 신규: 휴먼인루프·완료 라벨 보존·실용적인 에튜 포인트 영속 지침. 소비 프로젝트 CONDITION_ANALYSIS_TODO.md 상단 실행 이력 갱신.
- 전체94테스트 통과(26.234초). wheel 0.4.44의 Python/HTML 38파일과 소스 바이트 일치.
- 실제 MPS 후보·기존 모델 각24면 재추론 최대 차이0.0. 입력 사진/source·live 라벨·합의문·기존 모델/report 해시 불변.

실행:
```sh
TORCH_HOME=artifacts/torch-cache .venv/bin/card-condition visibility-experiment artifacts/observation-geometry-20261011-source.jsonl artifacts/observation-local-signals-20261011 --centroid --local-signals --device mps
.venv/bin/python -m unittest discover -s tests
```
기존 output은 덮어쓰지 않으므로 재실행할 때 별도 출력 디렉토리가 필요하다.

증거: artifacts/observation-local-signals-20261011/report.json, comparison.json, recovery.json, verify.py. train46면/25실물·val24면/14실물, 동일 box·라벨·그룹·이미지·frozen MobileNet·train 가중 centroid. test는 사용하지 않았다.

## BCE 하락 원인 추가 검산
기존 centroid 거리식 /D에서 D가576→612가 되어 기존 특징의 logit 기여는576/612=0.941176배가 된다. 학습 데이터만으로 국소36값의 centroid를 다시 계산해 분리 검산했다.
- 국소 특징 logit 기여 절댓값 평균0.00026149, 최대0.00058409.
- 분모 변경만의 logit 변화 절댓값 평균0.00656636: 국소 기여보다 약25배 큼.
- 기존 logit×576/612 + 국소 logit로 후보를 재구성한 최대 오차0.000000280.
확률 오차 하락을 분리 성능 향상으로 오해하지 않는다. 이 결과는 고정 /255 연결 방식의 실패이지 색·질감 특징 전체의 반증이 아니다. 검증 결과에 맞춰 배율·임계값을 조정하지 않았다.

## 다음 판단과 휴먼인루프
새 의존성/프레임워크는 추가하지 않았다. 다음 독립 가설은 특징 블록의 단위 차이를 train-only 스케일 처리로 다루는 것이다. 학습 통계는 train만 사용하고 val에는 고정 적용하며 같은 특징·백본·정답을 보존해야 한다. 먼저 사전 계획과 누수 방지 검증을 마련하며, 이번 결과를 이유로 완료 라벨을 재요청하지 않는다. 원본/깨끗한 비교 사진 부재 답변도 유지한다. 새로운 종류별 일반화에는 독립 자료가 필요하다.

## 리스크·롤백
국소 색·질감에도 카드 그림·배경·회색 padding이 섞이며 촬영 제한의 원인 정답이 아니다. 추가 차원의 거리 단위 영향은 위와 같이 확인됐다. 운영 채택하지 않았고 기본 경로는 그대로다.

실험 롤백: --local-signals를 생략하고 artifacts/observation-geometry-20261011/model.pt를 사용한다. 코드 롤백: .backups/local-signals-0444의 visibility_model.py·observation_audit.py·cli.py·pyproject.toml·README.md를 원래 경로에 복원하고 신규 observation_signals.py·tests/test_observation_signals.py만 제거한다. 실험 기록·AGENTS.md·사람 라벨은 보존한다. 무관한 변경/라벨 파일을 덮어쓰지 않는다.

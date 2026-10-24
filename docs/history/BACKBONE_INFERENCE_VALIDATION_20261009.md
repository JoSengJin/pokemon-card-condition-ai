# 독립 추론·backbone 비교·패키지 검증 — 2026-10-09

## 완료 범위
1. SideAnalyzer와 side-predict: 기존 MobileNet 및 새 ResNet18 면별 체크포인트 로딩, 앞/뒷면별 출력, 누락 면 표시, crop/tile의 사람 지정 영역 필수 검증. 미학습 항목은 null이며 항상 Gemini fallback을 요구한다.
2. side-experiment --backbone resnet18: torchvision 공식 ImageNet 고정 특징 + head 학습. 기본 MobileNet 유지. ResNet18의 마지막 블록 미세조정은 범위에 넣지 않았다.
3. compare-validation: 동일 snapshot·면·정답·출력 유효성 확인, 혼동행렬 재검산, 임계값별 오류 비교. 최종평가를 개발 비교에 사용하지 않는다.
4. benchmark-validation: val만 사용해 이미지 읽기/전처리/추론 포함 실제 속도 측정. 준비 실행 1회와 면별 반복 3회, 모델 로딩 시간 별도 기록.
5. 독립 패키지 0.3.0 wheel 빌드 및 임시 경로 설치. 소스 디렉터리 밖에서 새 모듈·review.html·구형 체크포인트 로딩 확인.

## 실제 모델 실험
visibility-complete-20261009.jsonl의 train40/val18, 전체 사진224px, seed42, epochs5 고정. test 미사용. MobileNet과 ResNet18 비교는 backbone만 변경하고, ResNet18 내부 비교는 train 클래스 가중치만 변경했다. pretrained 가중치는 torchvision 공식 서버에서 받았다. 카드 사진은 외부 API로 보내지 않았다.

| 모델 | val BCE | 센터링 검출/오탐 | 모서리 검출/오탐 | 엣지 검출/오탐 | 표면 검출/오탐 | 평가 불가 오탐 |
|---|---|---|---|---|---|---|
| MobileNet 기존 | 0.6091 | 2/7 · 0/8 | 0/3 · 0/11 | 0/6 · 0/8 | 0/2 · 0/10 | 5/5 |
| ResNet18 | 0.6336 | 3/7 · 3/8 | 0/3 · 0/11 | 0/6 · 0/8 | 0/2 · 0/10 | 5/5 |
| ResNet18 + balance | 0.6717 | 3/7 · 4/8 | 0/3 · 1/11 | 4/6 · 2/8 | 2/2 · 6/10 | 5/5 |

0.5 임계값의 비교다. 미확인 정답은 제외했다. 검출 수 개선에 오탐 증가가 동반돼 기본 모델을 교체하지 않았다. balance 모델의 매물 단위 routing-audit에서 모든 시도 문턱값의 Gemini 생략 후보는 0건이다. 실제 절감도 0건.

## 실제 추론 속도
현재 Mac의 MPS, val18면 × 3회 = 모델별54회. 첫 준비 실행 제외. 두 모델을 순서대로 측정했다.

| 모델 | 중앙값 | p95 | 모델 로딩 |
|---|---|---|---|
| MobileNet | 26.8ms | 54.9ms | 182ms |
| ResNet18 | 23.5ms | 42.6ms | 336ms |

이미지 I/O와 전처리도 포함한다. 캐시·기기 부하·온도 영향을 받는 단일 실행 기록으로, ResNet이 항상 더 빠르다는 뜻은 아니다. 메모리 최대 사용량은 측정하지 않았다. 속도보다 관찰 가능성 오판·결함 누락이 현재 병목이다.

## 검증과 산출물
- 전체31개 테스트 통과: 두 backbone 학습/저장/복원, 구형 메타데이터, null 출력·누락 면, 영역 필수, 잘못된 체크포인트, 비교 입력/지표 변조 차단, 속도 산출물 덮어쓰기 차단 및 기존 데이터 누수/HTTP 회귀 포함.
- 실제 CLI side-predict 실행: 앞면 점수 반환, back=null / missing_sides=[back] / requires_gemini=true 확인.
- wheel: artifacts/dist-20261009/pokemon_card_condition-0.3.0-py3-none-any.whl. --no-index --no-build-isolation --no-deps로 빌드, 임시 target 설치 후 소스 밖에서 import/리소스/모델 로딩 확인. 새로운 머신에서 의존성까지 설치하는 검증은 하지 않았다.
- 학습: artifacts/resnet18-full-20261009, artifacts/resnet18-balanced-20261009.
- 비교: artifacts/backbone-comparison-balanced-20261009.json.
- 속도: artifacts/mobile-inference-speed-20261009.json, artifacts/resnet-inference-speed-20261009.json.
- 라우팅: artifacts/resnet-balanced-routing-20261009.json.

## 변경 파일
- 새 모듈: card_condition/side_model.py, card_condition/comparison.py, card_condition/benchmark.py.
- 수정: card_condition/side_experiment.py, card_condition/side_evaluation.py, card_condition/cli.py.
- 검증: tests/test_side_model.py.
- 패키지/문서: pyproject.toml, README.md, 이 파일, PokeCollector의 CONDITION_ANALYSIS_TODO.md 진행 기록.

## 리스크와 롤백
val은 반복 개발 자료다. 새 모델/임계값의 일반화 성능·정식 등급·진위·동일 실물 보증은 없다. crop/tile 모델은 사람 지정 box를 요구하므로 자동 매물 분석에 바로 넣을 수 없다. 현재 PokeCollector worker/DB에는 연결하지 않았다.

기존 MobileNet 모델/라벨은 보존했다. 기본 side-experiment는 여전히 MobileNet이다. ResNet을 사용하지 않으려면 --backbone을 생략하고 새 실험 산출물만 보관하면 된다. 기능 전체 롤백은 CLI의 side-predict/compare-validation/benchmark-validation 및 backbone 인자를 제거하고, side-experiment와 side-evaluation을 기존 ConditionModel 특징 로딩으로 복원한 뒤 새 모듈·테스트를 제거한다. 버전은0.2.0으로 되돌린다. wheel을 소비 앱에 설치하지 않아 운영 의존성 롤백은 필요 없다.

## 다음 TODO와 기술 선택
반사 위치·결함 영역의 사람 라벨 및 신규 독립 최종평가 자료 확보 후 영역 모델을 검증한다. 기존 torchvision 안에서 두 backbone을 비교하는 경로를 마련했으므로 timm을 추가할 이유를 아직 확정하지 않는다. FastAPI/Docker/Mastra는 이 독립 Python API에 필요한 운영 요구가 확인될 때 검토한다.

# 0.4.50 고정 타일 배치 추론

## 목적과 구현

CONDITION_ANALYSIS_TODO의 추론 지연 검증과 독립 패키지 경계를 이어간다. 같은 검증 자료로 정확도 학습을 반복하지 않고, 기존 모델의 순차 5회 호출(구역 전체+2×2 타일)을 단일 배치 호출로 바꾸는 독립 가설을 검증했다. 좌표·해상도·풀링·모델·사람 정답·분할·임계값은 변경하지 않았다. 새로운 기술 의존성 없음: 기존 PyTorch 배치 추론만 사용한다.

배치는 `listing-infer --batch-views`로 명시적으로 켠다. inference mode 및 모든 하위 모듈 eval을 요구해 BatchNorm/학습 동작 차이를 차단한다. 기본 순차 경로, 학습 코드, 운영 Gemini fallback은 그대로다. MPS 실행 전후 동기화로 타이밍 구간을 명시했다. 타이밍은 모델 로딩/manifest 디코딩을 제외하고 구역 추론·입력 해시 재검사·readiness 집계를 포함한다.

## 실측

artifacts/batched-views-20261011/plan.json에 비교 전 기준을 고정: 최대 점수 차이1e-5 이하, 모든 구역 판정 일치, 기존 .3/.7 기준 유지. 동일15매물/160구역을 순차·배치 각3회, 순서S/B/B/S/S/B로 MPS에서 실행했다.

- 순차:24.1263 /21.1445 /19.5930초, 중앙값21.1445초.
- 배치:14.2693 /13.9992 /13.7518초, 중앙값13.9992초.
- 중앙값 기준 지연33.79% 감소(약1.51배 처리 속도).
- 전160구역 최대 점수 차이1.49e-7. 구역 정상/결함/보류·사유·매물 보류/추가 사진 정책은 전부 일치.
- live 라벨·source·고정 모델 SHA 유지. 모델 재학습·새 라벨·외부 호출 없음. 실제Gemini절감0건.

comparison.json에 전회 시간·입력 SHA·허용 오차·한계를 저장했고 run.py로 검산 가능하다. 산출물 덮어쓰기 방지를 위해 재실행 시 새 출력 디렉토리를 사용해야 한다. 한 개발 장비의 OS 캐시 영향이 있는 비교이며 첫 순차 실행/첫 배치 실행 구간에는 CPU 회귀검사도 겹쳤다. 따라서 운영 처리량·동시 부하·순수 하드웨어 벤치마크로 해석하지 않는다. 정확도 개선 근거도 아니다.

## 변경 파일·핵심 diff

- card_condition/edge_views.py: 기존 전처리·좌표 helper 재사용, opt-in batched_patch_features 추가. 고정 view들의 feature map을 동일 방식으로 집계.
- card_condition/listing_inference.py: batch_views 선택 인자·MPS 동기화·실행 경로 기록. 기존 구역 마스킹/관찰 제한 연결/파일 변동 차단 유지.
- card_condition/cli.py: --batch-views 옵션.
- tests/test_edge_views.py: 모든 입력 정책(context/views/tiles/tiles-max)·모서리/중앙의 특징 동일성, 단일 호출 수·배치 크기, grad/no_grad/train 모드 차단.
- tests/test_listing_inference.py: 배치 전후 구역 결과/readiness 일치 검사.
- pyproject.toml:0.4.50. README.md:사용법·수치 차이·메모리 한계.
- artifacts/batched-views-20261011:사전 계획·실행 스크립트·6회 보고서·비교·연결 CLI 검산.
- 본 보고서 및 소비 프로젝트 CONDITION_ANALYSIS_TODO.md:실행 근거. 소비 프로젝트 실행 코드·DB·라벨 UI는 변경하지 않았다.

## 실행 검증

최종 전체110테스트 통과. 배치 helper3테스트 재검사 통과. 0.4.50 wheel Python/HTML42파일 소스 바이트 일치. 실제 CLI에서 --batch-views와 --observation-checkpoint를 함께 실행해 관찰 제한 evidence 완전 일치 및 모든 구역 판정/매물 정책 일치를 검산했다(combined-checks.json). 누락 사진/카드 영역의 unknown과 Gemini fallback을 유지했다.

## 리스크와 롤백

배치5개는 단일 이미지보다 활성화 메모리를 더 사용할 수 있다. 메모리 최고치 및 운영 동시 부하는 측정하지 않았다. .3/.7 근처 입력은 미세한 부동소수점 차이로 판정이 바뀔 가능성이 있어 이번 자료의 일치만으로 일반화하지 않는다. 기본 경로로 승격하지 않았으며 독립 정확도 평가 및 운영 채택은 여전히 보류다.

즉시 롤백은 --batch-views를 생략하는 것이다. 소스 롤백은 .backups/batched-views-0450의 동일 경로7개 파일을 복원하되 이후 변경이 있으면 이번 diff만 제거한다. 모델/라벨 복원은 필요 없다.

에튜: Batch inference는 학습을 더 하는 기법이 아니라 동일 계산을 묶어 장치 호출 비용을 줄이는 방법이다. 속도 개선과 정확도 개선을 구분해서 검증한다.

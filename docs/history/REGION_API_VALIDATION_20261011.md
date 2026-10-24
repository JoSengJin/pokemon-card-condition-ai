# 0.4.52 최신 구역 모델의 독립 패키지 API 연결

## 목표와 구현

CONDITION_ANALYSIS_TODO 상단에 수용기준을 먼저 추가했다. 최신 point-grid/고정 타일 체크포인트는 listing-infer와 probe에서 실행되지만 RegionAnalyzer/region-predict는 이를 명시적으로 거부하고 있었다. 기존 테스트도 거부를 기대했다. 독립 의존 패키지로 사용할 연구용 구역 추론 계약을 최신 모델과 연결했다. 이는 정확도 개선 실험이나 운영 채택이 아니다.

신규 point-grid/views/tiles/tiles-max 모델은 기존 load_probe_model을 사용해 아키텍처·입력 정책·지원 항목·개발 이력 메타데이터를 검증한다. 전처리와 feature 집계는 기존 patch_features/batched_patch_features를 공유한다. 구형 region_v1 경로와 backbone_name 없는 구형 MobileNet 체크포인트는 유지했다. 모든 경로에서 image_size224/448을 확인하고 실제 전처리에 전달한다. 기존 RegionAnalyzer는 image_size가 있어도224로 처리했는데, 이제448 모델의 실제 입력 크기도 지킨다.

RegionAnalyzer.analyze(..., unknown_labels=(), batch_views=False) 및 region-predict --batch-views로 실행한다. architecture/image_size/input_policy/batched_views를 출력에 추가했다. 이미지를 자동으로 앞뒤 연결하거나 카드 영역을 자동 검출하지 않는다. unknown_labels는 기존처럼 관찰 제한 null, 적용 범위 밖/미지원 결함은 null이다. requires_gemini=true, production_ready=false, actual_calls_saved=0 유지.

## 검증

- 실제 MPS: 동일15매물의 기존160구역을 단일 API 순차·배치 각각 실행(총320회), 모델/source/photo/live SHA 보존 확인.
- 순차 점수 차이0, 배치 포함 최대 차이1.49e-7. 학습/임계값/사람 라벨 변경 없음.
- 실제 region-predict CLI: 최신 tile 체크포인트+batch 옵션 실행 및 --unknown edge_defect가 null/observation_limited로 남는지 확인.
- 기존 point 학습 보고서·context/views448/tiles 학습 보고서·tiles-max 학습 보고서와 API 점수 일치 검사. legacy448 실제 전달, 잘못된 크기/정책/개발 이력 거부, 기존 legacy/ResNet 테스트 유지.
- wheel을 /private/tmp/condition-0452-installed에 --no-index/--no-deps로 설치하고 /private/tmp에서 로딩 경로를 확인했다. 최신 tile 모델 CPU/batch 추론 성공, 기존 MPS 기준 점수 차이7.75e-7. 소스 checkout import에 의존하지 않는 독립 패키지 실행 확인.
- 전체115테스트 통과(41.509초), wheel0.4.52 Python/HTML43파일 소스 byte 일치.

실측 근거는 artifacts/region-api-20261011/{verify.py,checks.json,predictions.json,cli.json,cli-limited.json}. 원본 체크포인트 SHA abf327d5e80d90a30a8c904b99afa6988ff669c7ccf922e8471df7b44b6c0175, live SHA c61e11649ed52cd86af1b40ee4eafab45bb604f71c4ccfdf64d69b118ebdbf94 유지.

## 변경 파일과 핵심 diff

- card_condition/region_model.py: 현대 point 아키텍처의 공유 검증 로더 연결, 이미지 크기 전달, 공유 고정 crop/feature 경로, 선택 batch, 결과 메타데이터. 구형 region 검증 경로 유지.
- card_condition/cli.py: region-predict --batch-views 및 analyze 인자 전달.
- tests/test_point_dataset.py: point 모델 거부 기대를 학습 보고서 점수 일치 기대로 전환.
- tests/test_edge_views.py: context/views448/tiles API와 순차/배치·관찰 제한 대조.
- tests/test_tile_max.py: tiles-max API 점수/정책 대조.
- tests/test_region_api.py 신규: legacy448 전달·잘못된 크기·point 메타데이터 거부.
- pyproject.toml:0.4.52. README.md:독립 API/CLI 사용 계약.
- 본 보고서·신규 region-api 산출물·소비 프로젝트 CONDITION_ANALYSIS_TODO.md:개발 근거. PokeCollector 실행 코드·DB·라벨 UI 변경 없음.

## 리스크·롤백

API가 모델을 실행할 수 있게 된 것과 그 모델이 안전하게 매물 전체를 판단하는 것은 별개다. 관찰 제한/영역/구역은 호출자가 제공해야 하고, 모델 오답·미지원 항목·독립 평가 부재는 그대로다. 추가된 JSON 필드를 엄격하게 검사하는 외부 소비자는 계약 확인이 필요하다. batch는 수치 차이·메모리 증가 가능성이 있어 기본false다. 448을 잘못224로 처리하던 구형 호출의 점수는 이제 달라질 수 있으며, 올바른 학습 입력과의 일치가 목적이다.

소스 복귀는 .backups/region-api-0452의 기존7파일을 같은 경로에 복원하고 신규 tests/test_region_api.py를 제거한다. 후속 변경이 있으면 이번 diff만 제거한다. 데이터/모델 롤백은 필요 없다. batch 옵션만 끄려면 --batch-views를 생략한다.

에튜: 모델 파일만 같아도 전처리·해상도·풀링이 다르면 다른 결과가 나온다. 학습·검증·독립 API가 같은 입력 계약을 공유해야 비교가 성립한다.

# 속도 측정 입력 무결성 — 0.4.73

개발 기반4/6=67% 유지. 단일 면/타일 속도 측정 중 사진이 바뀌어도 결과가 저장되는 문제를 수정했다. 같은 모델/사진으로 측정했다는 계약을 지키는 보완이며 속도 개선이나 정확도 개선 주장이 아니다.

## 변경 파일·핵심 diff

- card_condition/benchmark.py: 시작 전 manifest/모델/측정 사진 SHA를 보존하고 저장 전에 기존 unchanged_inputs로 검산. 결과 manifest_sha256도 측정 시작 입력값으로 기록한다.
- card_condition/point_benchmark.py: 기존 manifest/모델 검사에 측정 사진 SHA를 추가하고 공통 검산을 재사용한다.
- tests/test_benchmark_inputs.py: 두 경로에서 photo/manifest/checkpoint 변경6사례 및 정상2사례. 추론/데이터 로더를 mock한 입력 계약 테스트이며 정확도나 성능 실측이 아니다.
- tests/test_finite_logits.py: 기존 mock 데이터에 실제 존재하는 사진 경로 추가. 비정상 logit 차단 검증 유지.
- pyproject.toml·README.md·소비 CONDITION_ANALYSIS_TODO.md: 버전·실행 근거. 운영 소비 코드 변경 없음.

## 검증

새 회귀 테스트를 수정 전에 실행했을 때 point사진1건·side사진/manifest/모델3건이 성공 보고서로 저장돼4사례 실패. 수정 후8사례 모두 기대대로 처리됐다. 기존 실제 합성 모델 추론/벤치마크 회귀도 포함해 전체149테스트42.719초 통과. 저장소 밖 설치본11테스트7.221초 통과. wheel52소스 파일 일치, 원본/live/기존 두 모델 SHA 보존. artifacts/benchmark-inputs-20261011/checks.json·테스트 로그 참고.

## 리스크·롤백

명령 전체 실행에는 입력 해시I/O가 추가된다. 개별 추론 타이머 밖이므로 per-patch/side latency는 이 추가 I/O를 포함하지 않는다. 이번 보완을 속도 향상으로 비교하지 않는다. 입력 변경 시 결과 저장을 거부하며 원본 파일이나 라벨을 자동 복원하지 않는다.

.backups/benchmark-inputs-0473/의 benchmark.py·point_benchmark.py는card_condition/, test_finite_logits.py는tests/, pyproject.toml·README.md는루트로 복원하고 tests/test_benchmark_inputs.py를 제거하면0.4.72로 되돌아간다. 진단 문서/artifacts는 별도 보관 가능. 모델/라벨은 변경되지 않았다.

에튜: 벤치마크는 실행시간뿐 아니라 비교 조건도 고정해야 한다. 사진이 측정 중 바뀌면 빠른/느린 결과가 모델 차이인지 입력 차이인지 알 수 없어 저장을 거부한다.

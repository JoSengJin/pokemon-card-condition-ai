# 0.4.56 확률 변환 전 수치 오류 차단

## 성과와 개발 진척
개발 기반4/6단계(67%) 유지. 추론의 무한대/NaN이 확실한 정상·손상 판단으로 둔갑하는 실패를 차단했다. 모델 정확도 개선이나 개발 미사용 실물의 일반화 검증을 뜻하지 않는다. 실제 Gemini 절감0건, 운영 변경 없음.

## 문제 재현
수정 전 고정 region/observation 체크포인트를 로딩한 인스턴스의 head weight를0으로, bias를 각각+inf/-inf로 주입했다. 실제 CPU 추론에서 region edge_defect=1.0, observation_limit_score=0.0으로 수용됐다. 저장된 원본 모델 파일은 변경하지 않았다. sigmoid 변환 후 확률의 finite 검사만으로는 이 오류를 잡을 수 없었다.

## 변경 파일 / 핵심 diff
루트 `.`:
- `card_condition/model.py`: 공유 checked_sigmoid 추가, logits 단계에서 torch.isfinite 검사 후 기존 sigmoid를 그대로 실행. 기존 전체 카드 Analyzer에도 적용.
- `card_condition/region_model.py`, `side_model.py`, `visibility_model.py`: 구역/단일 면/관찰 제한 API의 변환 전 공통 검사.
- `card_condition/listing_inference.py`: 매물 검증 추론의 변환 전 검사.
- `card_condition/point_probe.py`, `point_benchmark.py`: 진단·벤치마크에서도 수치 실패를 성공 보고서로 저장하지 않음.
- `tests/test_finite_logits.py`: 유한값 정확히 동일, NaN/±inf 거부, 구역 순차/배치·면별 관찰 경로·실패 벤치마크 보고서 미저장4테스트.
- `README.md`, `pyproject.toml`: 계약과0.4.56 버전.
- 이 문서 및 `artifacts/finite-logits-20261011/`: 실제 재추론·CLI·배포 검증 기록.
- 소비 프로젝트 `CONDITION_ANALYSIS_TODO.md`: 상단 계획과 완료 증거.

학습 loss·학습 head·선택 epoch·임계값·사람 라벨·운영 분기는 변경하지 않았다. 유한한 극단값을 임의로 clamp/교정하지 않는다.

## 검증 결과
- 전체124테스트 통과(41.377초). 벤치마크 경로 보완 전123테스트도 통과했고, 추가 경로/테스트 포함 후 전체를 다시 확인했다.
- 실제 MPS15매물/160구역/27면을 기존 동결 결과와 대조했다. 구역 점수/readiness 완전 일치, 관찰 점수 차이0.0. 미검토 면 unknown 보존, 정상 CLI 성공.
- no-index/no-deps wheel0.4.56 빌드, Python/HTML44파일 소스 byte 일치.
- 설치본 `/private/tmp/condition-0456-installed`를 저장소 밖에서 실행. 정상 CPU 두 모델 CLI 결과는0.4.54 설치본 결과와 완전히 일치.
- 임시 region 체크포인트 head에+inf, observation 체크포인트 head에-inf를 저장해 설치본 CLI로 각각 실행했다. 두 경우 모두 stdout 부분 결과 없이 JSON requires_gemini=true/exit1 반환.
- 실제 모델2개·source snapshot·live 라벨의 해시 보존 확인. 기존 사진으로 연결 검산한 결과이며 새 독립 정확도 평가가 아니다.
- 근거: artifacts/finite-logits-20261011/checks.json, verify.py, results.json, cli.json, installed-cli.json.

## 리스크 / 롤백
검사에 GPU 동기화 비용이 추가될 수 있다. 이번 작업에서 지연 개선/무비용이라고 주장하지 않는다. 비정상 logits는 전체 호출을 거부하므로 일부 지원하지 않는 head 출력에만 수치 오류가 있어도 결과를 부분 수용하지 않는다. 모델 파라미터의 모든 손상 유형이나 모든 연구 학습 경로를 검사하는 변경은 아니다. 정상적인 확률의 교정/오탐·누락 문제는 별개로 남는다.

`.backups/finite-logits-0456`의9파일을 원래 위치로 복원하고 신규 tests/test_finite_logits.py를 제거하면 롤백된다.0.4.55 wheel 사용 가능. 소비 TODO의0.4.56 항목은 롤백으로 표시한다. artifacts/보고서는 근거로 보존할 수 있다. 모델/라벨은 변경하지 않았다.

## 다음 실행 의존성
현재 상단 실행 계획의 이번 코드 보완은 완료했다. 독립 최종평가는 개발 미사용 새 실물 자료에 의존하며 현재 사용자 답변은 없음이다. 기존 train/val의 test 전환, 완료 라벨 재요청, 같은 입력 반복 학습으로 그 의존성을 우회하지 않는다. 소비 운영 적용/실제 절감 검증도 아직 완료되지 않았다.

에튜: logit과 probability의 차이를 익히면 변환 함수가 원래 오류를 숨기는 상황을 발견할 수 있다. 검증은 결과 표시값만 보지 말고 의미가 바뀌기 전 경계에서도 수행해야 한다.

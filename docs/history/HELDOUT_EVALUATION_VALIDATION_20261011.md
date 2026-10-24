# 독립 평가 경계 및 이번 개발 검증 — 0.4.48

## 현재 판단
선택 연구 후보는 앞/뒤별 train centroid이며 HELDOUT_EVALUATION_PLAN_20261011.md에 체크포인트 SHA를 고정했다. 고정 val에서 관찰 제한 FP/FN7/4→2/3, train 실물 제외25fold에서는11/5→6/4였다. 확률 교정 개선은 확인되지 않았다. 독립 최종 성능/운영 승인/실제 Gemini 절감은 미확인/미승인/0건이다.

사용자 답변: 새 독립 실물 사진 없음. 기존 manifest에는 train36행/val16행/미지정17행이며 test0행. 미지정 중 t는 사람 상태 라벨이 이미 있고 나머지16행은 excluded=true이므로 재검토/재분할하지 않았다. 원본·live 라벨·기존 모델·합의문을 그대로 보존했다. 다음 독립 성능 판단에는 새 실물과 사람 정답이 필요하다. 기존 자료를 시험용으로 돌려 숫자를 만들지 않는다.

## 경계 구현
- CLI `visibility-heldout`는 expected-model-sha256을 필수 입력으로 받아 후보가 바뀌면 거절한다.
- test만 로드, 학습/모델선택/임계값 선택 없음. checkpoint 개발 id/group/디코딩 RGB 픽셀 hash와 겹치면 거절한다. 독립 평가 안의 다른 실물명 사이에 픽셀이 동일해도 분모를 부풀리지 않고 거절한다.
- 같은 픽셀의 다른 실물명 문제를 train 교차검증에도 차단했다. 실제25실물에는 중복0이라 기존 OOF 숫자는 유효하며 재학습을 반복하지 않았다.
- 명시적인 제한/비제한 두 클래스가 없으면 결과를 만들지 않고, 미확인 면은 skipped에 사유를 기록한다. 새 사진이어도 같은 실물인지의 의미적 판단까지 hash가 보증하지는 않으므로 사람 확인이 필요하다.
- 면을 모르면 side-aware checkpoint 추론을 거절하고 fallback을 요청한다. 완료 라벨을 모델 오답으로 변경하지 않는다.

## 변경 파일 목록과 핵심 diff
독립 프로젝트 기준:
- card_condition/visibility_model.py: train-only 표준화 선택, 앞/뒤 train 대표값 분리 선택, checkpoint/면별 진단/추론 연결. 기본 기존 동작 유지.
- card_condition/observation_scaling.py 신규: 실물 균등 train mean/std, 상수 차원 floor1e-6, 저장 통계 검증.
- card_condition/observation_crossfit.py 신규: train 전체 실물 제외 비교, 불가 fold/분모 기록, 다른 실물명 중복 픽셀 차단.
- card_condition/observation_heldout.py 신규: SHA·개발 실물/픽셀 누수 차단, test 예측 전용 평가.
- card_condition/cli.py: --standardize, --side-aware, visibility-predict --side, visibility-crossfit, visibility-heldout.
- tests/test_observation_scaling.py, test_side_centroids.py, test_observation_crossfit.py, test_observation_heldout.py 신규: 통계/대표값 누수 방지, 실물 전체 제외, 모델/사진 재사용 경계 및 추론 일치.
- pyproject.toml0.4.48, README.md, 단계별 PLAN/VALIDATION 문서, artifacts 실행 근거.
소비 프로젝트는 CONDITION_ANALYSIS_TODO.md 실행 이력만 갱신. 운영 Python/DB/웹 UI 변경 없음. 외부 Gemini/Claude 호출/사진 전송 없음, 새 의존성 없음.

## 검증과 증거
- 최종 고정 코드 전체107테스트 통과(29.294초). 관찰 관련18테스트도 별도 통과.
- wheel0.4.48의 Python/HTML41파일과 소스 바이트 일치.
- 실제 앞/뒤 CLI 예측 각1면과 연구 checkpoint report 차이0.0. 연구 후보/기존 모델24면씩 재추론 차이0.0은 side-centroids recovery.json 참고.
- 실제 heldout CLI에 test0 source를 넣으면 기존 로더의 `Manifest is empty` 오류 및 requires_gemini=true로 종료하고 output을 생성하지 않음. 최초 검증 스크립트가 다른 오류 문구를 기대해 실패했으며, 실제 계약/출력 부재를 재확인했다. 이를 독립 성능 실행으로 세지 않는다.
- 독립 평가 경로는 합성 fixture로만 정상 동작/차단 검증했다. 사용자 실제 독립 test 평가는 미실행이다.
- artifacts/heldout-readiness-20261011.json: 고정 모델 SHA, live 보존, CLI 일치, 실제 독립 평가 미실행 기록.
- artifacts/observation-train-scaling-20261011: 표준화 후보 보류 근거.
- artifacts/observation-side-centroids-20261011: 고정 val 연구 후보 채택 근거.
- artifacts/observation-group-crossfit-20261011: 25fold 진단·입력/선택모델 보존 근거.

## 리스크·롤백
반사/그늘/흐림의 종류별 독립 실물이 부족하고, 같은 val 반복 사용에 따른 선택 편향이 남는다. 작은 점수 차이는 교정 확률/카드 상태 점수가 아니다. 해시 검사는 정확히 같은 픽셀을 잡지만 리사이즈/재촬영한 같은 실물까지 판별하지 못한다. 따라서 연구 개선을 실제 호출 절감으로 확대하지 않는다.

사용 롤백: 새 옵션/명령을 생략하고 기존 artifacts/observation-geometry-20261011/model.pt 사용. 이번 코드 전체 롤백은 .backups/train-scaling-0445의 visibility_model.py·cli.py를 card_condition에, pyproject.toml·README.md를 프로젝트 루트에 복원하고 위 신규 모듈3개·신규 테스트4개만 제거한다. 문서·실험 artifacts·AGENTS.md·사람 라벨은 보존한다. 후속 수정이 추가됐다면 무조건 덮어쓰지 않고 diff를 먼저 확인한다.

에튜: 원본 카드와 같은 실물의 앞/뒤는 한 시험 묶음이다. 한쪽만 학습에 남겨두면 답을 미리 본 시험이 된다. 이번 교차검증은 실물을 통째로 제외해 그 영향을 줄였으며, 실제 새 실물에서의 성능 보증은 별개다.

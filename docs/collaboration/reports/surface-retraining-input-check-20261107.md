# 표면 입력 중복 재학습 점검 — 2026-11-07

**개발 진척78/100(v1.13) 유지. 확정 라벨과 직전 표면 실험의 실제 재판정 반영 학습 입력은 동일. 사용자 조건에 따라 중복 재학습을 실행하지 않았다.**

검증 기준SHA 50ce9635ba39b7417c49610bf2031a3292c10d40. 직전 표면 실행을 started_at 기준으로 조회하고 최신 record가 `artifacts/experiments/20261106T210640-0eb1bdc0/record.json` completed임을 확인했다. 실패/진행 중 실행을 건너뛰어 과거 결과로 대체하지 않았다. 이번 확인은 모델 학습/성능 실험이 아닌 입력 비교다.

## 실제로 비교한 입력

|항목|직전 후보 학습|현재 확정 입력|차이|
|---|---|---|---|
|사용 구역|1776|1776|추가0·제거0|
|결함/정상|370/1406|370/1406|구역별 라벨 변경0|
|판단 불가 제외|15|15|제외 ID/순서 동일|
|사진 그룹|204|204|5fold 배정 동일|
|원본 사진/영역/메타데이터|실행 당시 rows|확정 대장과 대조|차이0|

직전 원라벨 대조 팔(결함179개)과 현재 확정 라벨을 단순 비교하면191개 차이가 보이지만, 그191개는 **직전 실험의 재판정 반영 학습 팔에 이미 포함**돼 있었다. 새로 바뀐 학습 라벨이 아니다. 이번 주 비교는 실제 후보 팔의1776개다. 대조 팔의 원라벨1776개도 별도로 동일함을 확인했다.

실행 record에 등록된 plan/reference/code snapshot/result 해시, plan의 모든 input_sha256 및 source_hashes를 검증했다. 실행 당시 `code/1-after.py`의 순수 label_rows 함수로 rows/judgments에서 실제 두 학습 팔을 재구성해 observations.rows/original_rows 및 frozen reference.rows와 완전 일치 확인했다. 모델 worker 본문은 실행하지 않았다. 확정 대장과 원본 rows의 ID·group·area·box·사진해시를 대조하고 같은 순서에서 최종 선택 target을 반영한 후 전체 행 완전 동일을 확인했다.

5개 fold의 train/evaluation10개 집합은 각각 ID/라벨/영역/메타데이터 및 순서가 동일하며 comparison.json에 팔별 fingerprint를 기록했다. 그룹/사진해시 train/evaluation 중복0. 204개 실제 사진의 원본 또는 EXIF 반영 RGB 디코딩 해시가 기록된 사진해시와 일치했다. raw/decoded 중 어떤 기준으로 맞았는지는 photo-hashes.json에 구분했다. D1·표면 보류2는 그룹/사진해시 비중복만 대조했고 추론/평가하지 않았다.

전체 후보 입력 canonical SHA-256: `077650973caaf77d832ef33f38bffff2f6d157266ad701f01519a2f903e1f656`. 직전/현재 동일이다. 원본 파일의 JSON 표시/규약 설명이 달라졌는지가 아니라 모델에 공급한 행/라벨/제외/분할이 달라졌는지로 판단했다.

## 실행 결정과 결과 해석

`skip_identical_training_input`. 새 사전 계획·공통 ./experiment·record는 만들거나 실행하지 않았다. 기존 실험은 completed이지만 기준 미충족이었고 그 판정을 유지했다. 규약 확인 근거가 완성된 것이 학습 라벨값 변경이나 모델 성능 개선을 의미하지 않는다. 새 정확도/FN·FP·AUC·속도·독립 일반화 평가는 하지 않았다. 원본 라벨·사진·모델·운영 코드·PokeCollector·Gemini fallback 불변. 새 Gemini/Codex 호출0.

이번 사용자 요청은 이전 보류를 조건부로 갱신했다. 라벨이 다를 때만 사전 기준을 고정해1회 실행할 수 있으며, 이번 동일 입력에서는 실행하지 않는 조건을 따랐다. 재학습 허가를 무조건 열린 상태로 저장하지 않는다. 결정은 decision.json에 기록했다.

## 변경 파일·검증·리스크·롤백

- 추적 docs/collaboration/reports/surface-retraining-input-check-20261107.md, 동명.html(합성 검사·상대경로 안내만), docs/collaboration/tasks/surface-retraining-input-check-20261107.md 신규3파일.
- ignored artifacts/surface-retraining-input-check-20261107/: 비교 script·comparison.json·실사진 해시·실행 결정·성과HTML/보고·검사·입력해시. 최종 규약 폴더 latest-retraining-check.json 신규 포인터로 연결한다. 기존 감사/실험/사람답을 덮어쓰지 않는다.
- 합성5경로 검사: 동일 행, 라벨 변화 검출, box 변화 검출, ID추가/제거, 순서 변화. 실자료1776행 완전동일/15제외동일/5fold train평가10집합동일 검산, 실제 사진 해시 확인, 실행 근거·입력 파일 SHA 검증. 새 experiment record0.
- 구조: ignored compare.py 함수4개, 주요 자체 경로 main→compare_rows/read_json/fingerprint1전이. 읽은 순수 snapshot label_rows 이외 모델/최적화 함수는 호출하지 않았다. 신규 추적 소스 및 기존 호출경로 변경0.
- 한계: 입력 동일 확인은 기존 모델 품질을 보증하지 않는다. 완벽한 라벨 정답이나 일반화를 새로 증명한 것이 아니다. 전체 회귀/새 학습/추론/모바일 실기기/브라우저 렌더는 미실행이며 열기 접수/렌더 여부는 checks.json과 인계에 구분한다.
- 롤백: 이번 신규 문서 커밋만 revert 후 일반push, 비교 근거/사람 확인은 이력으로 보존. 기존 라벨/모델을 바꾸지 않아 복구 불필요. 최신 포인터만 제거하면 이전 감사 보기는 유지된다.

최종 검산: 전체 입력 fingerprint/5fold train·evaluation10개 fingerprint 일치,277개 읽은 입력 파일SHA 불변. HTML1791개ID 중복0. HTML 파일 열기 요청 queued, 실제 표시/렌더 미확인.

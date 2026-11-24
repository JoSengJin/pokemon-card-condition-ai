# 공통 실험 기록

계획·worker·필수 평가·상태 계약은 이 문서 전체를 읽는다. 자동 검토·개발 연결·재개·격리 실행을 다루면 [자동 검토 상세 계약](docs/agent/AUTO_REVIEW_CONTRACT.md) 전체도 필수다. 분리한 날짜별 보완은 계속 적용되며 보호 조건·호출 제한·승인 범위를 바꾸지 않는다.

새 실험은 Codex가 계획과 worker를 작성한 뒤 공통 실행기로 실행한다. 기존 review 명령과 과거 실험 파일은 유지한다. 기존 학습·평가 코드를 LangGraph로 이전하지 않는다.

```sh
./experiment --plan 경로/계획.json -- .venv/bin/python 경로/실험_worker.py
```

앞으로 Codex에게 “공통 실행기로 실험하고 record.json과 같은 평가 자료의 전후 결과를 보고해줘”라고 요청하면 된다. AGENTS.md에 이 실행 경로를 필수로 명시했다. 실행기를 거치지 않는 임의 명령까지 가로채거나 감시하지는 않는다.

## 실행 전 계획 계약

아래는 형식 설명이며 실제 경로·가설·기준으로 작성해야 한다. 기준 결과는 기존 지원 result.json 또는 이전 공통 result.json이다. Python 파일을 수정하기 전에 수정 전 snapshot을 artifacts에 보존한다.

```json
{
  "hypothesis_id": "한번-정한-가설-ID",
  "hypothesis": "어떤 관찰 근거로 어떤 원인을 의심하는가",
  "change": "이번에 바꾸는 변수 하나와 대조 조건",
  "success_criterion": "같은 평가 자료에서 FP 2 이하, FN 0, 새 오답·사람점 누락 없음",
  "failure_criterion": "위 조건 중 하나라도 미충족",
  "reference_result": "artifacts/기준실험/result.json",
  "acceptance": {
    "max_fp": 2,
    "max_fn": 0,
    "no_new_errors": true,
    "require_actual_point_guard": true
  },
  "code_changes": [
    {"path": "card_condition/수정모듈.py", "baseline": "artifacts/준비/snapshot-before.py"},
    {"path": "artifacts/준비/실험_worker.py", "baseline": null}
  ]
}
```

가설·변경·성공·실패 문장과 수치 기준은 필수다. 현재 판정은 FP/FN 상한, 구간별 새 오답 여부, 승인된 실제 사람점의 새 누락 여부다. 텍스트 문장을 AI로 해석하지 않으므로 문장과 수치 기준을 일치시켜야 한다. threshold는 기존 평가 계약과 같은 0.5만 지원하며 독립 검증으로 표시할 수 없다.

기준 결과에 실제 사람점이 있으면 guard=true가 필수다. 실제점 정답이 없는 실험만 false로 명시할 수 있다. 없는 사람점 정답은 추정하지 않는다. 새로운 판정 지표가 필요하면 계획·실행기·테스트를 함께 확장한다.

### 분모가 0인 상한은 미측정이다 (2026-11-25)

새 계획에는 평가 자료마다 결함·정상 행 수를 적는다: `"evaluation_counts": {"primary": {"defect": 12, "normal": 30}, "<필수 평가 id>": {"defect": 5, "normal": 0}}`. 적으면 실행기가 동결한 정답 행과 정확히 대조하고(평가 하나라도 빠지거나 다르면 child 시작 전 거절), 한쪽이 0인 평가는 그 사실을 계획에 밝힌 것이 된다. 이 칸이 없는 계획은 그대로 실행된다(과거 계획과, 아직 이 칸을 쓰지 않는 자동 검토 경로의 계획).

`result.json`의 주 평가와 각 `required_cohorts` 항목에 `acceptance_caps`가 추가된다. 누락 상한(`max_fn`)은 결함 행이, 오탐 상한(`max_fp`)은 정상 행이 1 이상일 때만 `passed`/`failed`이고 0이면 `unmeasured`다. `unmeasured`는 통과가 아니며 보고에 "미측정"으로 적는다. `acceptance_passed`는 나머지 측정된 조건으로 정해지는 값 그대로이므로 과거 판정은 바뀌지 않는다. 따라서 `acceptance_passed=true`만 보고 누락·오탐 상한을 모두 통과했다고 쓰지 말고 `acceptance_caps`를 함께 읽는다.

## Worker 입력·출력

실행기는 아래 환경변수를 worker에 전달한다. 키나 환경변수 전체를 기록하지 않는다.

- `CARD_CONDITION_EXPERIMENT_DIR`: 이번 실행의 출력 폴더.
- `CARD_CONDITION_EXPERIMENT_REFERENCE`: 고정된 reference.json 경로. rows, before_scores, cohort_sha256, point_ids, point_scores를 포함한다.

worker는 실제 학습·평가를 수행하고 출력 폴더에 observations.json을 쓴다.

```json
{
  "rows": ["설명용: reference.json과 같은 실제 평가 행 dict 전체"],
  "scores": ["설명용: 각 평가 행의 실제 예측 확률"],
  "point_ids": ["reference.json의 실제 사람점 ID와 동일한 순서"],
  "point_scores": ["해당 사람점의 실제 예측 확률"]
}
```

위 배열 문자열은 형식 설명이며 그대로 실행할 데이터가 아니다. 실제 rows는 id/target/group/image_sha256/box/fold/profile/split 정보를 보존해야 하고, scores는 0~1의 유한한 숫자다. actual point가 없는 기준 자료에서는 point_ids/point_scores를 생략할 수 있다. worker가 성공 종료해도 출력이 없거나 평가 사진·영역·정답·분할·순서·사람점 ID가 바뀌면 공통 실행은 failed다. 같은 정답을 모델 오류에 맞춰 수정하면 안 된다.

## 추가 필수 평가 (`required_cohorts`)

기존 개발 평가가 통과해도 별도로 확인한 사진에서 누락·오탐이 남으면 최종 통과로 해석하면 안 된다. 계획에 다음 목록을 사전 선언하면 실행기가 각 평가의 행·정답·영역·그룹·기준 점수·실제점 ID를 `reference.json`에 동결한다.

```json
"required_cohorts": [{
  "id": "known-new-photo-regression",
  "reference_result": "artifacts/required-cohort-gate-20261022/required-reference.json",
  "acceptance": {"max_fp": 0, "max_fn": 0, "no_new_errors": true, "require_actual_point_guard": false}
}]
```

각 reference는 기존과 같은 `rows`/`before_scores`/`scores` 형식이다. 미확인 정답을 정상으로 채우지 않는다. 알려진 정답 행만 별도 reference에 넣고 제외한 미확인 ID·사유를 원본 기록에 남긴다. 실제점 정답이 있는 필수 평가에서는 point guard를 끌 수 없다. 주 평가의 기존 실제점 보호도 유지된다.

worker는 `observations.json`에 `required_cohorts` 목록을 추가한다. 각 항목은 동결한 `id`, `rows`, `point_ids`와 **같은 후보로 계산한** `scores`, `point_scores`다. 목록 누락·순서/정답/영역 변경·미등록 평가·비유한 점수는 `failed`다. 기준 예측을 새 후보 예측으로 복사하면 안 된다. 모델을 바꾸지 않는 명시적 진단은 실제 checkpoint와 캐시 특징으로 같은 점수를 재생해 검증할 수 있다.

`primary_acceptance_passed`는 주 평가만의 결과, `required_cohorts[].acceptance_passed`는 각각의 결과, 최상위 `acceptance_passed`는 **모두의 AND**다. 필수 평가가 없는 과거 계획의 판정은 그대로다. 필수 평가가 든 결과를 다음 기준으로 삼으면 같은 평가 ID/정답/실제점/수치 기준을 삭제·변경할 수 없고, 새 오답 비교에는 직전 결과의 점수를 사용한다. 자동 구현도 이 목록과 worker 출력 계약을 보존하며 누락 시 실패한다. 자동 비교 HTML에는 주 평가와 각 필수 평가를 나눠 표시한다.

이 기능은 채택 판정의 누락을 막는 장치다. 자체로 정확도를 높이지 않으며, 이미 확인한 사진을 다음 모델 선택에 쓰면 그 사진은 알려진 회귀 평가다. 독립 시험으로 다시 주장하지 않는다. 과거 result/record의 통과 값을 덮어쓰지 않고 새 진단 기록에서 바로잡는다. 실제 Gemini/Codex 호출 없이 로컬 테스트·재생으로 검증한다.

## 저장 구조와 상태

```text
artifacts/experiments/<UTC시각-고유ID>/
  plan.json           실행 전 고정 계획
  reference.json      기준 결과에서 고정한 평가 자료와 점수
  code/*-before.py    수정 전 snapshot
  code/*-after.py     실행 시작 시 snapshot
  changes.diff        명시한 파일의 unified diff 전체
  record.json         실행 ID·시간·명령·PID·상태·파일 SHA256
  observations.json   worker가 저장한 실제 관찰 — 있으면
  result.json         검산한 전후 수치·사람점 누락·사전 기준 판정
```

실행 전 계획·기준 평가·코드·diff를 저장하고 running을 기록한 뒤 child를 시작한다. 정상 종료 시 결과 검산과 파일 무결성 검증 후 completed를 기록한다. **completed는 실행·검산 완료이며 성능 개선이나 성공 기준 충족을 뜻하지 않는다.** 성공 기준 결과는 result.acceptance_passed다.

비정상 종료·출력 누락·정답/코드 변경은 failed, Ctrl+C/SIGINT/SIGTERM은 interrupted로 남긴다. 명령 시작 실패도 기록한다. 오류는 단계(stage)·반환 코드·예외 종류만 남기고 비밀값이 섞일 수 있는 원문 예외를 저장하지 않는다. SIGKILL/전원 종료에서는 finally가 실행되지 않으므로 마지막 running 기록이 남는다. 다음 review 조회에서 감독 PID가 사라진 것을 확인하면 interrupted/orphaned_process로 보정한다. 종료 시각은 발견 시각이며 end_time_inferred=true다. PID가 재사용됐거나 접근할 수 없으면 보수적으로 running으로 남을 수 있다. 감독 프로세스를 강제 종료하면 child가 남아 있을 수 있으므로 실행 상태를 별도 확인해야 한다.

기록 저장 자체가 디스크 오류로 불가능한 경우까지 완전 보장하지는 않는다. 기존 기록을 덮어쓰지 않고 각 실행마다 새 폴더를 사용한다. 명시한 코드 파일만 포착하므로 변경한 실행 스크립트와 모듈을 빠짐없이 code_changes에 등록해야 한다.

## review 연결

```sh
./review
```

공통 기록이 있으면 등록된 started_at 순으로 최신 실행을 우선한다. 최신 실행이 failed/interrupted/running이면 그 상태와 record 경로를 표시하고 Gemini를 호출하지 않는다. 예전 성공 결과로 대체하지 않는다. completed지만 사전 성공 기준을 충족하면 정체 근거가 없다고 알리고 호출하지 않는다.

사전 기준을 충족하지 못한 완료 실험이면 같은 평가 자료의 결과·실패 이력·최근 실행 실패/중단 이력, 동결된 계획과 실제 changes.diff를 packet에 넣는다. 실행 실패 이력에는 존재하지 않는 평가 수치를 만들지 않는다. diff는 전송량을 위해 최대6000자만 포함하고 잘림 여부와 원본 경로·SHA를 표시한다. 현재 수정 파일의 첫 함수 대신 **실행 당시 저장된 diff**를 사용한다. 기본1회/최대3회·완료 응답 재사용 정책은 유지한다.

공통 기록이 없으면 과거 날짜 폴더 result.json 수집을 그대로 사용한다. 과거 파일은 변환·덮어쓰기하지 않는다. 공통 기록 이후에도 과거의 같은 평가 자료를 실패 이력으로 활용할 수 있다. 대화형 미완료 검토는 기존처럼 동결된 packet을 재개한다.

## 범위와 검증

기록·판정·자료 선택은 로컬 코드가 수행하며 모델 토큰을 쓰지 않는다. `./review --auto`는 Gemini 제안을 별도 Codex 검토·구현과 공통 실험으로 연결한다. 기본 `./review`는 자동 개발을 하지 않는다. LangGraph는 검토 상태·분기·중단/재개를 관리한다. 학습/평가 자료 분리와 독립성은 worker에서도 검증해야 하며, 공통 실행기는 개발용 동일 평가 자료의 비교와 정답 불변을 검증한다.

자동 검토는 기존 계획의 worker와 `input_sha256`에 연결된 직접 import 함수를 읽어 전달한다. 사용 함수는 본문 전체와 원본 SHA를 제공하고, 관련 없는 함수·중복 diff는 제외한다. 입력 상한을 넘으면 호출 전에 중단한다. 새 프로젝트 자료에 필요한 코드·캐시 경로가 기존 계획에 없으면 추정하여 실행하지 않는다.

Codex는 실험 배율 하나를 `experiment_parameter`의 `name/baseline/value/scope`로 먼저 확정한다. 미정·비유한·기존과 같은 값은 채택하지 않는다. 이 값은 선택 기록·구현 입력·공통 계획에 동일하게 전달한다. 새 worker나 변경 후 결과를 미리 요구하는 대신 구현 단계에서 worker를 작성한다. worker는 출력 폴더의 `plan.json`에서 고정 값을 읽고, 기준 점수는 reference의 `before_scores`를 사용한다. 원래 수치 기준과 사람점 보호를 완화할 수 없으며, 미달·실패 시 코드 복원을 유지한다. 기존 호출 상한·중복 방지·불명 요청 재시도 금지도 유지한다.

이번 변경과 테스트·리스크·롤백은 artifacts/common-experiment-record-20261020/REPORT.md에 기록한다. 실제 Gemini 호출이나 새 모델 학습·성능 실험은 수행하지 않는다.

## 제한된 자동 교정

자동 Codex 요청은 기본 검토1회·필요할 때 교정1회·구현1회로 최대3회다. 가설 ID·인용·완료 진단 확인·수치 설정의 검증 실패만 동일한 동결 근거와 오류를 교정 슬롯으로 전달한다. 수정 후에도 틀리면 종료한다. 정당한 stop/wait는 그대로 유지한다. 요청 실패·사용량 미확인·소스 변경은 교정 명목으로 재요청하지 않는다.

최신 모델 실험이 추가돼도 동일 평가 자료의 완료 진단(최근 가설 최대3개)을 경로/SHA·완료 상태·측정 요약과 함께 전달한다. 초기 실행 실패와 이후 완료 진단은 모두 보존한다. `review_claims`는 완료 진단의 가설 ID와 실제 없는 근거 ID를 명시한다. 이미 제공된 근거를 없다고 하거나 Gemini 잔여0을 실험 선택 금지로 해석하면 교정 대상이다. stop/wait도 전체 실패 가설 ID와 인용을 검사한다.

추가 Gemini 비판 후 판정도 같은 교정 슬롯을 사용한다. 교정 슬롯을 쓴 뒤에는 추가 Gemini를 요청하지 않는다. 자동 모드에서 Gemini 최대3회는 여전히 상한이지만 Codex 슬롯을 소진하면 그 전에 멈춘다. 수동 검토 상한은 유지한다. 단계별 journal로 완료 호출을 재사용하며 불명 교정을 반복하지 않는다.

## 실패 반복을 막는 근거 계약

새 검토 프롬프트 `cross-review-ko-v4-grounded-alternative`는 실패 실험의 변경 조건·고정 수치 기준·구역 비교·실제 사람점 비교·기준 미달 이유를 함께 전달한다. 완료 진단은 `completed_diagnostic_*`의 측정으로, 실행 실패는 `failed_execution_*`의 실행 상태로 구분한다. 후자를 모델 측정 결과처럼 사용하지 않는다.

`fresh_evidence_ids`는 동일 평가 자료의 마지막 완료 Gemini 요청에 전달한 경로/SHA와 비교한 새 결과·완료 진단·코드 근거다. 역할 프롬프트나 요약만 바뀐 것은 새 실험 근거가 아니다. 로컬 응답 복사(`response_reuse.json`)는 새 Gemini 검토로 세지 않는다. 새 근거가 없으면 호출 전에 `no_new_evidence`로 종료한다. 새로운 평가 자료는 별도 검토이며 기존 결과와 성능을 섞지 않는다.

응답은 기존 설명 필드 외에 `proposal_status`, `compared_failed_hypotheses`, `new_evidence_ids`, `difference_from_failed`를 포함한다. 대안 제안은 전체 제공 실패 ID 대조·새 근거 ID·실패 조건과 다른 점을 모두 명시해야 한다. 기존 실패 ID를 다시 열려면 명시적인 새 반증 근거(`reopen_evidence`)가 추가로 필요하다. 근거가 없으면 `stop`으로 끝내며 자동 Codex 검토·구현으로 전달하지 않는다. ID와 필드 검사는 인과적 타당성을 증명하지 않으므로 통과한 제안도 기존 Codex 코드/SHA 대조와 실험 판정을 거친다.

명령과 호출 상한은 유지한다. 과거 v1/v2/v3 응답·체크포인트는 이전 계약대로 읽고 새 계약과 캐시를 섞지 않는다. 이 변경의 검증·핵심 diff·롤백: `artifacts/evidence-grounded-review-20261022/REPORT.md`.

## 품질 규칙 연결 (2026-11-25)

새 가설·계획·결과 보고에는 [품질 규칙](docs/agent/QUALITY_RULES.md)을 함께 적용한다. 본문은 그 문서에만 둔다.

- 계획 전: `error-cause-triage`(오류 원인 분류), `can-this-experiment-tell`(판별 가능성 관문), `stop-repeated-misses`(같은 평가 자료의 연속 미달 횟수 기록. 상한 3은 **사용자 승인 기록과 main 통합이 모두 끝난 뒤 발효**하며 근거는 `docs/collaboration/plans/quality-threshold-proposal-20261125.md`).
- 연속 미달 횟수는 같은 `cohort_sha256`에서 완료된 모델 실험(`experiment_kind`가 `diagnostic`이 아니고 실패·중단 제외)의 `result.acceptance_passed`가 false인 연속 횟수이며 통과하면 0으로 돌아간다. 통합 뒤 새 실험부터 세고 과거 미달은 세지 않는다. 계획의 `acceptance`가 달라도 같은 평가 자료면 이어서 세되 기준이 달랐음을 적는다.
- 횟수가 3에 닿으면 그 평가 자료로 새 모델 가설을 내지 않고 `error-cause-triage`의 라벨·사진 조건·입력 경로·기준 쪽 진단이나 자료 요청만 제안한다. 세션 중단 조건이 아니며 다른 독립 작업은 계속한다.
- 계획·판정: `zero-denominator-unmeasured`(분모 0 상한은 미측정). 결과 보고: `chance-check`(우연·반복 시도 표기), `experiment-closeout`(세 칸). 새 라벨 묶음: `fresh-labels-test-first`. worker 리뷰: `worker-review-checklist`.
- 이 규칙은 사전 기준·배점·승인·보호 조건을 바꾸지 않으며 새 실험을 승인하지 않는다. 정확도를 높인다는 측정은 없다.

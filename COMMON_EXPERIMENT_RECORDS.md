# 공통 실험 기록

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

## 개발 세션에서 정체 시 자동 연결

`development-review.json`에 지정한 ‘카드분석 AI 만들기’ 세션에서 기존 공통 실행기를 사용하면 결과 저장 후 기존 latest_packet 정체 판정을 재사용한다. 완료 실험이 사전 기준을 충족하지 못해 정체 검토가 가능하고 새 근거가 있을 때 자동 review 경로를 동기 실행한다. 실행 실패/중단은 성능 실패로 바꾸지 않으며, 사전 기준 충족·새 근거 없음·다른 세션·비활성 정책에는 AI 검토를 호출하지 않는다. 단순히 시간이 지났거나 대화가 길다는 이유로 정체를 추정하지 않는다.

원래 실험 종료 코드는 그대로 유지한다. 자동 검토 결과는 원래 실험 폴더의 `development_handoff.json`에 별도로 저장하며 `artifacts/development-cycle/latest.json`으로 찾는다. 여기서 review 상태·next_steps·분리된 토큰 기록·자동 공통 실험 record·수용/개선/복원 여부를 확인하고 개발을 이어간다. 자동 검토 실패가 원래 실험의 완료를 실패로 덮어쓰지 않는다. 요청 전 journal을 저장해 중단 후 같은 연결을 자동 재시도하지 않는다.

코드 수정은 `./develop -- <수정 명령>`, 기존 실험·review 진입점은 공유 OS 파일 잠금을 사용한다. 수정 명령이 공통 실험을 실행하면 잠금 descriptor를 안전하게 상속해 동일 소유자의 중첩 실행을 허용한다. 다른 프로세스는 호출/수정 전에 즉시 중단한다. descriptor를 받은 자식이 살아 있으면 부모가 반환해도 잠금은 유지된다. 잠금 파일을 삭제해서 해제하지 않는다. 모든 편집자는 이 협력 규약을 따라야 하며 임의 외부 편집기를 강제로 막는 보안 장치는 아니다.

자동 검토의 공통 실험은 review_scope로 감싸 새 후속 검토를 시작하지 않는다. 자동 연결 하나당 기존 Gemini 기본1회·최대3회, Codex 기본 검토1회·교정최대1회·구현1회와 캐시/롤백 규칙을 그대로 사용한다. 다른 데스크톱 세션에 메시지를 보내 깨우지 않으므로 실제 AI 호출 금지 테스트에서도 세션 호출이 없다. 지정 세션이 다음 개발을 재개해 공통 실행기를 사용할 때 적용된다. 결과를 해석하고 다음 승인 작업을 선택하는 것은 개발 세션의 역할이며 프로그램이 현재 대화 자체를 LangGraph에 넣는 것은 아니다.


## 증거 기반 3자 검토와 심판 정책 (2026-10-23)

명령은 `./review --auto` 그대로다. Gemini는 대안 가설의 옹호·검증자, NVIDIA Lightning은 비판자, 별도 Codex CLI는 독립 심판이다. `cross_review_roles.py`의 역할 지시를 분리한다. Gemini v5와 NVIDIA v3 요청/캐시 버전은 역할 변경을 구분하며, 동일 자료의 정상 Gemini v4 저장 응답도 추가 호출 없이 재사용한다. 과거 발언을 새 역할로 수행했다고 소급 표시하지 않는다.

추가된 `cross_review_adversarial.py` StateGraph는 Initialize → Advocate → Skeptic → Evidence Verification → Judge → Decision Router → Final Report로 진행한다. Advocate/Skeptic 노드는 기존 호출 어댑터가 제공한 공개 응답을 받으며 별도 LLM을 중복 실행하지 않는다. CONTINUE/REVISE이면 보고·심판 피드백을 저장하고 interrupt한다. 기존 Gemini 조건부 루프가 피드백·상대 반론으로 다음 응답을 받은 뒤 프로그램이 Command(resume=...)로 정책 그래프를 재개한다. 기존 Gemini SQLite와 선전송 journal, 새 정책 그래프의 adversarial.sqlite를 구분한다. 에이전트의 내부 사고 과정은 수집하지 않는다.

`adversarial.json`은 질문/현재 가설/라운드/양측 발언/증거 레지스트리/검증 사실/쟁점/심판 피드백·점수/진전·정체/판정/최종 보고를 보존한다. 다음 Codex 교정에도 이전 심판 피드백을 명시적으로 전달한다. 동일 정책 입력을 재평가해도 이력이나 모델 호출을 늘리지 않는다. 오류·대기·상한으로 종료하면 진행 중 정책도 UNCERTAIN으로 닫는다.

새 심판 출력 `debate_assessment`는 양측의 출처 신뢰성35%·논리25%·반박 대응20%·독립성20% 점수와 근거 ID·미해결 쟁점을 받는다. 프로그램이 가중 합계를 계산한다. 출처 미확인 점수와 단일 원자료의 독립성 점수는 최대49로 제한한다. 미참여는0, 과거에 평가하지 않은 점수는 미확인으로 남긴다. SHA가 같은 자료는 같은 원자료로 묶는다. 서로 다른 파일이라도 실제 독립성의 증명은 아니며 심판의 의견으로 표시한다. source SHA 확인은 파일 진위 검사이며 요약·인과 해석의 참을 증명하지 않는다. 외부 검색은 비활성 상태로 명시한다.

ACCEPT/REJECT는 프로그램이 생성한 `machine_claim`의 지정 JSON 필드·기대값을 SHA가 일치하는 원자료와 직접 대조할 때만 해당 좁은 명제에 사용할 수 있다. 현재 수집기의 인과 가설에는 이를 자동 생성하지 않는다. 양측 합의·높은 점수·실험 select만으로 가설을 입증하지 않으며 UNCERTAIN으로 남긴다. UNCERTAIN이어도 기존 검증을 통과한 실험 select는 개발·공통 실험을 진행할 수 있다. 성능은 실제 공통 실행 결과에서 별도로 판정한다.

기본1회, 필요할 때만 검토/교정의 유효 최대2라운드다. 사용자가 보낸 일반 설계의 최소2·최대8라운드는 적용하지 않는다. Gemini 최대3, Codex 검토1·교정최대1·구현1, NVIDIA 최대2의 기존 예산이 우선한다. 동일 주장 반복, 새 검증 근거 ID가 없는 정체2회, 사람/자료 필요, 명시적 stop, 상한에서 종료한다. 새 질문의 표현만 바꿔도 정보 진전으로 계산하지 않는다. recursion_limit=16은 추가 안전장치다. 전송된 실패/결과 불명 요청은 재시도하지 않는다.

NVIDIA는 `nemotron-review.json`의 승인 범위·키 바인딩·24시간 이내 무료 확인과 실제 요청 전 공식 무료 엔드포인트 상태를 확인한다. 유료 전환 신호/402, 429, 인증·요청 오류는 provider-alerts에 저장하고 NVIDIA만 제외한다. 유료 fallback·프로젝트/키 교체는 없다. 현재 허용 모델은 무료 확인된 Lightning 하나다. 임의 공급자/모델은 무료 안전 계약 없이 허용하지 않는다. 입력/출력을 NVIDIA가 기록·제품 개선에 사용할 수 있다는 동의 범위를 유지한다.

모든 공개 발언·근거·품질 점수·종료 사유는 `debate.html`/`debate.json`에서 본다. 기존 `next_steps`와 개발 handoff에도 HTML 경로를 연결한다. 이번 변경의 모의 검증·호출·리스크·롤백은 `artifacts/nemotron-debate-20261022/REPORT.md`에 기록한다.


## 2026-10-23 적대적 검토 High 결함 보완

`./review --auto`의 새 자료는 Codex 개선안 → Gemini 독립 비판 → Codex의 비판 ID별 답변/수정안 → NVIDIA 독립 심판 순서다. 필요한 경우 Codex 수정안을 Gemini에 한 번 재전달하며 검토 1회·교정 최대 1회·구현 제안 1회를 넘지 않는다. Gemini의 `stop` 의견은 API/권한/예산 오류와 구분하며 독립 심판이 확인한다. NVIDIA 무료/키/동의 확인이 없으면 심판을 임의 대체하지 않고 종료한다. 수동 review 경로는 유지한다.

ACCEPT/REJECT는 원래 인과 가설에 붙이지 않는다. 동결 JSON의 지정 필드에 대한 명시적 기계 명제만 직접 판정하며, 인용 오류·미해결 쟁점이 있으면 UNCERTAIN이다. 점수·합의·실험 선택은 모델 성능의 증거가 아니다. 완료 진단 측정값과 비판 원문은 보존하고 입력 예산 초과 시 잘라 판단하지 않고 호출 전 차단한다.

**자동 실행 제한:** 현재 생성 worker의 안전한 격리 실행과 독립 모델 재평가 경로가 없다. 모델이 만든 worker가 사람 정답을 점수로 복사해도 기존 공통 기록은 실제 추론 여부를 인증하지 못한다. 따라서 자동 검토는 `implementation-proposal.json`에 최소 변경/worker를 미적용 상태로 저장하고 `trusted_execution_required`로 끝낸다. 모델 소스 적용·worker 실행·성능 채택은 하지 않는다. 이 차단은 격리 평가 구현 완료를 뜻하지 않는다. 개발자가 검토한 신뢰된 실험은 기존 `./experiment --plan ... -- ...` 경로를 사용한다.

과거 검토·실험·중복 방지 기록을 덮어쓰지 않는다. 구버전 자동 검토는 읽기 전용이며 새 역할 프롬프트만으로 같은 자료를 재호출하지 않는다. 새 검토 재개는 journal/checkpoint를 재사용하고 실패·결과 불명 요청은 자동 재시도하지 않는다. NVIDIA 피드백을 여러 라운드 반복 반영하는 8라운드 범용 토론은 이번 제한된 흐름에 구현했다고 간주하지 않는다.


## 2026-10-23 격리 학습·독립 계산 평가 연결

새 자동 연결은 NVIDIA 의견을 받은 뒤 기존 구현 슬롯의 Codex가 `final_decision=proceed/stop/wait`와 이유를 명시한다. 별도 Codex 요청을 늘리지 않는다. proceed와 코드/SHA·근거·기준 검사를 통과한 경우에만 자동 공통 실험으로 연결한다. Code 검토1·교정최대1·최종판단/구현1, Gemini 전체최대3(실행 옵션으로 추가1 제한 가능), NVIDIA 기존 상한과 완료/불명 요청 비재시도를 유지한다. 과거 trusted_execution_required 기록을 소급 실행하지 않는다.

`trusted-experiment.json`은 현재 고정 74개 행·26개 개발용 평가와 필수 회귀 자료의 feature cache/학습 metadata/기준 가중치/보조 학습 소스를 SHA로 고정한다. 지원 adapter는 `isolated-linear-patch-v1` 하나이며 임의 아키텍처·다른 모델 소스 변경을 이 평가로 검증했다고 취급하지 않는다. 새로운 데이터·구조는 신뢰된 계약 갱신 전 차단한다.

생성 worker는 macOS sandbox-exec에서 fold별로 실행한다. 환경변수는 명시한 최소 목록만 주고 API 키·이전 환경·평가 reference는 전달하지 않는다. 프로젝트의 후보 소스 복사본과 그 fold의 학습 특징·mask·target·point_tokens·weights·ids만 읽는다. 원본 저장소 내용·다른 fold·평가 자료·비밀 파일·네트워크는 차단한다. 출력은 model.json의 유한한 coef/bias만 허용하며 stdout.log 외 쓰기도 차단한다. CPU/벽시계 시간·열린 파일·파일 크기를 제한한다. macOS 격리가 실패/미지원이면 비격리 실행으로 대체하지 않는다. 하드 메모리 한도나 모든 운영체제에 대한 보안 인증을 구현했다고 주장하지 않는다.

프로그램의 신뢰된 평가기는 생성 코드를 import/실행하지 않고 가중치로 동결된 특징에서 max-patch sigmoid와 기존 사람점 점수를 직접 계산한다. 원래 기준 모델의 점수 재현, 그룹/원본·decoded-photo 분리, 평가 ID/정답/순서, 필수 코호트와 사람점 보호를 검사한다. worker가 쓴 scores/observations는 읽지 않는다. request/policy/evaluator/가중치/관측 SHA를 evaluation-attestation.json에 저장하고 공통 record에도 묶는다. 이것은 계산 경로의 분리이며 독립 시험 자료나 일반화 개선의 증명이 아니다. worker 내부 학습 과정의 정직성을 수학적으로 증명하는 장치도 아니다.

후보 학습·평가는 기존 공통 실행기의 prepare/run 계약으로 한 번만 기록한다. 평가 전에는 원본 소스를 수정하지 않는다. 사전 기준 충족과 같은 평가 자료의 실측 개선이 함께 확인된 경우에만 허용 소스를 적용한다. 기준 미달/개선 없음/실행 실패는 격리 후보를 폐기하고 원본은 유지한다. 사용자 수정은 덮어쓰지 않으며 적용 중 실패하면 원본 snapshot으로 복원한다. 실행 journal을 선저장하고 pending/중단/실패 학습은 재시도하지 않는다. 완료 후 재개는 저장한 결과만 복원한다. 결과는 모델 선택/개발용이며 production_adopted=false다.

증거의 반복 값은 `$ref` JSON Pointer로 무손실 공유한다. 평가 원문·조건·진단 수치는 삭제하지 않으며 Python에서 원문 복원이 가능하다. Codex/심판 입력은 각각의 전송 루트에 맞게 참조를 다시 만든다. 입력 한도는 올리지 않고 초과 시 호출 전에 차단한다.


### 실제 실행 후 입력 보완

실제 076357246710 검토는 Codex 검토1·Gemini1 이후 교정 입력 36,444바이트가32KB를 초과해 발송 전 중단했다. 재전송하지 않았다. 수정 후 교정 단계는 원래 인용된 함수의 전체 정의와 의존 정의만 제공하고 누락 함수는 명시한다. 새 인용은 실제 그 단계 입력에 들어간 원문에서만 허용한다. 중복 코드 인용/성공·실패 서술은 이미 고정된 수치 기준과 원본 호출 기록으로 연결하며, Gemini 반론·진단 수치·실패 조건은 자르지 않는다. 전체 문서 참조는 원문 복원이 가능한 `$ref`로 표시한다. 저장된 동일 제안·반론의 모의 재검사는31,791바이트로 통과했으며 실제 교정 호출은 하지 않았다.

최종 고정 학습 경로의 baseline_training_contract에는 실행 worker의 SHA와 `normal_reduction='max_bound'` 호출을 명시한다. 실제 Codex가 mean_odds 분기를 선택한 일을 성능 개선으로 취급하지 않는다. 사용되지 않는 분기 변경과 역할 동의를 사람 확인으로 잘못 기입하는 문제는 이후 실제 응답에서 재검증해야 한다. 기존 response/journal은 고치거나 소급 성공 처리하지 않는다.


### 2026-10-23 명시적 재개 검증
- `artifacts/manual-cross-review/076357246710`의 최초 Codex 검토·Gemini 응답을 보존한 채 재개했다. 입력 검사에서 미전송된 교정만 실제 1회 요청했다. Gemini 추가 요청은 0회다.
- 기준 worker의 고정 `baseline_training_contract` 원문/SHA를 제공했으므로 해당 인용도 검증한다. 제공하지 않은 함수는 인용할 수 없고 저장된 응답을 보완/변조하지 않는다.
- 교정 응답은 실제 사용 중인 `max_bound` 온도 변경을 제안했으나 `failed_executions` 4개를 `failed_hypotheses_checked`에 섞어 계약 검사에서 종료했다. 실행 실패를 가설 반증으로 사용할 수 없으므로 심판·구현·실험으로 넘기지 않았다. 이후 프롬프트는 두 ID 목록을 명시적으로 구분한다.
- 전체 누적 실제 요청: Codex 검토 1회·교정 1회(41,909토큰), Gemini 1회(11,596토큰), NVIDIA 0회(usage 미확인/해당 없음). 이번 재개분은 Codex 교정 1회 21,235토큰이다. 현재 채팅 토큰은 이 수치에 포함되지 않는다.
- 격리 실행/별도 추론은 합성 데이터로 실제 macOS 프로세스까지 테스트했다. 이번 최신 프로젝트 후보는 실행하지 않았으므로 성능 개선·실환경 전체 연결 성공을 주장하지 않는다.
- 상세 기록/변경 diff/백업 기반 롤백: `artifacts/isolated-auto-experiment-20261023/index.html`.


### 공통 근거와 분류 경고의 개발 승인 분리
- 새 자동 검토는 `shared-core.json`에 현재 baseline worker의 실제 호출식·SHA, 기준 결과 경로를 동결한다. 근거 registry의 해시도 묶어 변경을 검사한다. Codex 모든 단계·Gemini 첫/추가 검토·NVIDIA 심판에 동일한 shared_core를 전달한다. 기존 예산 상한은 유지한다.
- `failed_hypotheses_checked`에 필수 가설 ID가 모두 있고 추가 ID가 제공된 `failed_executions`에만 속하는 경우, 원본 응답은 보존하고 별도의 classification_issues에 원래 목록·잘못 섞인 ID·프로그램의 정규 분류를 저장한다. 실행 실패는 반증된 가설로 채택하지 않는다. 이 경고를 심판에게 전달한다.
- 필수 가설 누락·알 수 없는 ID·잘못된 코드 인용·변경된 근거는 기존 차단을 유지한다. API/한도/인증/미확인 요청은 자동 재시도하지 않는다.
- 심판 후 `development-gate.json`에서 프로그램의 정규 분류에 엄격한 기존 검증을 다시 적용한다. 사람 확인/미해결 반론/심판 거절이 있으면 개발을 허용하지 않는다. 점수나 찬성만으로 승인하지 않는다. 분류만 고칠 뿐 가설·변수·판정 기준·worker를 보완하지 않는다.
- 심판 입력에는 전체 반론·실험 근거·현재 실험 내용·수치 acceptance를 유지한다. 이미 수정된 이전 제안의 절차 설명, 현재 숫자와 겹치는 판정 문장, 파일 수집 관리 metadata는 제외하고 이를 projection_note에 명시한다. 원본은 기존 journal에 남는다.
- 기존 중단 검토를 자동 재개하거나 과거 응답을 새 공통 근거로 보낸 것처럼 처리하지 않는다. 저장된 Codex/Gemini의 shared_core가 다른 경우 재호출 없이 보존한다. 캐시/상한/격리 평가/롤백은 기존 경로를 사용한다.
- 검증·diff·롤백: `artifacts/debate-contract-fix-20261023/REPORT.md`. 실제 AI 호출 없이 검증했으며 모델 성능 개선이나 실제 심판 품질 검증은 아니다.


## Gemini·NVIDIA 무료 전용 보호와 실측 화면 (2026-10-24)

- Codex는 기존 이용 방식·설정 그대로 유지하며 이번 무료 API 차단 대상이 아니다.
- Gemini는 전용 키·설정 모델에 연결된 실제 Free tier/결제 미연결 확인이 있어야 호출한다. 확인 기록의 model, project_id, evidence, key_sha256, verified_at, expires_at 및 billing_disabled=true를 검사한다. 유효 기간은 최대24시간이다. 기존 Free 표시만 있는 오래된 기록은 허용하지 않는다. 실제 계정 상태를 확인하지 않고 필드를 작성해 우회하면 안 된다. 결제 요구(402)는 provider-alerts/gemini-disabled.json에 보존하고 자동 재시도하지 않는다.
- NVIDIA는 기존 무료 확인·회로 차단을 유지하고 실제 POST 직전에도 공식 무료 엔드포인트 상태와 고정 모델·주소를 재검사한다. 유료 fallback, 결제·충전·한도 구매는 없다. 외부 계정에서 사용자가 직접 바꾼 과금 설정까지 로컬 코드가 통제할 수는 없다.
- ./review --web의 /nvidia는 별도 읽기 전용 평가 화면이다. canonical nemotron-cache/*/call.json만 집계하여 재사용된 복사본을 중복 계산하지 않는다. 요청 수·형식 검사·실제 토큰·응답 시간과 SHA에 연결된 수동 품질 주석을 보여준다. 정답 일치율·단일 LLM 대비 효과·카드 모델 개선은 별도 실측 전 미측정이다. 페이지를 열어도 AI를 호출하지 않는다.


### 토론 재개 준비 (2026-10-24)
Gemini 최신 무료 확인은 data/gemini-free-verification.json에 저장한다. 과거 동결 설정의 프로젝트·모델·현재 키 SHA와 모두 일치할 때만 요청 직전 그 확인을 적용한다. 확인 갱신은 과거 API 입력·캐시·체크포인트를 변경하지 않는다. 결제 미연결·최대24시간·유료 차단 조건은 동일하다.
NVIDIA v6 심판 입력은 현재 수정안의 judging_target을 명시하며 철회안은 ID/철회 표시만 남긴다. 원본 검토 기록은 보존한다. Gemini 원문과 Codex 답변, 근거 registry ID와 비판 ID를 구별하도록 지시한다. 응답의 reviewed_hypothesis_id가 현재안과 다르면 개발을 차단한다. criticism_checks 배열·근거 ID·완전성 검사도 유지한다. JSON 객체 모드를 유지하며 실제 무료 호스팅 엔드포인트의 서버 스키마 강제를 검증했다고 주장하지 않는다.
모의 회귀 검증 후 기존 response_error 회로만 명시적으로 복구 준비할 수 있다. 402·한도·인증·결과 불명 차단은 임의 해제하지 않는다. 응답 복구 준비는 과거 실패 응답의 성공 전환이나 자동 재시도가 아니다. 새 실제 호출은 별도 승인된 실행에서만 가능하며 호출 상한은 동일하다. 화면의 실제 응답 미검증 표시를 유지한다.


### 격리 학습 진단 기록

자동 검토의 격리 worker는 학습 전용이며 `model.json`의 `coef`/`bias`만 내보낸다. 평가·`observations.json` 생성은 신뢰된 외부 실행기가 담당한다. worker가 평가 정답이나 기준 점수에 접근해 진단을 작성하지 않는다.

실행기가 삽입한 bootstrap은 LBFGS 실행을 관찰하고 각 fold의 `output/training-diagnostics.json`에 최종 `max_gradient`, 실제 optimizer `n_iter`에 해당하는 `iterations`, `function_evaluations`, `converged`를 남긴다. 추가 closure 호출이나 optimizer 설정 변경은 없다. function_evaluations는 optimizer 내부 카운터이며 fitter가 step 이후 별도로 호출한 closure까지 포함한 총 횟수는 아니다. `converged`는 기존 fitter의 최종 기울기 기준 `1e-5`를 사용한 관찰이며 모델 성능을 뜻하지 않는다.

성공/실행 실패 시 부모는 이를 공통 실험 폴더의 `training-diagnostics.json`으로 집계하고 record.json에 SHA를 등록한다. 강제 종료·미지원 optimizer·진단 파일 부재는 `unavailable`, 잘못된 자료는 `invalid`이며 미확인 값은 null이다. 실패를 수렴이나 성능 0으로 대체하지 않는다. 완료 평가의 attestation에도 집계 파일 SHA를 묶는다. review는 최신 완료 실험의 진단 파일을 `latest_training_diagnostics` 근거로 가져온다.

진단은 `isolated_process_observation`, `independently_verified=false`로 표시한다. 같은 Python 프로세스의 학습 코드는 관찰에 영향을 줄 수 있으므로 이 기록을 독립 성능 증명이나 자동 채택 근거로 사용하지 않는다. 기존 FP/FN·사람점·필수 코호트 독립 평가, 호출 상한·journal 중복 방지·실패 재시도 금지·후보 폐기/롤백을 유지한다. 과거 동결 계약·기록은 덮어쓰지 않는다.


### Codex app-server 연결

`./review --auto`의 기본 Codex 전송은 `codex app-server --listen stdio://`이다. 기존 로그인과 모델 설정을 사용하며 API 키/플랜/유료 fallback을 새로 설정하지 않는다. 모델 검토는 read-only·도구/메모리/앱/MCP 비활성 상태의 새 ephemeral thread에서 단계당 turn/start 한 번이다. 검토1회·교정 최대1회·구현1회와 기존 Gemini/NVIDIA 상한은 유지한다. 예상 밖 도구 요청·추가 턴·모델 전환·불완전 응답·시간 초과·사용량 미확인은 자동 재시도 없이 종료한다. app-server 장애 시 CLI로 자동 fallback하지 않는다. 기존 CLI 완료 저널은 재사용한다.

최종 프롬프트 텍스트는 모든 단계32,000 bytes 이하로 검사한다. 프로토콜의 outputSchema와 Codex 내장 system instruction은 이 텍스트 크기와 별도이며 전체 모델 컨텍스트가32KB라고 주장하지 않는다. project_rules는 원본 AGENTS.md에서 하위 제안에 필요한 라벨·평가 분리·사전 기준·독립 검증·적용/복원·중복/도구 제한 규칙을 문장 그대로 발췌하고 원본 SHA를 기록한다. 부모의 개발 세션 조정·대화 종료/보고 규칙은 하위 JSON 제안 작업에 중복 전달하지 않는다. 근거의 표는 전송 시 유지하고 문서 전체의 동일 값은 shared_values 표와 짧은 $ref로 공유하며 저장된 input.json을 expand_evidence로 복원한다. 성공/실패 문장 및 수치·전체 실패 ID·코드 원문/SHA를 유지한다. 검토/교정의 latest_plan 평가군에서 중복 reference_result 경로만 생략하며 원본 경로/SHA 검사는 부모에서 유지한다.

공개 item/agentMessage/delta는 stream.json에 누적되며 기존 웹이 약1.5초 간격으로 읽는다. 생성 중·중단/실패한 문장은 미검증으로 표시하며 개발 승인에 쓰지 않는다. reasoning 이벤트·입력 프롬프트·인증 응답은 웹에 표시하지 않는다. 항목 완료 메시지가 delta보다 우선하며 JSON·기존 근거 검사 후에만 다음 단계로 진행한다. thread/tokenUsage/updated의 last 실제 사용량은 usage-metadata.json에 보존하고, 미확인을0으로 대체하지 않는다.

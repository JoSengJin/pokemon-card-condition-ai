task_id: harness-vs3-plangate-20261128
owner: Claude
status: in_progress (구현 전 확인 사항 기록)
base_sha: 1760219
branch: claude/harness-vs3-plangate-20261128
goal: VS3 최소 PLAN_GATE — EXPERIMENT_VERIFIED → ANALYZE → next_plan.json → PLAN_GATE → declared.json → graph.register_missing 연결(합성 종단 검증까지)
decisions: artifacts/harness-resume-20261127/decisions-vs3-20261128.md(사용자 승인 원문, 정본)
not_touched: harness/claude_job.py·budget.py·logical_zones.py(VS4 담당), dedupe.PLAIN_TYPES 줄(VS4), 자동 재개·재실행 안전 목록(빈 상태 유지)

# 1. 구현 전 확인 사항 (원문 3절, 코드 근거)

줄 번호는 base 1760219 기준. card_condition의 실데이터·실험 기록은 읽거나 실행하지 않았다(코드만 읽음). `development-review.json`(설정)만 열었다.

## 1-1. experiment_record.py·cross_review.py 검증 기능 재사용 가능 여부

| 기능 | 근거 | 재사용 판단 |
|---|---|---|
| 가설·기준 문구 필수 | `card_condition/experiment_record.py:155-157` prepare가 hypothesis_id·hypothesis·change·success_criterion·failure_criterion 비지 않은 문자열 요구 | 같은 규칙의 하네스 판 `harness/experiment_exec.py:54-63` build_plan을 PLAN_GATE에서 그대로 부른다(사전 등록 문구) |
| 수치 기준 형식 | `experiment_record.py:87-92` acceptance_rules(max_fp·max_fn·no_new_errors·require_actual_point_guard) | prepare 안(L158)에서만 쓰이며 prepare는 L200에서 저장소 `artifacts/experiments/` 폴더를 만들고 실제 기준 결과를 읽는다(부수 효과·실데이터). 하네스에서 부르지 않는다. 대신 PLAN_GATE는 acceptance·reference_result를 대조 실험 값과 **같아야** 통과시킨다(대조 실험은 prepare를 통과해 VERIFIED가 됐다) |
| code_changes 필수 | `experiment_record.py:183-185` 비지 않은 목록, `:188-189` card_condition/·artifacts/ 아래 .py만 | 내용이 baseline과 달라야 한다는 조건은 없다(스냅샷만 남김). 대조 실험의 code_changes를 그대로 물려받는다 |
| 변수 하나 | prepare에는 변경 변수 수 검사가 없다(L150-215 전체). `card_condition/cross_review_auto_validation_plan.py:25-33` check_experiment_parameter가 기존 관례 `experiment_parameter{name, baseline, value, scope}`(유한 숫자 하나)를 검사, worker는 `CARD_CONDITION_EXPERIMENT_DIR/plan.json`의 `experiment_parameter.value`를 읽는다(`cross_review_auto_context.py:133`) | 이 관례를 승인 변수로 쓴다: 바꿀 수 있는 자리는 `config.plan.experiment_parameter.value` 하나. 셈은 Claude 선언이 아니라 대조 계약과 제안의 실제 차이(키 경로)로 한다 |
| 기준 완화 금지 | `cross_review_auto_validation_plan.py:36-42` check_numeric_acceptance(이전보다 완화 금지) | 더 엄격하게: acceptance가 대조와 다르면 거절 |
| 기각 가설 | `card_condition/cross_review.py:89-101` proposal_gate, `:284-287` 선택 단계: `hypothesis_id in packet['failed_hypotheses']` | **ID 문자열 대조**라 ID만 바꾸면 빠져나간다(원문 1절 위반). packet은 `cross_review_evidence.py:59-` latest_packet이 저장소 실험 기록(실데이터)에서 만들고 정체 판정을 전제한다. 재사용하지 않는다 |

## 1-2. 기존 실패 기록으로 기각 가설 판별 가능 여부

- 하네스 실패 기록 `tasks/<k>/failures/NNN-<run_id>.json` = {attempt, run_id, kind, error, ts}(`harness/queue.py:145-158`): 가설 정보가 없다.
- `harness/dedupe.py:146-170` find_duplicate: 논리 키가 같은 등록 작업을 **상태와 무관하게**(실패한 실험 포함) 찾는다. 논리 키(`:132-137`)는 hypothesis_id·description·input_roles(NOTE_KEYS, `:57`)를 빼고 실제 실행 조건(command·코드·config·seed·입력 SHA)으로만 만든다 → 가설 ID·설명만 바꾼 재제안은 같은 키. 이것을 기각 판별로 재사용한다(새 실패 가설 관리 체계 없음). 성공한 같은 실험의 반복도 거절된다(더 엄격, AGENTS "동일 입력 반복 학습 금지"와 같은 방향).
- 빈틈(5차 P1, `verify-auto-resume-123-r5.md` P1·`verify-123-r5-scripts/r5_tree_key.py` A): 코드 자리가 저장소 HEAD tree 전체라 문서만 바꾼 커밋 뒤 같은 실험이 새 키가 된다 → 원문 4절 "문서 커밋만 변경된 동일 실험의 중복 실행 차단"으로 고친다(2절).
- DESIGN 11절 "탐색 2회 실패" 같은 횟수 규칙은 코드에 없다. 새 임계값을 만들지 않고 "같은 실행 조건은 다시 등록하지 않음"만 쓴다.

## 1-3. development_handoff.json에서 ANALYZE로 이어지는 실제 입력 경로

- `card_condition/development_review.py:29-96` after_experiment가 `artifacts/experiments/<id>/development_handoff.json`을 쓰는 것은 `enabled(root)`(`:21-26`)일 때뿐이다: `development-review.json`의 enabled가 true이고 session_id가 환경변수 CODEX_THREAD_ID와 같아야 한다. 현재 기본 checkout의 `development-review.json`은 `"enabled": false`이고, 하네스 실험 어댑터는 환경을 PATH·LANG·PYTHONIOENCODING만 넘긴다(`harness/experiment_exec.py:41`). → **하네스 경로에서는 development_handoff.json이 생기지 않는다.** 그 next_steps도 외부 AI 검토(`./review --auto`, `:65`)의 산출물이라 승인 범위 밖이다.
- 실제로 이어지는 입력: ./experiment가 원본 저장소에 남기는 동결 기록 `artifacts/experiments/<experiment_id>/{record.json, result.json, plan.json}`(`experiment_record.py:199-215`). 하네스 실험 작업의 out/에는 record.json·result.json 사본(바이트 동일, `experiment_exec.py:123-129`)이 있고, record.json의 `files["plan.json"]`이 동결 plan.json의 sha256이다(`experiment_record.py:211`).
- Claude 작업 입력은 source_root(원본 저장소)에서만 복사되며 하네스 root 안 파일은 거절된다(`harness/claude_perm.py:79`). 그래서 ANALYZE 계약의 inputs는 out/ 사본이 아니라 원본 저장소의 위 세 파일 경로 + 하네스가 아는 SHA(out 사본의 manifest, record.files)로 만든다. 실행 직전 stage_inputs가 SHA를 다시 대조한다.
- 한계: `claude_job._prompt`(`harness/claude_job.py:135-151`, VS4 소유)는 유형별 지시가 없어 실제 claude는 next_plan.json 형식을 알 수 없다. 합성 시험은 가짜 claude로 한다(6절 필요 변경).

## 1-4. A군 권한과 code_changes 필수 조건에서 자동 실행 가능한 실험 유형

- 실행 가능한 Claude 묶음은 A뿐(`harness/claude_perm.py:33` RUNNABLE): experiment_log_summary·misanalysis_general·repeated_failure_analysis(`:29`), 읽기 + `./out/**` 쓰기만(`:34-35`, 명령 실행 도구 없음). Claude는 코드를 바꿀 수 없다.
- 실험 executor는 `experiment` 유형 하나(`experiment_exec.py:142`), 계획은 계약 config.plan에서만 만들고 실행 파일은 어댑터가 고정한다(`:10-13`).
- 따라서 **자동 등록까지 연결 가능한 유형**: 사람이 등록한(또는 그 계보의) `experiment` 대조 계약이 `config.plan.experiment_parameter`를 갖고, Claude가 `value` 하나만 바꾸는 매개변수 실험. command·inputs·code_sha·code_changes·acceptance·reference_result·성공/실패 기준 문구는 대조에서 물려받거나 결정론 코드가 정한다.
- **연결할 수 없는 유형(현재 권한·계약상)**: 코드 변경 실험(C군 general_dev 등 미실행, 형식적 코드 변경으로 우회하지 않음), 새 worker·명령·평가 자료가 필요한 실험, 학습·평가 유형(executor 없음), Silver·이미지(B군 미실행), 승격(미승인). 대조 계약에 experiment_parameter가 없으면 변수 하나를 셀 수 없어 그 계획만 대기한다.
- 실제 ./experiment는 sandbox 안에서 원본 저장소 쓰기가 막혀 진입점에서는 결과 불명이 된다(VS2 문서 "사용자 확인 필요" 1). VS3 진입점 증거는 가짜 실험 executor로만 한다.

# 2. 설계 결정(구현 전)

- 새 파일 `harness/plan_gate.py`(결정론, LLM 없음) + `supervisor.py` 한 줄: declared.json을 읽은 뒤 `plan_gate.gate`가 (1) VERIFIED 실험마다 ANALYZE(misanalysis_general, outputs next_plan.json, depends_on=[실험]) 선언 추가, (2) VERIFIED이며 하네스가 만든 ANALYZE의 next_plan.json을 검사해 통과한 다음 실험 계약을 declared.json에 추가, (3) LLM 작업에 직·간접 의존하는 실험·학습·평가 선언은 PLAN_GATE가 이번 회차에 만든 계약과 정확히 같을 때만 register_missing에 넘긴다(직접 작성 우회 차단).
- next_plan.json(Claude 제안, 이 키만): hypothesis_id·hypothesis·change(문구), variable(선언, 신뢰하지 않음), plan(제안 config.plan 전체). 차이 계산은 키 경로 튜플(점이 든 키로 위장 불가), 자료형까지 비교.
- code_sha는 PLAN_GATE가 source_root HEAD를 읽고 `dedupe.verify_code`로 확정한다. 대조 실험 커밋과 코드 지문이 다르면(코드가 바뀜 = 두 번째 변수) 대기.
- 예산: 실행 직전 최종 차감은 VS2의 runner.charge(논리 키 멱등)만. PLAN_GATE는 `budget.usage`로 남은 실험 예산을 읽기만 하고 없으면 대기(차감 경로를 새로 만들지 않음).
- 거절(refused, Claude 제안 위반)·대기(waiting, 지금 확인 불가)는 그 계획만 멈추고 `graph.note_rejected`로 장부·알림 한 번(같은 사유 반복 안 함). 독립 작업은 계속한다.
- runner 오염원(메인 확인 사항, 2026-11-28): `runner._scan`은 VERIFIED여도 LLM 작업에 의존하는 Python 작업을 실행하지 않는다(`harness/runner.py:63-69`). 다음 실험이 ANALYZE에 의존하면 등록돼도 실행되지 않는다. **(나)를 택한다**: VERIFIED인 LLM 작업만 오염원에서 뺀다(미검증·실패·대기·손상 LLM 의존은 계속 차단, runner는 LLM 작업을 실행하지 않음). 이유: 계보(어느 분석에서 나왔는지)를 depends_on에 두어야 (3)의 우회 차단이 "LLM 출력에서 나온 실험은 PLAN_GATE 파생과 같아야 한다"로 결정론적으로 판정된다. (가)(의존 없이 기록만)는 사람이 쓴 선언과 PLAN_GATE 선언을 구분할 별도 승인 기록이 필요해 새 저장소가 된다.
- P1(문서 커밋): 논리 키의 코드 자리를 "HEAD tree 전체"에서 "`docs/` 아래 `.md` 일반 파일을 뺀 추적 파일 목록의 sha256"으로 바꾼다. command·config 글자에 `.md`가 있으면 아무것도 빼지 않는다. 루트 .md(AGENTS.md는 `cross_review_auto_context.py:16`이 읽음)·docs/ 아래 .md가 아닌 파일·링크는 코드로 본다.

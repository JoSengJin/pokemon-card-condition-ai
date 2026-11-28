task_id: harness-vs3-plangate-20261128
owner: Claude
status: ready_for_review (합성 종단 검증까지. 실제 claude·실제 ./experiment 연결·활성화 아님)
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

# 3. 커밋

| 커밋 | 내용 | 바꾼 파일 | 함수 수(전→후, lambda 포함) |
|---|---|---|---|
| 94b9bf6 | 구현 전 확인 사항·설계 결정 | 이 문서 | — |
| 6d76b2f | 문서(docs/*.md)만 바꾼 커밋 뒤 같은 실험 = 중복(필수 9, 5차 P1) | harness/dedupe.py(verify_code 한 hunk + 설명, PLAIN_TYPES 줄 미변경), tests/test_harness_vs3_doc_commit.py(새) | dedupe 6→6, 새 시험 6 |
| 5144dee | plan_gate 새 파일, supervisor 한 줄, runner 오염원 (나), 시험 | harness/plan_gate.py(새), supervisor.py, runner.py, tests/harness_plan_gate_kit.py(새), test_harness_vs3_gate.py(새)·_gate_flow.py(새)·_entry.py(새) | plan_gate 6, supervisor 4→4, runner 6→6, kit 7, gate 7, flow 6, entry 4 |
| a7db7ee | 변이 M8·M13 생존 보강 시험 | tests/test_harness_vs3_gate.py | 7→7 |

구조(AST, tests/harness_depth_kit.py): supervisor.run 4(기존 최장 경로 그대로), plan_gate.gate 3(`gate → budget.usage → ledger.verify → _check_line`, `gate → find_duplicate → logical_key → _command`), runner.main 4, harness 정적 그래프 전체 최장 4. 재귀 없음(_diff는 반복형). 새 경로: supervisor.run → plan_gate.gate(1) → {_analyze·_derive·_screen·find_duplicate·budget.usage·note_rejected·write_json·ledger.append}. 정적으로 확정할 수 없는 경로 없음(plan_gate는 동적 호출을 쓰지 않는다).

# 4. 필수 합성 시험 대응(원문 4절 12개)

"수정 전 실패 확인": P1은 dedupe 변경 전 HEAD(94b9bf6)에서 실행해 실패를 봤다. 관문 시험은 구현 뒤 HEAD 복사본에 "관문 없음" 변이(M0: gate가 선언을 그대로 돌려줌 = 수정 전 동작)와 runner 옛 오염원(M10)을 넣어 실패를 봤다(scratchpad `vs3-mut/run.log`). 결과는 최종 HEAD 기준.

| # | 항목 | 시험 이름 | 수정 전 실패 확인 | 결과 |
|---|---|---|---|---|
| 1 | 적격한 단일 변수 계획의 자동 등록 | test_harness_vs3_gate: test_eligible_single_variable_plan_is_declared_registered_and_runs_with_its_lineage | M0 실패, M10 실패(등록돼도 실행 안 됨) | 통과 |
| 2 | 복수 변수 변경·허위 단일 변수 선언 차단 | test_multiple_variables_or_a_false_single_variable_declaration_are_refused(값+기준값, 새 키, 선언≠실제, 점 든 키 위장, 변경 0, 자유 문구 선언, bool·문자열·NaN·거대 정수, 코드 커밋·미커밋 = 대기) | M0·M1·M2·M3·M11·M12 실패 | 통과 |
| 3 | 미승인 명령·인자·입력 자료 차단 | test_unapproved_command_arguments_or_inputs_are_refused(next_plan의 command·inputs·run_conditions·depends_on·seed·task_type·code_sha, plan의 command·extra_args·worker·code_changes) | M0·M1·M4 실패 | 통과 |
| 4 | 기각 가설 ID·설명 변경 재등록 차단 | test_rejected_hypothesis_with_a_new_id_or_description_is_refused_even_after_a_docs_commit(실패 실험 F와 같은 조건, 완료 대조로 되돌림 + 사이 문서 커밋) | M0·M5·M8 실패 | 통과 |
| 5 | 평가 자료·성공 기준 임의 변경 차단 | test_evaluation_data_and_success_criteria_cannot_be_changed_by_the_plan(reference_result, acceptance 완화·자료형만 변경, required_cohorts, threshold, independent, 기준 문구 키; 대조에 승인 변수 없음 = 대기) | M0·M1·M4·M13 실패 | 통과 |
| 6 | 예산 초과·중복 차감 방지 | test_harness_vs3_gate_flow: test_budget_exhausted_plan_waits_and_the_gate_never_charges(한도면 대기·차감 0·BUDGET_EXCEEDED 안 켬, 다음 주 등록, 두 번 돌려도 그 실험 차감 1건) | M0·M6 실패 | 통과 |
| 7 | PLAN_GATE 우회 직접 등록 차단 | test_declarations_bypassing_the_gate_are_not_registered(분석 의존 위조 선언, 결정론 작업 경유 간접 의존, 하네스가 만들지 않은 분석(같은 실험 의존)·그 의존 선언, Claude가 out/에 쓴 declared.json) | M0·M7·M9 실패 | 통과(부분 — 6절 한계 4) |
| 8 | 중단·재개 뒤 중복 등록 방지 | test_kill_and_restart_do_not_register_the_next_experiment_twice(실제 SIGKILL: 선언 저장 뒤·등록 전 + 그 사이 문서 커밋 / 등록 직후, 재시작 2회) | M0 실패 | 통과 |
| 9 | 문서 커밋만 변경된 동일 실험 중복 실행 차단 | test_harness_vs3_doc_commit 3개(중복·실행 1회 / 코드·docs의 .json·AGENTS.md·README.md·docs .md 링크·.md 이름 폴더의 .py는 다른 실험 / 명령·config가 docs .md를 가리키면 다른 실험) | 94b9bf6에서 1번 실패(DuplicateTask 안 남), 변이 4개(항상 유지·폴더 조건 제거·모드 조건 제거·이름 조건 제거) 모두 실패 | 통과 |
| 10 | 검증 불가 계획 대기 중 독립 작업 지속 | test_unverifiable_plan_waits_while_independent_work_continues(Supervisor 2회차, sandbox runner: 대조에 승인 변수 없는 계획만 대기·알림 1회, 다른 계획 등록, 독립 Python 작업 VERIFIED) | M0 실패 | 통과 |
| 11 | 사용자 추가 메시지 없이 적격 다음 계획 등록 | test_harness_vs3_entry: test_entry_point_chains_to_the_next_experiment_without_user_input_and_runs_no_real_experiment(실제 진입점, 아래 C 증거) | M0·M10 실패 | 통과 |
| 12 | 실제 실험 미승인 상태 실제 실행 0건 | 같은 시험(원본에 ./experiment 없음, 실험 기록 폴더 = 심은 2개뿐, 차감 = 가짜 executor 실행 2건) + test_without_an_executor_table_the_gate_registers_but_nothing_is_executed(executor 표 없으면 등록만, python_runs 0, claimed 0) | M0 실패 | 통과 |

추가(설계 (나)): test_runner_runs_dependents_of_verified_llm_tasks_only_and_never_llm_tasks — VERIFIED LLM 의존만 실행, PENDING·FAILED LLM 직접·간접 의존은 untouched.llm_dependents, LLM 작업은 executor가 있어도 실행 안 함. M10·M14(LLM 작업 실행 허용) 실패.
구조 시험: test_structure_function_counts_and_call_depth(새·바꾼 파일 함수 ≤7, 깊이).

변이 결과(scratchpad `vs3-mut/mutate.py`, git archive 복사본, VS3 시험 4개 모듈): M0~M14 15개 중 첫 실행 13개 잡힘, 생존 M8(이미 다음 실험을 낸 분석 재파생: find_duplicate가 막아 중복 등록은 없고 문서 커밋 뒤 거짓 거절 알림만 생김)·M13(자료형 무시 차이) → 시험 보강(a7db7ee) 뒤 둘 다 잡힘(개별 재실행 확인).

# 5. C 증거(연결, 합성 root, 대상 5144dee — 이후 커밋은 시험만)

명령(1회 실행, 3회차, 사용자 입력 없음): `python -m harness.supervisor --root <root> --claude-bin <가짜 claude> --executors tests.harness_plan_gate_kit:EXECUTORS --source-root <임시 git 원본> --max-cycles 3 --poll 0`, 실제 sandbox-exec. 사람이 한 일은 대조 실험 1개를 declared.json에 쓴 것뿐(실행 전). 원본 기록: scratchpad `vs3-c-evidence/c-evidence.json`(스크립트 `c_evidence.py`).

장부(root/ledger.jsonl, 발췌): seq0 enqueued experiment 7a2cbed8(대조) → 1 claimed → 2 completed(가짜 executor) → 3 python_drain → 4 **plan_gate_declared** misanalysis_general 5c29c8b0(depends_on 7a2cbed8) → 5 enqueued → 6 claude_job_picked → 7 claude_run_started(가짜 claude가 next_plan.json 작성) → 10 claimed → 11 completed → 12 claude_job_finished done → 13 **plan_gate_declared** experiment 196a236a(depends_on 5c29c8b0, value 0.7, code_sha = 원본 HEAD 7c971069) → 14 enqueued → 15 claimed → 16 completed(가짜 executor) → 17 python_drain. 종료 코드 0, 상태 RUNNING, claude 1회, 세 작업 모두 VERIFIED, declared.json에 세 선언.
실제 실행 0건 근거: 원본에 `experiment` 파일 없음, 원본 실험 기록 폴더 = 미리 심은 2개뿐, 예산 장부 charge 2줄(가짜 executor가 실행한 두 실험, 관문 차감 0), experiment_exec 표를 쓰지 않음.

자동 등록까지 연결된 실험 유형 / 연결할 수 없는 유형: 1-4절. 연결됨 = 사람이 등록한 `experiment` 대조 계약 계보의 `experiment_parameter.value` 한 개 변경(합성). 연결 안 됨 = 코드 변경(C군 미실행), 새 worker·명령·평가 자료, 학습·평가 유형(executor 없음), Silver·이미지(B군), 승격(미승인), 그리고 **실제 ./experiment 실행**(sandbox 쓰기 차단, VS2 사용자 확인 1)과 **실제 claude의 next_plan 작성**(지시 전달 없음, 6절 한계 1).

# 6. 한계·리스크

1. 실제 claude는 next_plan.json 형식을 알 수 없다: `claude_job._prompt`(VS4 소유, 고치지 않음)에 유형별 지시가 없다. 필요한 변경: `_prompt`에 task_type이 plan_gate.ANALYZE_TYPE이고 outputs가 [next_plan.json]일 때 키 목록(PLAN_KEYS)·"plan은 in/의 plan.json이 아니라 대조 config.plan과 같은 dict에서 experiment_parameter.value만 바꾼다"를 넣는다. 그리고 대조 config.plan 자체가 Claude 입력에 없다(입력은 동결 plan.json = config.plan + 가설 문구 + schema_version 등). 실제 연결 때 입력 방식 결정 필요.
2. 실제 ./experiment는 sandbox 안에서 결과 불명(VS2). 진입점의 실험 VERIFIED는 가짜 executor로만 보였다.
3. 등록과 실행 사이에 커밋(문서 포함)이 끼면 runner의 실행 직전 대조(code_sha = HEAD)에서 결정적 실패(차감 취소)하고, 그 분석은 이미 다음 실험을 냈으므로 그 가지는 멈춘다(VS2 runner 동작). 개선 후보: 실행 직전 대조를 코드 지문 기준으로(실행 기록에 실제 HEAD 남김).
4. 우회 차단 범위: LLM 출력에 의존하는 선언만 관문 파생과 같아야 한다. root/supervisor를 쓸 수 있는 주체(하네스·사용자)가 LLM 의존 없는 실험을 직접 선언하는 것은 사람 경로로 남긴다(같은 신뢰 영역이라 구분 불가). Claude A군의 root 쓰기 불가는 A 옵션 문서 기준이며 실환경 미확인(B4).
5. 기각 판정 = 같은 실행 조건의 실험이 이미 있음(성공·실패·인프라 실패 무관). DESIGN 11절 "탐색 2회 실패"보다 엄격하고, 인프라 실패한 실험도 같은 조건으로는 다시 제안되지 않는다(재시도는 큐의 재시도 정책 몫).
6. 예산은 읽기만: 남은 1건에 여러 계보가 동시에 등록될 수 있고, 넘는 것은 runner의 최종 차감에서 거절(budget_refused, PENDING 유지)된다.
7. runner (나)의 의미 변화: `untouched.llm_dependents`가 "VERIFIED 아닌 LLM 작업의 의존 작업"만 뜻한다. 사람이 등록한 결정론 작업이 VERIFIED Claude 작업에 의존하면 이제 실행된다(전에는 영원히 안 됨). LLM 출력에 의존하는 실험·학습·평가는 관문 파생만 등록되므로 Claude 출력이 실험 조건을 정하는 경로는 관문을 거친다. 영향 시험: 기존 test_harness_runner의 llm_dependents 기대(PENDING LLM)는 그대로 통과.
8. 문서 규칙 한계: 코드가 이름 없이 docs/*.md를 읽으면 같은 실험으로 합쳐진다(card_condition·harness에 그런 코드 없음, grep). tests/test_agent_*는 docs를 읽지만 실험 명령이 아니다.
9. declared.json 재작성: 새 선언이 있을 때만 쓰며 사용자 선언도 JSON 정규화된다. NaN이 된 거대 정수 선언이 있으면 쓰지 않고 알린다(그 회차 등록은 메모리 선언으로 진행). 사용자가 같은 순간 편집하면 덮어쓸 수 있다. declared.json이 깨졌으면 그 회차 관문도 건너뛴다(기존 파일 단위 규칙).
10. 대기·거절 계획은 회차마다 다시 검사한다(git 호출 수 회, 알림은 사유가 바뀔 때만).
11. ANALYZE 유형은 misanalysis_general(A, sonnet·medium)로 정했다(experiment_log_summary는 요약용이라 다음 가설에 맞지 않다고 판단).

# 7. 미검증

- 실제 claude·실제 ./experiment·학습·평가·모델·네트워크 호출(하지 않음), launchd 상시 실행, 실데이터·실제 실험 기록 형식과의 대조(합성 기록만), 여러 계보 동시 진행·주 경계 부하.
- 모델 정확도(누락·오탐) 변화 없음. 합성 시험 통과는 자율 루프 실제 작동 근거가 아니다.

# 8. 시험

- 개발 중: VS3 새 시험 4개 모듈 + dedupe·graph·code_sha·code_tree·register_race·policy_guards + supervisor·runner·graph·task_isolation·b5_*·job_state·policy·exec_boundary 관련 138개 통과(3.12).
- 전체(대상 a7db7ee, 이 문서 커밋은 문서만, `mkdir scratchpad/full-suite.lock` 12:09:19 획득 → 12:18:53 내가 만든 잠금만 rmdir, 저장소 루트에서 `python -m unittest discover -s tests -p "test_harness_*.py"`): Python 3.12(.venv) 512개 OK(270.8초), Python 3.9(/usr/bin/python3) 512개 OK(301.2초). 기존 496 + 새 16. 로그: scratchpad `vs3-full-312.log`·`vs3-full-39.log`.

# 9. 사용자 확인 필요

1. runner 오염원 (나)(VERIFIED LLM 작업은 오염원 아님)와 그 의미 변화(6절 7)를 받아들일지. 대안 (가)는 별도 승인 기록이 필요하다.
2. 문서 규칙을 `docs/` 아래 `.md`로 고정한 것이 맞는지(루트 README.md 등은 코드로 본다).
3. 6절 1의 `claude_job._prompt` 지시 추가와 ANALYZE 입력에 대조 config.plan을 어떻게 줄지(VS4 담당 파일).
4. 6절 3(실행 직전 대조를 코드 지문 기준으로 바꿀지)·6절 5(성공·인프라 실패 실험도 같은 조건 재제안 금지) 기본값.

# 10. 롤백

`git revert a7db7ee 5144dee 6d76b2f`(역순). 5144dee만 되돌리면 Supervisor는 declared.json을 그대로 등록하고 runner는 VERIFIED LLM 의존도 막는다. 6d76b2f를 되돌리면 논리 키 코드 자리가 tree 전체로 돌아간다(문서 커밋 뒤 같은 실험이 다시 등록됨). 합성 root 밖의 상태 파일은 바꾸지 않았다.

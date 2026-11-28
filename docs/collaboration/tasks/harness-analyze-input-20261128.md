task_id: harness-analyze-input-20261128
owner: Claude
status: ready_for_review (합성 종단 검증까지. 실제 claude 실행·실제 ./experiment 연결·활성화 아님)
base_sha: 3a3bc84
branch: claude/harness-analyze-input-20261128
goal: ANALYZE(task_type plan_gate.ANALYZE_TYPE) 프롬프트에 next_plan.json 형식과 대조 계획 위치를 알려 분석→다음 가설 고리가 실제 Claude에서도 PLAN_GATE를 통과할 수 있게 한다.

# 1. 문제와 원인

`claude_job._prompt`는 모든 작업에 일반 문구만 줬다. PLAN_GATE(`harness/plan_gate.py` docstring 2절)는 next_plan.json의 키(PLAN_KEYS만), 변수(experiment_parameter.value 하나), plan(대조 config.plan에서 그 값만 바꾼 것), 가설 문구만 Claude 몫이라는 규칙으로 검사하지만, Claude는 그 규칙과 대조 계획의 위치(in/ 아래 plan.json 사본)를 알 길이 없었다. 가짜 claude를 쓴 기존 종단 시험(test_harness_vs3_entry)은 정답 JSON을 시나리오에 미리 박아 이 간극을 가렸다.

# 2. 변경(최소)

| 파일 | 변경 | 함수 수 전/후 |
|---|---|---|
| harness/claude_job.py | 모듈 상수 `_PLAN_FORMAT`(plan_gate.NEXT_PLAN·PLAN_KEYS·VARIABLE·_FROZEN, experiment_exec.TEXT_KEYS에서 만든 형식 안내), `_prompt`가 contract를 받아 ANALYZE(task_type 일치 + outputs에 next_plan.json + inputs에 */plan.json 있음)일 때만 규칙 5로 덧붙임. execute의 호출 한 줄 | 6 → 6 |
| tests/harness_plan_gate_kit.py | `seed(src, hid, plan=None)`: 동결 plan.json 내용을 지정(기본 동작 그대로) | 7 → 7 |
| tests/test_harness_analyze_input.py | 신규 시험 4개 | 신규 ≤7 |

- 새 모듈·새 추상화 없음. 다른 task_type 프롬프트는 바이트 그대로(시험이 기존 문구 리터럴과 비교).
- 호출 깊이: supervisor.run 4(변경 전과 같음), claude_job.execute 3. `_prompt`는 말단(0). 새 함수 없음.
- 안내 문구: 키 목록·변수 경로·뺄 키(hypothesis_id, 설명 문구 4개, 하네스가 붙인 _FROZEN 4개)·대조 사본 경로를 상수에서 만들므로 plan_gate가 바뀌면 안내도 따라간다.
- 대조 사본은 record·result가 아니라 inputs의 `*/plan.json`(= 동결 plan.json, build_plan 결과 + _FROZEN)이다. config.plan = 그 파일에서 위 키를 뺀 것(plan_gate._derive·experiment_exec.build_plan 정의).

# 3. 시험(수정 전 실패 먼저)

- 수정 전(claude_job 변경 전) `python -m unittest tests.test_harness_analyze_input`: 종단 시험 ERROR(가짜 claude가 형식 설명을 못 찾아 다음 실험이 등록되지 않음 `[e2] = ... not enough values`), 프롬프트 시험 2개 FAIL.
- (a) AnalyzePromptTest: ANALYZE 프롬프트에 PLAN_KEYS 각 키·`experiment_parameter.value`·TEXT_KEYS·_FROZEN 키·in/artifacts/experiments/<eid>/plan.json(record·result 경로는 없음), 다른 유형(experiment·label_review·unknown_type)은 기존 문구와 정확히 같음.
- (b) AnalyzeEntryTest: `python -m harness.supervisor` 1회 실행. 가짜 claude는 시나리오에 정답을 갖지 않고 프롬프트 글에서 키 목록·변수·대조 사본 경로·뺄 키를 정규식으로 읽어 in/ plan.json으로 next_plan.json을 만든다 → PLAN_GATE 통과 → plan_gate_declared(experiment) → 다음 실험 등록·가짜 executor 실행·VERIFIED, declaration_rejected 없음, value 0.7.
- 변이(수정 후 코드를 일부러 고쳐 시험이 잡는지): M1 형식 설명 삭제 → 종단 ERROR + 프롬프트 FAIL. M2 뺄 키에서 _FROZEN 제거 → 종단 ERROR + 프롬프트 FAIL. M3 PLAN_KEYS 중 variable 누락 안내 → 종단 ERROR(프롬프트 시험은 통과: 키 하나 누락은 종단이 잡음). 변이는 원복했다.
- 전체 시험 결과는 마지막 절.

# 4. C(연결) 증거

합성 root에서 `python -m harness.supervisor --root … --claude-bin <가짜> --executors tests.harness_plan_gate_kit:EXECUTORS --source-root … --max-cycles 3 --poll 0` 1회. 재현: 시험 `AnalyzeEntryTest`(또는 `_entry` 헬퍼). 실행 로그 전문(프롬프트·next_plan.json·장부 줄)은 작업 중 임시 폴더 `…/scratchpad/analyze-entry-evidence.log`에 남겼고 핵심을 아래에 옮긴다.

```
returncode 0 / stdout: {"claude_runs": 1, "cycles": 3, "outcomes": ["done"], "python_runs": 5, "state": "RUNNING"}
장부: enqueued experiment → completed → plan_gate_declared misanalysis_general(depends_on 대조 실험) → enqueued → claude_job_picked
      → claude_run_started → completed(분석) → plan_gate_declared experiment(depends_on 분석) → enqueued → completed(다음 실험)
프롬프트 규칙 5: "- 키: hypothesis_id, hypothesis, change, variable, plan (이 키만, 다른 키 금지) … - 변수: experiment_parameter.value 하나만 …
  - plan 만드는 법: 대조 계획 사본 in/artifacts/experiments/<eid>/plan.json 을 읽어 키 hypothesis_id, hypothesis, change, success_criterion,
    failure_criterion, schema_version, threshold, independent, production_adopted 를 뺀 나머지를 그대로 옮기고, experiment_parameter의 value만 …"
next_plan.json(가짜 claude가 프롬프트만 보고 생성): {"hypothesis_id": "H-next", …, "variable": "experiment_parameter.value", "plan": {…"value": 0.7…}}
선언된 다음 실험 value: [0.7]
```

이것은 합성 연결 증거다. 실제 claude 실행·실제 ./experiment·모델 호출은 하지 않았다.

# 5. 한계·미검증

- 실제 claude(모델)가 이 안내를 읽고 올바른 next_plan.json을 쓰는지는 미검증이다. 가짜 claude는 안내 글을 정규식으로 읽을 뿐이라 "글이 사람·모델에게 충분히 명확한가"는 증명하지 못한다(글의 정확성·완전성만 시험).
- 시험의 동결 plan.json은 `build_plan(control) + plan_gate._FROZEN`으로 만든 것이다. 실제 ./experiment가 남기는 plan.json과의 일치는 코드 정의(experiment_record.prepare 주석)에 근거했고 실기록으로는 확인하지 않았다(실데이터 금지).
- 대조 계획 사본이 둘 이상이면(`*/plan.json` 입력 여러 개) 정렬 첫 번째를 안내한다. PLAN_GATE가 만드는 ANALYZE 계약은 하나뿐이다.
- 안내는 한국어 글이라 모델이 value를 위 조건과 다른 수로 정하는 선택은 Claude 몫이다(PLAN_GATE가 같은 수·2번째 변수를 거절).

# 6. 보류(운영 뒤 개선)

- 실제 claude 1회 실행으로 안내의 이해도 확인(별도 승인 필요, 이번 범위 밖).
- next_plan.json 예시 JSON을 프롬프트에 넣을지는 실제 실행 결과를 본 뒤 결정.

# 7. 사용자 확인 필요

없음(승인 범위 안의 프롬프트 안내 추가). 실제 claude 실행 승인은 별도.

# 8. 롤백

브랜치 커밋을 되돌리면 `_prompt`는 기존 4-인자 시그니처·일반 문구로 돌아간다(다른 파일 의존 없음, 장부·계약 형식 변경 없음).

# 9. 전체 시험 결과(저장소 루트, 잠금 절차 사용)

- 코드 커밋 b0418eb에서 `PYTHONDONTWRITEBYTECODE=1 …/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"`: 530 통과(304초).
- 같은 명령 `/usr/bin/python3`: 530 통과(342초). 분기점 대비 시험 +4(신규 파일). kill9 간헐 실패는 이번 두 번에서는 나오지 않았다(고치지 않음).

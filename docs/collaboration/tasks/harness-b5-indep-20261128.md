task_id: harness-b5-indep-20261128
owner: Claude
status: ready_for_review (체크포인트 정지: B5-5·B5-6 미착수, 묶음 끝 전체 시험 미실행)
base_sha: df6b78b
branch: claude/harness-b5-indep-20261128
goal: B5 독립 묶음(B5-3·B5-2·B5-7·B5-8)을 새 파일·비공통 파일만으로 구현하고 합성 시험·변이로 고정한다.
allowed_files: harness/budget.py, harness/eligibility.py, 새 harness/train_manifest.py·apply_train.py·experiment_exec.py, 새 tests/test_harness_b5_*.py·tests/harness_depth_kit.py, 형식 이전 시험 도우미 2개(아래), 이 문서
forbidden_files: dedupe·claude_job·sandbox·runner·safefs·graph·supervisor·queue와 그 시험(다른 담당 수정 중), 실데이터·라벨·봉인 자료

# 상태 구분

- 구현 완료·합성 검증 완료: B5-3, B5-2, B5-7, B5-8(어댑터만).
- 실환경 검증: 없음. 실제 claude·모델·네트워크·./experiment·학습·승격은 실행하지 않았다.
- 미완료: 호출부 연결(runner·claude_job·supervisor, 공통 파일이라 통합 뒤), **실제 ./experiment 연결: 미완료**, B5-5·B5-6(체크포인트 지시로 보류, 착수 안 함), 묶음 끝 전체 시험(지시로 미실행).
- 합성 시험 통과는 실제 작동·자율 루프 완료·모델 정확도(누락·오탐) 개선 근거가 아니다. 정확도 변화 없음.

# 단계별 커밋

| 단계 | 커밋 | 바꾼 파일 | 함수 수(전→후) |
|---|---|---|---|
| B5-3 budget.charge 깊이 펼침 | 9bbe392 | harness/budget.py, tests/harness_depth_kit.py(새), tests/test_harness_b5_budget_depth.py(새) | budget 3→4 |
| B5-2 manifest v2 부모 대조 | e26df65 | harness/eligibility.py, tests/test_harness_b5_manifest_parent.py(새), tests/test_harness_champion_support.py, tests/test_harness_eligibility_manifest.py | eligibility 6→6 |
| 깊이 도구 수정 | f35d92f | tests/harness_depth_kit.py(`from harness import x`를 놓쳐 낮게 재던 것) | — |
| B5-7 학습 적용기 | ce4e776 | harness/train_manifest.py(새), harness/apply_train.py(새), tests/test_harness_b5_apply_train.py(새) | 새 4, 새 1 |
| B5-8 실험 어댑터(합성) | 0a7a1da | harness/experiment_exec.py(새), tests/test_harness_b5_experiment_exec.py(새) | 새 3 |

새 시험 파일 함수 수: 4·5·5·7, 깊이 도구 2(모두 ≤7).

# 구조(AST, tests/harness_depth_kit.py)

- budget.charge 3→2(`charge → ledger.verify → _check_line`). 호출 지점 runner.main → drain → charge, supervisor.run → claude_job.execute → charge는 2+2=4로 한도 안(시험이 고정).
- eligibility.parent_check 3, champion.promote 3, apply_train.apply 4(진입점: 다른 함수 안에서 부르면 5가 되므로 통합 때 별도 프로세스 `python -m harness.apply_train <root> <task_key>`로 부른다), train_manifest.build 2, experiment_exec.run 2.
- df6b78b+이 브랜치에서 harness 공개 함수 중 깊이 4 초과 0개. 동적 호출(executor 표 등)은 정적으로 확정할 수 없어 세지 않았다.

# 단계별 내용과 결정

## B5-3 (동작 불변)
- usage를 거치지 않고 같은 검증을 charge 안에서 하고, 합계·꼬리 판정은 순수 함수 `_tally`로 나눴다.
- BUDGET_EXCEEDED 전이를 opstate.set_condition과 같은 단계(opstate.lock → load → 상태 파일 → root/ledger.jsonl 한 줄)로 펼쳤다. 상태 파일·장부·알림이 set_condition 경로와 바이트 단위로 같음을 시험으로 고정했다. 실행자 없음·깨진 상태 파일은 이전처럼 OpStateError.
- 결정 3(실행 시작 시 차감, 재개 중복 차감 금지) 관련: 기존 (kind, key) 멱등으로 같은 논리 실험 키는 한 번만 차감된다. 한도 도달 뒤 이미 차감한 키의 재개는 ok·already(초과 아님), 새 키는 거절. 장부 기록 뒤·꼬리 기록 전 실제 SIGKILL → 재시작 후 같은 키 already, 한도 유지. 꼬리 잘림·꼬리 파일 삭제로 사용량을 되돌리는 시도는 charge·usage 모두 BudgetError. 정지 상태 중에는 이미 차감한 키도 거절(시작을 허락하지 않음).

## B5-2
- MANIFEST_FORMAT v1→v2, 키 `start_weights_sha`. None이면 parent도 None, 값이 있으면 선언된 부모의 weights_sha와 정확히 같아야 한다(대문자·공백·40자 접두어·다른 모델·정수·목록 거절). 어긋나면 `manifest_parent_mismatch`, 자손도 거절. v1·키 없음은 `manifest_mismatch`(fail-closed).
- 부모를 생략하고 보류 계보에서 이어 학습한 모델의 승격 경로(b924753 결함 ②, 검사 쪽)를 닫았다. 정직하게 부모를 선언하면 기존대로 policy_withdrawn_hold.
- 기존 시험 도우미 변경(완화 아님, 형식 이전): add_model 기본 manifest에 부모 가중치 SHA(없으면 None)를 넣고, test_harness_eligibility_manifest가 직접 쓰는 manifest 2개에 `start_weights_sha: None`을 넣었다. 검사 기준·기대 사유는 바꾸지 않았다.

## B5-7
- manifest는 하네스가 만든다. 입력 경로 규칙(pre-b5 결정 7 미정 → 계약 필드·dedupe 논리 키를 바꾸지 않는 안을 기본값으로 택함): `parents/<모델 ID>/<파일>` 하나 = 학습 시작 가중치(그 입력 SHA = 그 모델 weights_sha), `silver/labels.json` = trainable_labels 형식 라벨 목록(label_id만 읽고 묶음은 Silver 장부에서). 등록 모델 가중치와 같은 SHA를 parents/ 밖에 두면 거절, silver/ 아래 다른 입력 거절, 모든 in/ 사본 SHA 재대조.
- out/에 executor가 쓴 manifest는 읽지 않는다. VERIFIED·training만. 적용 기록 + registry 동일 식별 멱등으로 등록 직후 SIGKILL 뒤에도 모델 1개. 적용 기록이 레지스트리에 없는 모델을 가리키면 거절.
- 정지 상태(HALTING) 중에는 반영하지 않는다(pre-b5 결정 9 미정 → 미뤄도 잃는 것이 없는 fail-closed 기본값). 승격은 하지 않는다.

## B5-8 (합성, 실제 연결 미완료)
- 실행 파일은 어댑터가 정한다(`<workdir>/experiment`), 계약 command는 `--` 뒤에만. 계획 JSON = 계약 `config.plan`(실행 조건, 논리 키 포함) + 설명 키 `hypothesis_id`·`description{hypothesis, change, success_criterion, failure_criterion}`(논리 키 제외). plan이 설명 키를 덮어쓰면 거절.
- 실행 직전 dedupe.verify_code(code_sha = workdir HEAD, 추적 파일 변경 없음).
- 결과 해석: 0+completed+result 해시 일치 = 완료, 1+failed = 결정적 실패, 128 초과+interrupted = 중단, 안내문으로 확인되는 1(잠금 사용 중)·2(계획 오류) = not_started. 그 밖(코드·상태 불일치, running, 폴더 밖 기록, 명령·가설 불일치, 안내문 없는 1, 신호 사망, 시간 초과) = 결과 불명 → 종류 interrupted(작업권을 남겨 결과 확인 대기). 완료 사본도 다시 대조.
- 임시 git 저장소의 가짜 experiment로만 시험했다.

### 첫 실험 후보 승인 때 검토할 최소 권한·실행 경로 초안 (미승인, 미구현)
1. 실행 위치: 기본 checkout 한 곳(단일 담당), sandbox 밖 신뢰 실행기. executor 표가 아니라 어댑터 고정 경로 `<저장소>/experiment`만.
2. 쓰기 허용: 저장소 `artifacts/experiments/`와 `artifacts/development-cycle/workspace.lock`, 작업 폴더 staging. 그 밖 저장소 쓰기·Gold·봉인 경로는 금지(가능하면 별도 sandbox 프로필로 강제할지 그때 결정).
3. 네트워크: 기본 금지. 실험 명령이 외부 AI를 부르면 기존 승인 범위·호출 제한을 따로 확인.
4. 직렬화: `./develop` 잠금과 하네스 작업권을 함께 잡는다. 잠금 사용 중(종료 코드 1 안내문)은 not_started.
5. 예산: runner에서 claim 뒤·실행 직전 `budget.charge(root, "experiment", 1, now, key=<논리 실험 키>)`. not_started만 취소 후보.
6. 결과 반영: record.json·result.json 사본만 outputs로. 결과 불명은 자동 재실행하지 않고 사람/검증 확인 뒤 반영. 다음 가설 생성(ANALYZE 입력 development_handoff.json)까지 실제로 확인해야 최종 완료(사용자 결정).

# 실제로 돌린 시험

- Python 3.12(.venv): tests.test_harness_b5_budget_depth·supervisor_budget·evidence_fixes·supervisor_halt·policy_guards·supervisor_ratelimit(28개 OK), eligibility·champion·silver·withdrawal 관련 28개 모듈(118개 OK), test_harness_b5_apply_train(3 OK), test_harness_b5_experiment_exec(4 OK).
- Python 3.9(/usr/bin/python3): budget 관련 6개 모듈(28 OK), b5_apply_train·b5_manifest_parent·b5_budget_depth(10 OK), b5_experiment_exec(4 OK).
- 전체 시험(`test_harness_*.py` 전부): **미실행**(체크포인트 지시). 통합 전 반드시 3.12·3.9 순차 실행.

# 변이 시험(scratchpad 복사본, 원본 미수정)

| 단계 | 변이 | 결과 |
|---|---|---|
| B5-3 | M1 key 멱등 제거, M2 `>`→`>=`, M3 꼬리 대조 제거, M4 정지 확인 제거, M5 펼친 전이 장부 필드 누락, M6 기존 조건 삭제, M7 깨진 상태 파일 덮어씀, M8 꼬리 전 한 줄 허용 제거, M9 기록 순서 뒤바꿈, M10 usage 경유(깊이 회귀) | 처음 8/10, M3·M7 생존 → 시험 보강(charge 경로 꼬리 잘림, 잠금 안 손상 경합) 뒤 10/10 |
| B5-2 | M11 비교 삭제, M12 None이면 건너뜀, M13 자기 SHA와 비교, M14 키 집합에서 제거, M15 v1 허용, M16 대소문자 무시, M17 부모 없으면 아무 값 허용 | 7/7 |
| B5-7 | M18 executor manifest 사용, M19 parent=None, M20 적용 기록 멱등 제거, M21 기록을 등록 전에, M22 사본 SHA 대조 제거, M23 부모 SHA 대조 제거, M24 선언 안 한 가중치 검사 제거, M25 파일의 batch_id 신뢰, M26 정지 확인 제거, M27 VERIFIED 확인 제거, M28 중복 라벨 허용, M29 부모 여럿 허용 | 처음 11/12, M25 생존 → 위조 batch_id 시험 추가 뒤 12/12 |
| B5-8 | M30 130을 실패로, M31 interrupted를 완료로, M32 상태 무시·코드만 신뢰, M33 code_sha 재대조 제거, M34 command를 `--` 앞에, M35 설명 키 덮어쓰기 허용, M36 기록 경로 범위 제거, M37 result 해시 제거, M38 결과 불명을 결정적으로, M39 시간 초과를 not_started로, M40 안내문 없이 not_started, M41 명령 불일치 무시 | 처음 8/12, M32·M36·M37·M40 생존 → 가짜 모드 추가(failed_with_result·quiet_fail·폴더 밖 완결 기록)·해석 단계 직접 시험 뒤 12/12 |

# 통합 뒤 필요(공통 파일, 이 브랜치에서 고치지 않음)

1. runner.drain: 실험 claim 뒤·executor 직전(verify_code·stage_inputs 뒤가 맞다: 그 전 실패는 실행 안 됨)에 `budget.charge(..., key=dedupe.logical_key 기반)`, 거절 시 작업권 반납·대기. 깊이 2+2=4 확인 필요(4차 수정 뒤 runner 깊이 재측정).
2. 예산 차감 취소(not_started 확인 시): budget.py에 취소 이벤트가 없다. 사용자 결정 3의 "객관적으로 미실행만 취소"를 구현하려면 장부 이벤트 하나 추가가 필요(설계 범위 확인 필요). 지금은 차감 시점을 사전 검사 뒤로 두면 대부분 불필요.
3. experiment_exec를 executor로 쓰려면 실행 경계 결정(위 초안)과 runner 쪽 ExperimentError → 실패 종류 연결(sandbox.ChildError와 같은 kind 규칙), dedupe 유형 등록은 불필요(experiment는 이미 CONDITION_TYPES).
4. apply_train 호출: Supervisor 회차 또는 적용기 진입점(apply_main)에서 VERIFIED training 작업마다 별도 프로세스로 호출. 학습 계약이 parents/·silver/ 입력 규칙을 쓰도록 PLAN_GATE/등록 쪽 연결(결정 7 확정 필요).
5. B5-1(supervisor 철회 복구 호출), B5-4, B5-5(claude_job 비전 차감), B5-6(claude_job route 이력), B5-9·10, B5-11.

# 미완료(체크포인트 정지)

- B5-5 구역 수 세기, B5-6 route_history.py: 사용자 조건부 승인(2026-11-28)을 받았으나 개발 전략 재검토 지시로 착수하지 않았다. 코드·시험 없음.
- 묶음 끝 전체 시험: 미실행.

# 한계·리스크

- manifest 대조는 계약 입력으로 선언된 것만 본다. 학습 코드가 inputs 밖(원본 경로·네트워크)에서 가중치·라벨을 읽는 것, 가중치 바이트가 같은 두 모델 구분은 못 한다.
- budget의 펼친 전이는 opstate 규칙을 복제한 것이다. opstate 전이 규칙을 바꾸면 함께 바꿔야 한다(동치 시험이 어긋남을 잡는다).
- apply_train은 VERIFIED 판정 뒤 등록 사이 out/ 변경 경합을 막지 않는다(out/은 하네스만 쓴다는 runner 전제).
- experiment_exec 시간 초과는 직접 자식만 죽인다(실제 ./experiment의 프로세스 그룹 잔류 가능 → 결과 불명 처리).
- 자동 재개 목록(claude_perm.AUTO_RESUME)·재실행 안전 목록(recovery.RERUN_SAFE_TYPES)은 비어 있음을 시험으로 고정했다(켜지 않음).

# 롤백

단계별 독립 커밋이라 `git revert <SHA>`로 되돌린다(역순 권장: 0a7a1da → ce4e776 → f35d92f → e26df65 → 9bbe392). e26df65는 시험 도우미 형식 이전을 같은 커밋에 포함하므로 함께 돌아간다. ce4e776은 e26df65의 v2 형식에 의존한다.

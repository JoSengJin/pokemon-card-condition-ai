task_id: harness-b5-indep-20261128
owner: Claude
status: ready_for_review (B5-5·B5-6 새 파일 구현·전체 시험 완료, 호출부 연결은 통합 뒤)
base_sha: df6b78b
branch: claude/harness-b5-indep-20261128
goal: B5 독립 묶음(B5-3·B5-2·B5-7·B5-8, 추가 배정 B5-5·B5-6)을 새 파일·비공통 파일만으로 구현하고 합성 시험·변이로 고정한다.
allowed_files: harness/budget.py, harness/eligibility.py, 새 harness/train_manifest.py·apply_train.py·experiment_exec.py·logical_zones.py·route_history.py, 새 tests/test_harness_b5_*.py·tests/harness_depth_kit.py, 형식 이전 시험 도우미 2개(아래), 이 문서
forbidden_files: dedupe·claude_job·sandbox·runner·safefs·graph·supervisor·queue와 그 시험(다른 담당 수정 중), 실데이터·라벨·봉인 자료

# 상태 구분

- 구현 완료·합성 검증 완료: B5-3, B5-2, B5-7, B5-8(어댑터만), B5-5(세는 함수만), B5-6(이력 읽기만).
- 실환경 검증: 없음. 실제 claude·모델·네트워크·./experiment·학습·승격은 실행하지 않았다.
- 미완료: 호출부 연결(runner·claude_job·supervisor·dedupe, 공통 파일이라 통합 뒤, **B5-5·B5-6도 연결 전이라 실행 경로에서는 아직 아무것도 하지 않는다**), **실제 ./experiment 연결: 미완료**.
- 합성 시험 통과는 실제 작동·자율 루프 완료·모델 정확도(누락·오탐) 개선 근거가 아니다. 정확도 변화 없음.

# 단계별 커밋

| 단계 | 커밋 | 바꾼 파일 | 함수 수(전→후) |
|---|---|---|---|
| B5-3 budget.charge 깊이 펼침 | 9bbe392 | harness/budget.py, tests/harness_depth_kit.py(새), tests/test_harness_b5_budget_depth.py(새) | budget 3→4 |
| B5-2 manifest v2 부모 대조 | e26df65 | harness/eligibility.py, tests/test_harness_b5_manifest_parent.py(새), tests/test_harness_champion_support.py, tests/test_harness_eligibility_manifest.py | eligibility 6→6 |
| 깊이 도구 수정 | f35d92f | tests/harness_depth_kit.py(`from harness import x`를 놓쳐 낮게 재던 것) | — |
| B5-7 학습 적용기 | ce4e776 | harness/train_manifest.py(새), harness/apply_train.py(새), tests/test_harness_b5_apply_train.py(새) | 새 4, 새 1 |
| B5-8 실험 어댑터(합성) | 0a7a1da | harness/experiment_exec.py(새), tests/test_harness_b5_experiment_exec.py(새) | 새 3 |
| B5-5 논리 구역 수 | e53e56f | harness/logical_zones.py(새), tests/test_harness_b5_logical_zones.py·b5_zone_budget.py(새) | 새 2 |
| B5-6 route 이력 | c82d4f7 | harness/route_history.py(새), tests/test_harness_b5_route_history.py(새) | 새 2 |

새 시험 파일 함수 수: 4·5·5·7, 깊이 도구 2, B5-5·6은 5·7·7(lambda 포함, 모두 ≤7). B5-5·6은 기존 파일을 고치지 않았다.

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

## B5-5 (세는 함수만, 연결 전)
결정: decisions-b5-b6-20261128.md "B5-5·B5-6 결정"(나안 조건부 승인).
- `logical_zones.count_logical_zones(task_dir, contract)`: 계약 입력 `candidates/selection.json`(이 구현에서 고정한 경로)의 작업 폴더 사본을 한 번 읽어 **읽은 바이트**의 SHA를 계약과 대조하고 구역 수를 센다. **실제 AI 사용량(호출·토큰·본 사진 수)이 아니다**(모듈 설명에 명시).
- 형식은 `{"selected": [...]}` 하나이며 항목은 `active_learning.select`의 selected 항목과 정확히 같다. 거절: 빈 목록, 모르는 키(최상위·항목), 중복 JSON 키, region_id 중복, (image_sha, zone) 중복(앞뒤 공백·대소문자 무시), 링크·FIFO·폴더·없는 사본, SHA 불일치, 입력 미선언.
- **select의 반환 전체는 거절한다(담당의 해석)**: 이 파일은 Claude가 읽는 입력인데 trace에는 선별 점수가, silver_queue·human_queue 소속에는 기대 라벨이 드러난다. 세지 않는 목록에 구역을 숨길 수도 있다. 후보 목록을 만드는 쪽은 selected만 저장해야 한다.
- 차감·멱등·잠금은 새로 만들지 않았다. 기존 budget.charge(key=task_key)를 시험으로 고정: 목록이 바뀌면 task_key가 달라 별도 차감, 같은 계약의 재개는 다음 주에도 재차감 없음, 8개 프로세스 동시 100구역 → 성공 3개·합 300(3회 반복), 같은 key 6개 동시 → 한 줄, 실제 SIGKILL 세 지점(장부 쓰기 전 / 장부 뒤·꼬리 전 / 꼬리 뒤·반환 전) 뒤 재시작에서 누락·중복 없음, 반쯤 쓴 장부 줄 → 모든 차감 거절.
- 연결(통합 뒤): claude_job.execute에서 needs_vision 작업의 Claude 실행 시작 직전에 `budget.charge(root, "vision_zone", count_logical_zones(task_dir, contract), now, key=task_key)`. stage_inputs 뒤여야 한다. LogicalZoneError·한도 거절이면 그 작업을 실행하지 않는다.

## B5-6 (이력 읽기만, 연결 전)
결정: 같은 절(가안 조건부 승인). route.py·route_escalate.py·routing_policy.json은 고치지 않았고 새 상향·중단 규칙, 사용량 지표, PLAN_GATE는 없다.
- `route_history.history(root, task_key, policy)`: 검사 유형(`quality_gate`·`reverification`·`promotion_judge`, 이 구현에서 정한 이름)이고 needs_llm=false이며 VERIFIED인 작업의 `out/route_cause.json`만 읽는다(읽은 바이트를 done.json manifest와 대조). 형식은 `{"target_task_key", "cause", "ruled_out"}` 정확히 셋. xhigh_justified 같은 추가 키는 거절한다.
- 귀속: 검사 작업이 대상에 의존 + 라우팅 작업이 검사 작업에 의존 + 대상이 needs_llm=true·같은 task_type이고 대상 inputs가 같은 SHA로 모두 들어 있음(마지막 조건은 **담당의 해석**: 같은 작업의 이전 시도). 아니면 이력으로 세지 않는다. 손상·위조·귀속 위반·서로 다른 두 시도의 판정에 함께 의존은 RouteHistoryError(이력을 비우면 낮은 모델로 돌아가 횟수가 초기화되므로 그 작업을 대기시킨다).
- 관문 실패만으로는 상향 없음: 상향 원인은 ruled_out이 data·checker·criteria 전부일 때만 넘기고 아니면 cause=None. 데이터·검사기·기준 문제는 검사기가 기존 no_escalate 원인을 적는다. 한 시도는 검사기가 여럿이어도 한 번만 세며, 하나라도 상향 불가 판정이면 올리지 않는다. 통과(cause=null)에서 연쇄를 끊는다.
- 기존 규칙 확인(합성 6회 연쇄, general_dev): sonnet/medium → sonnet/high → opus/high → pending(request_user=False, Xhigh 미사용), 이후 실패에도 pending 유지. 다시 읽어도 같은 결과.
- 연결(통합 뒤): claude_job의 `route.route(contract, [], ...)`의 `[]`를 이력으로 바꾸고, RouteHistoryError면 held, **decision["pending"]이면 held**. 검사 유형 3개를 dedupe.PLAIN_TYPES에 추가하고 검사 executor를 만들어야 이력이 생긴다.

## B5-5·B5-6: 기존 정책과 충돌·미검증(별도 보고)
1. **pending이 실행을 막지 않는다**: route()의 pending 결정에는 model·effort(opus/high)가 남고 claude_job.execute는 `model is None`만 본다. 지금은 이력이 `[]`라 pending이 생기지 않지만, 이력만 연결하면 최상위 모델이 계속 실행된다. 연결과 같은 커밋에서 pending 대기를 넣어야 "기존 중단 정책"이 실제로 멈춘다(시험은 route 결정 수준까지만 고정).
2. **중단 규칙의 우회 가능성**: 이력은 재시도 계약이 직전 시도의 검사 작업에 의존할 때만 생긴다. 의존을 선언하지 않거나 task_type·입력 경로·SHA를 바꾸면 기본 모델부터 다시다. PLAN_GATE가 없어 강제하지 않는다. 또 데이터·검사기 문제(no_escalate)는 기존 정책상 "상향 안 함"일 뿐 재시도를 멈추지 않는다. 재시도 계약을 자동으로 만드는 호출부는 지금 없다(선언은 declared.json).
3. **원인 분리는 검사기의 자기 선언이다**: ruled_out을 실제로 확인했는지는 이 모듈이 알 수 없다. 검사 executor를 만들 때 확인 근거를 검토해야 하며, 검사기가 Claude 산출물의 문구를 cause·ruled_out으로 옮기면 안 된다. 대상 inputs가 빈 계약이면 입력 귀속 조건은 아무것도 거르지 않는다.
4. Xhigh는 claude_job이 runtime(budget_remaining)을 주지 않고 이력이 xhigh_justified를 넘기지 않아 닫혀 있다. route() 자체의 Xhigh 경로는 그대로 있다.
5. **한 작업의 301구역 이상은 "그 작업만 거절"이 아니라 전체 정지**: 기존 budget 정책대로 BUDGET_EXCEEDED(사람 재승인)를 켠다. 바꾸지 않고 시험으로 고정했다. 그 작업만 거절하려면 별도 결정이 필요하다.
6. **논리 차감과 실제 사용의 차이**: 같은 task_key의 재개·새 세션·사람이 작업 상태를 지운 뒤 재실행은 AI가 다시 보더라도 추가 차감이 없다. 목록에 없는 입력 이미지를 Claude가 읽는 것도 막지 않는다(B군 이미지 접근 범위 미구현). charge의 key 멱등은 금액을 비교하지 않는다(금액이 SHA 고정 입력에서 나오는 것이 전제).
7. select는 region_id만 중복 검사하므로 같은 (image_sha, zone)을 결함 유형만 달리해 둘 담을 수 있고, 그런 목록은 여기서 통째로 거절된다(라벨 단위는 relabel·silver_gate와 같은 (image_sha, zone)). selected 항목의 part(ranked/random)·defect_type이 라벨러에게 주는 앵커링 영향은 검토하지 않았다.
8. 반쯤 쓴 예산 장부 줄은 이미 차감한 작업의 재개까지 막는다. 자동 복구는 없다(사람 확인).
9. 미검증: 실제 claude·비전 호출, claude_job 연결 뒤의 깊이·함수 수(claude_job은 6/7), B군 활성화(RUNNABLE=("A",)라 실제 차감 경로는 아직 쓰이지 않는다), 전원 장애 수준의 부분 쓰기.

# 실제로 돌린 시험

- Python 3.12(.venv): tests.test_harness_b5_budget_depth·supervisor_budget·evidence_fixes·supervisor_halt·policy_guards·supervisor_ratelimit(28개 OK), eligibility·champion·silver·withdrawal 관련 28개 모듈(118개 OK), test_harness_b5_apply_train(3 OK), test_harness_b5_experiment_exec(4 OK).
- Python 3.9(/usr/bin/python3): budget 관련 6개 모듈(28 OK), b5_apply_train·b5_manifest_parent·b5_budget_depth(10 OK), b5_experiment_exec(4 OK).
- B5-3~8 당시 전체 시험은 체크포인트 지시로 미실행.
- B5-5·6 새 시험 14개: 3.12·3.9 OK. 구조(AST): route_history.history 깊이 2, count_logical_zones 0 → 예정 호출 지점(supervisor.run → execute → 함수)에서 합 4 이내.
- **전체 시험(`tests/test_harness_*.py` 전부, 대상 c82d4f7, full-suite.lock 잠금 아래 순차): 3.12 444개 OK, 3.9 444개 OK.** 첫 시도는 discover `-t .` 옵션 오류(tests에 __init__.py 없음)로 시험 0개 실행·종료 1이었고, 모듈 이름 나열로 다시 돌렸다.

# 변이 시험(scratchpad 복사본, 원본 미수정)

| 단계 | 변이 | 결과 |
|---|---|---|
| B5-3 | M1 key 멱등 제거, M2 `>`→`>=`, M3 꼬리 대조 제거, M4 정지 확인 제거, M5 펼친 전이 장부 필드 누락, M6 기존 조건 삭제, M7 깨진 상태 파일 덮어씀, M8 꼬리 전 한 줄 허용 제거, M9 기록 순서 뒤바꿈, M10 usage 경유(깊이 회귀) | 처음 8/10, M3·M7 생존 → 시험 보강(charge 경로 꼬리 잘림, 잠금 안 손상 경합) 뒤 10/10 |
| B5-2 | M11 비교 삭제, M12 None이면 건너뜀, M13 자기 SHA와 비교, M14 키 집합에서 제거, M15 v1 허용, M16 대소문자 무시, M17 부모 없으면 아무 값 허용 | 7/7 |
| B5-7 | M18 executor manifest 사용, M19 parent=None, M20 적용 기록 멱등 제거, M21 기록을 등록 전에, M22 사본 SHA 대조 제거, M23 부모 SHA 대조 제거, M24 선언 안 한 가중치 검사 제거, M25 파일의 batch_id 신뢰, M26 정지 확인 제거, M27 VERIFIED 확인 제거, M28 중복 라벨 허용, M29 부모 여럿 허용 | 처음 11/12, M25 생존 → 위조 batch_id 시험 추가 뒤 12/12 |
| B5-8 | M30 130을 실패로, M31 interrupted를 완료로, M32 상태 무시·코드만 신뢰, M33 code_sha 재대조 제거, M34 command를 `--` 앞에, M35 설명 키 덮어쓰기 허용, M36 기록 경로 범위 제거, M37 result 해시 제거, M38 결과 불명을 결정적으로, M39 시간 초과를 not_started로, M40 안내문 없이 not_started, M41 명령 불일치 무시 | 처음 8/12, M32·M36·M37·M40 생존 → 가짜 모드 추가(failed_with_result·quiet_fail·폴더 밖 완결 기록)·해석 단계 직접 시험 뒤 12/12 |
| B5-5 | SHA 대조·(사진,구역) 중복·region_id 중복·정규화·중복 JSON 키·최상위/항목 추가 키·빈 목록·링크·일반 파일 검사·random_part 일치 제거(Z1~Z11) | 11/11(Z10은 FIFO에서 멈춰 시간 초과로 포착) |
| B5-6 | needs_llm·검사 유형·대상 의존·task_type·inputs 귀속, 검사기/대상 VERIFIED, 바이트 대조, 추가 키, ruled_out, 상향 불가 우선, 시도당 1회, 연쇄, 순서, 통과에서 끊기, 두 시도 거절, 손상 의존, 대상 needs_llm(R1~R18) | 처음 16/18, R6·R18 생존 → 시험 보강 뒤 18/18 |

# 통합 뒤 필요(공통 파일, 이 브랜치에서 고치지 않음)

1. runner.drain: 실험 claim 뒤·executor 직전(verify_code·stage_inputs 뒤가 맞다: 그 전 실패는 실행 안 됨)에 `budget.charge(..., key=dedupe.logical_key 기반)`, 거절 시 작업권 반납·대기. 깊이 2+2=4 확인 필요(4차 수정 뒤 runner 깊이 재측정).
2. 예산 차감 취소(not_started 확인 시): budget.py에 취소 이벤트가 없다. 사용자 결정 3의 "객관적으로 미실행만 취소"를 구현하려면 장부 이벤트 하나 추가가 필요(설계 범위 확인 필요). 지금은 차감 시점을 사전 검사 뒤로 두면 대부분 불필요.
3. experiment_exec를 executor로 쓰려면 실행 경계 결정(위 초안)과 runner 쪽 ExperimentError → 실패 종류 연결(sandbox.ChildError와 같은 kind 규칙), dedupe 유형 등록은 불필요(experiment는 이미 CONDITION_TYPES).
4. apply_train 호출: Supervisor 회차 또는 적용기 진입점(apply_main)에서 VERIFIED training 작업마다 별도 프로세스로 호출. 학습 계약이 parents/·silver/ 입력 규칙을 쓰도록 PLAN_GATE/등록 쪽 연결(결정 7 확정 필요).
5. B5-1(supervisor 철회 복구 호출), B5-4, B5-5(claude_job 비전 차감, 위 B5-5 연결 항목), B5-6(claude_job route 이력·pending 대기, dedupe 검사 유형·검사 executor, 위 B5-6 연결 항목), B5-9·10, B5-11.

# 미완료

- 위 "통합 뒤 필요"의 호출부 연결 전부. B5-5·B5-6은 함수만 있고 호출하는 곳이 없다.
- 합성 시험 통과는 실제 Claude 실행 성공이나 모델 정확도(누락·오탐) 개선 근거가 아니다. 정확도 변화 없음.

# 한계·리스크

- manifest 대조는 계약 입력으로 선언된 것만 본다. 학습 코드가 inputs 밖(원본 경로·네트워크)에서 가중치·라벨을 읽는 것, 가중치 바이트가 같은 두 모델 구분은 못 한다.
- budget의 펼친 전이는 opstate 규칙을 복제한 것이다. opstate 전이 규칙을 바꾸면 함께 바꿔야 한다(동치 시험이 어긋남을 잡는다).
- apply_train은 VERIFIED 판정 뒤 등록 사이 out/ 변경 경합을 막지 않는다(out/은 하네스만 쓴다는 runner 전제).
- experiment_exec 시간 초과는 직접 자식만 죽인다(실제 ./experiment의 프로세스 그룹 잔류 가능 → 결과 불명 처리).
- 자동 재개 목록(claude_perm.AUTO_RESUME)·재실행 안전 목록(recovery.RERUN_SAFE_TYPES)은 비어 있음을 시험으로 고정했다(켜지 않음).

# 롤백

단계별 독립 커밋이라 `git revert <SHA>`로 되돌린다(역순 권장: c82d4f7 → e53e56f → 0a7a1da → ce4e776 → f35d92f → e26df65 → 9bbe392). e26df65는 시험 도우미 형식 이전을 같은 커밋에 포함하므로 함께 돌아간다. ce4e776은 e26df65의 v2 형식에 의존한다.

task_id: harness-vs5-apply-20261128
owner: Claude
status: ready_for_review (B5-7 연결·B5-10 연결 합성 종단 검증까지. B5-9 미구현. 실제 학습·평가·승격·claude 연결 아님)
base_sha: 3a3bc84
branch: claude/harness-vs5-apply-20261128
goal: VS5 — VERIFIED 학습 작업 → 적용기(별도 프로세스) 모델 등록 → 평가 채점 → 승격 **판정 기록**을 Supervisor 실제 진입점에 연결(호출부만, 새 정책 없음)
allowed_files: harness/apply_main.py(새), harness/apply_promote.py(새), harness/supervisor.py(+30/-3), 새 tests/harness_vs5_*.py·test_harness_vs5_*.py, 이 문서
not_touched: runner.py·dedupe.py·claude_job.py·budget.py·queue.py, 자동 재개 목록·재실행 안전 목록(빈 상태 유지), 실데이터·라벨·봉인 자료

# 1. 메인 기본값(사용자 변경 가능)

미결 결정은 기능 확대 없는 보수안을 메인이 기본값으로 정했다. 사용자가 다르게 정하면 바꾼다.

| 결정 | 기본값 | 근거 | 구현 위치 |
|---|---|---|---|
| B5 결정 7 (학습 시작 가중치 표시) | (나) 학습 계약만 inputs 경로 규칙 `parents/<model_id>/<파일>`로 표시. dedupe 논리 키·계약 필드 변경 없음 | `input_roles`는 신뢰할 수 없는 표시이고 (가)는 `dedupe.logical_key`(공통) 수정이 필요 | 이미 B5-7(`train_manifest.parent_of`)에 있음. 이번에는 연결만 |
| B5 결정 9 (정지 중 반영) | (나) BUDGET_EXCEEDED·USER_STOPPED(및 INTEGRITY_HALT·DONE) 중에는 모든 반영(모델 등록·판정 기록) 정지 | 미뤄도 잃는 것이 없다(재개 뒤 다시 적용). HARNESS_RULES "정지 중 시작 안 함"의 보수적 해석 | Supervisor는 정지 상태 회차를 일찍 끝내 적용기를 안 부른다 + `apply_train.apply`·`apply_promote.apply`가 각자 다시 확인(회차 중 정지) |
| B5 결정 8 (`seal_cycle`) | 합성 ID만. 이번 범위는 승격 **실행**이 없어 `seal_cycle`도 승격 예산 차감도 쓰지 않는다 | 봉인 Gold 미승인 | — (미사용) |
| B5 결정 5(나)·6(나) | **구현하지 않음.** (5(나) 이력 `cause`를 계획 관문이 올림, 6(나) 최소 PLAN_GATE 확대) | 기능 확대 소지 | VS3·VS4에서 이미 다룬 범위 밖 |

# 2. 구현 전 확인 사항 (코드 근거, base 3a3bc84)

- 호출 지점 0건이던 것: `registry.register`·`apply_train.apply`(모듈 하단 `__main__`만 있었다), `promotion.evaluate`·`scoring.report`(시험만). 이번에 Supervisor → 적용기 경로로 연결했다.
- 깊이 제약: `apply_train.apply` 4, `apply_promote.apply` 4(`promotion.evaluate` 3 + 1). 어떤 함수 안에서 불러도 5라서, **반복은 `apply_main.py`의 `__main__` 블록**(함수가 아니라 깊이에 더하지 않음, apply_train의 기존 선례)에서 하고 Supervisor는 이를 별도 프로세스로 부른다(`_python`과 같은 방식). `supervisor.run`은 최장 4 유지(`_apply → apply_main.pending → states.facts → cas.sha_file`).
- `graph.register_missing`은 의존 선언을 의존 작업이 VERIFIED가 된 뒤에야 등록한다(설계). 그래서 평가 작업(학습에 의존)은 학습이 끝난 **다음 회차**에 등록·실행된다. Supervisor 한 번 실행에 **2회차**가 필요하다.
- 평가 executor는 harness에 없다(합성 시험의 가짜뿐). 평가 작업의 `rows.json`(구역 행: id·card_group·eval_tier·stratum·truth·pred_a·pred_b)을 만드는 실제 실행기는 미구현이다.
- Silver·능동 학습·감사(B5-9)는 아래 4절.

# 3. 구현

## 3-1. 흐름(Supervisor 회차 안)

declared.json(사람이 쓴 학습·평가 계약) → register_missing → runner(별도 프로세스, sandbox)가 학습·평가 실행 → **`supervisor._apply`**: `apply_main.pending(root)`(적용 기록이 없는 VERIFIED 학습·평가만, 읽기만)이 비어 있지 않으면 `python -m harness.apply_main <root>`를 별도 프로세스로 실행 → 학습 먼저 `apply_train.apply`(모델 등록, Challenger) → 평가 `apply_promote.apply`(채점·판정 기록).

## 3-2. 평가 계약(승격 판정 입력, 새 형식이 아니라 기존 `evaluation` 유형의 config 사용)

`run_conditions.config = {"promotion": {noise_rate, direction_min_fraction, min_defect_cards, min_valid_fraction[, replicates, trials, seed, delta]}, "candidate_of": <학습 작업 key>}`, `depends_on`에 그 학습 작업, `outputs`에 `rows.json`. 사전 등록 수치가 계약 config라 논리 키(SHA)에 묶인다(결과를 본 뒤 바꿀 수 없음, 기본값 없음). 후보 모델 = 그 학습 작업의 적용 기록이 가리키는 모델(적용 전이면 `candidate_not_applied` 대기).

## 3-3. 결과물

- 모델: `models/registry.jsonl`에 Challenger 1건(`train_applied/<key>.json` 기록으로 멱등).
- 판정: `promotion/verdicts/<평가 key>.json`(verdict·reasons·`promoted: false`·평가 결과 전체: 누락률·오탐률·분모·부트스트랩·민감도·보류 상한) + 장부 `promotion_verdict` 한 줄 + Supervisor 장부 `apply_drain` 줄. **champion 포인터·승격 예산·봉인 평가는 건드리지 않는다**(시험이 `champion.promote` 호출 금지(mock)와 `champion.read_current` 없음을 확인, C 로그가 `models/champion.json` 없음을 확인).

## 3-4. 실패 처리

- 정지 상태: 회차를 일찍 끝내 적용기를 부르지 않고, 적용기도 `halted:<상태>`로 거절(반영 0).
- 적용기 비정상 종료·시간 초과(1800초, 임시 기본값)·출력 불명(= 등록 장부 손상 등 무결성 오류): `RuntimeError` → Supervisor의 기존 except가 INTEGRITY_HALT(fail-closed, 사람 확인).
- 영구 거절(계약 형식 오류·입력 사본 불일치·사전 등록 수치 오류·봉인 행 등): 그 작업만 반영 안 함, `graph.note_rejected`로 같은 사유 한 번만 장부·알림. 대기(`candidate_not_applied`, 정지)는 기록하지 않는다.

# 4. 이번에 못 한 것 / 사용자 확인 필요

## 4-1. B5-9(Silver·능동 학습·감사) — 구현하지 않음(호출부만 연결하라는 범위 안에서 연결할 입력이 없다)

| 대상 | 연결하려면 필요한 입력 | 지금 상태(근거) | 필요한 결정 |
|---|---|---|---|
| `silver_gate.judge_candidates` | 승인된 정책(`silver_policy.approve`는 **사람 Gold 보정 대조**가 필요), `protected`(봉인·보정 그룹 목록, Gold 보호 미승인), 주입 검증 함수 `verifiers`(작업 산출물로 넘길 수 없는 호출 가능 객체), 후보 파일을 쓰는 Claude B군 작업 | `claude_perm.RUNNABLE = ("A",)`라 B군은 실행 불가. protected·정책은 실데이터·사람 라벨이 필요(합성 불가능하지 않으나 그 목록을 만드는 쪽이 없다) | Gold 보호 승인, B군 활성화, 정책 승인 절차 |
| `active_learning.select` | 후보 목록(모델 점수·기대 라벨 포함 = 사진 분석 결과), protected | 후보를 만드는 실행기 없음. 결과(큐)를 `relabel.request_*`로 넘기는 규칙도 없음 | 같음 |
| `audit.plan_audit`·`record_verdicts` | 감사 표본의 **사람 판정**(사람만 판정) | 합성 판정만 가능 | 사람 라벨 사용 승인 |

→ 합성 입력만으로 호출부를 만들면 실제 입력 경로 없이 "연결됨"을 주장하게 된다. 입력 출처가 정해지면 `apply_main`의 `_kind`에 유형 하나와 `apply_*` 새 파일을 같은 방식으로 추가할 수 있다(적용기는 별도 프로세스, 진입점 깊이 ≤4).

## 4-2. 사용자 확인 필요

1. 위 1절 기본값 두 개(결정 7 (나), 결정 9 (나))를 그대로 둘지.
2. **학습 시작 가중치(`parents/<model_id>/...`) 입력을 쓰려면 그 파일이 `--source-root`(원본 폴더)에 있어야 한다**(계약 입력은 원본에서 복사·SHA 대조). 레지스트리 CAS(`root/cas`)의 모델 가중치를 원본으로 꺼내는 경로가 없다. 부모를 이은 두 번째 학습의 자동 연결은 이 경로(예: 사람이 가중치를 원본에 놓기, 또는 CAS 입력 허용)를 정해야 한다. 기능 확대 소지라 구현하지 않았다. 부모 없는 학습(처음부터)은 연결됐다.
3. 사전 등록 수치(`noise_rate` 등 4개)는 평가 계약을 쓰는 사람이 정한다. D-5/D-6 승인 수치가 정해지면 그 값을 계약에 넣어야 한다(이번 합성 값은 시험용).

# 5. 커밋

| 커밋 | 내용 | 함수 수(전→후, lambda 포함) |
|---|---|---|
| 8e42099 | apply_main·apply_promote 새 파일, supervisor `_apply`+호출 한 곳, 시험·도구 | apply_main 2(함수 2: `_kind`·`pending`), apply_promote 2(`_config`·`apply`), supervisor 4→5, kit 5, run 5, 시험 5·3 |
| (다음) | 승격 함수 호출 금지 시험 보강 + supervisor 설명 | — |

공통 파일 diff 줄 수: `harness/supervisor.py` +30/−3. `runner.py`·`dedupe.py` 변경 없음(`PLAIN_TYPES`도 변경 없음: 학습·평가는 기존 CONDITION_TYPES).

# 6. 시험

## 6-1. 수정 전 실패

적용기 새 파일 뒤·supervisor 연결 전에 `tests.test_harness_vs5_entry`를 먼저 실행했다: 학습만 VERIFIED이고 모델 등록·판정이 없어(`apply_drain`·`promotion_verdict` 장부 줄 없음) 3개 중 2개 실패(초기 기대 구조 시험은 함수 수 10으로도 실패해 kit을 둘로 나눴다). 새 모듈 시험(`test_harness_vs5_apply`)은 모듈 없음으로 전부 실패 후 구현.

## 6-2. 합성 시험(수정 후)

| 시험 | 내용 |
|---|---|
| test_verdict_is_recorded_once_after_the_candidate_is_applied_and_nothing_is_promoted | 적용 전 대기(기록·장부 0), 적용 뒤 판정 1줄, 재적용 already, 승격 함수 호출 금지(mock), 포인터 없음, Challenger 유지, 분모 기록 |
| test_verdict_can_be_a_rejection_and_a_repeated_abstain_hack_is_still_rejected | 정상 구역 전부 보류로 누락을 줄이는 후보 = 미달(abstain_cap 사유) |
| test_bad_contract_bad_rows_or_halted_state_record_nothing | 후보 선언 없음·의존 없음·수치 부족·모르는 키·봉인 행 거절(기록 0), USER_STOPPED 중 학습·판정 모두 `halted`, 모델·장부 0 |
| test_a_crash_between_the_record_and_the_ledger_line_is_repaired_without_a_second_line | 기록 후 장부 줄 전 장애 → 다음 적용이 줄만 보충, 줄은 하나 |
| test_pending_lists_training_before_evaluation_and_drops_applied_ones | 순서, 적용 후 목록 비움, 재실행 무변화 |
| test_first_cycle_runs_training_then_registers_then_judges_without_promoting (진입점) | 아래 C 증거 |
| test_stopped_state_blocks_every_apply_and_a_broken_registry_halts_the_supervisor (진입점) | USER_STOPPED = 모델 디렉터리 생성 0·`apply_drain` 0, 해제 뒤 등록 장부 손상 = INTEGRITY_HALT·판정 0 |
| test_structure_function_counts_and_call_depth | supervisor.run 4, apply_promote.apply 4, apply_main.pending 2, apply_train.apply 4, 새·변경 파일 함수 ≤7 |

## 6-3. 변이 시험(scratchpad `vs5-mut/mutate.py`, git archive 복사본, 원본 미수정)

| 변이 | 결과 |
|---|---|
| M1 Supervisor가 적용기를 부르지 않음 / M3 판정기 정지 확인 제거 / M4 후보 의존 확인 제거 / M5 후보 미적용에도 판정 / M6 장부 줄 중복 확인 제거 / M7 평가를 학습보다 먼저 / M9 적용 기록 있어도 다시 대상 / M11 학습 적용기 정지 확인 제거 | 8/8 잡힘 |
| M2 판정 뒤 `champion.promote` 호출 | 처음 생존(승격이 적격성에서 거절돼 효과가 안 보임) → mock 시험 보강 뒤 잡힘 |
| M8 적용기 실패 시 빈 결과로 계속 | 처음 생존(가짜 변이가 우연히 TypeError → HALT) → 변이를 `return []`로 바꿔 잡힘 확인 |
| M10 필수 수치 확인 제거 | 동치 변이: `promotion.evaluate`가 같은 입력을 TypeError로 거절해 결과가 같다(사유 이름만 다르다). 검사는 사유를 분명히 하려는 중복이라 남김 |

## 6-4. 전체 시험

마지막 절(10)에 기록.

# 7. C 증거 (합성 root, 연결 증거이며 실환경·활성화 아님)

명령(한 번 실행, 2회차, 사용자 입력 없음): `python -m harness.supervisor --root <합성 root> --executors tests.harness_vs5_kit:EXECUTORS --source-root <합성 git 원본> --max-cycles 2 --poll 0`, 실제 sandbox-exec. 사람이 한 일은 학습·평가 계약 2개를 declared.json에 쓴 것뿐(실행 전). 원본 로그: scratchpad `vs5-c-evidence/c-evidence.log`(스크립트 `run_c.py`, 이 저장소 HEAD 8e42099에서 실행).

종료 코드 0, 최종 상태 RUNNING, `python_runs 4`(두 회차 × 작업 1개 + 빈 확인), Claude 실행 0. 장부(root/ledger.jsonl):

```
0 enqueued   training            ← declared.json → graph.register_missing (평가는 의존이라 다음 회차에 등록)
1 claimed / 2 completed          ← runner(sandbox) 가짜 학습 executor
3 python_drain executed=1
4 apply_drain [train ok model_id=1f463ea2…]     ← supervisor._apply → apply_main(별도 프로세스) → apply_train.apply
5 enqueued   evaluation          ← 2회차: 학습 VERIFIED 뒤 평가 등록
6 claimed / 7 completed / 8 python_drain executed=1
9 promotion_verdict candidate_of=b1589655… model_id=1f463ea2… verdict=통과 promoted=false gold_n=400
10 apply_drain [promote ok 통과]
```

판정 기록: `promotion/verdicts/7eb48796….json` = 통과, 기준 모델 누락 80/200=0.4, 후보 20/200=0.1, 후보 오탐 20/200=0.1, `promoted: false`. `models/champion.json` 없음(승격 실행 0). 다시 한 번 실행하면 새 줄 0(시험).
이 숫자는 합성 구역 행에서 나온 것이며 모델 성능이 아니다.

# 8. 한계·리스크

1. 실제 학습·평가 executor가 없다. 합성 가짜 executor로만 경로를 확인했다. `rows.json`을 만드는 실제 평가 실행기(사진 추론 포함)가 없다.
2. 판정은 학습 데이터와 평가 행의 카드 그룹 겹침(평가 독립성)을 다시 확인하지 않는다. Silver 입력 단계의 `protected` 검사에 맡긴다(그 단계도 호출부가 없다: 4-1). 평가 행 안의 eval_tier 사이 겹침과 sealed 행은 `promotion.evaluate`가 막는다.
3. 판정은 모델 적격성(eligibility·감사 완료)을 확인하지 않는다. 승격 실행 때 `champion.promote`가 한다(미승인).
4. 영구 거절된 작업은 회차마다 적용기 프로세스가 다시 뜬다(알림은 한 번). 거절 기록으로 건너뛰는 개선은 보류.
5. `apply_drain` 줄은 적용기 프로세스가 끝난 뒤에 쓴다. 적용기가 모델을 등록한 뒤 이 줄 전에 Supervisor가 죽으면 그 회차의 줄이 빠진다(등록·판정 자체의 기록은 레지스트리·`promotion_verdict` 줄로 남는다).
6. 한도 상태(RATE_LIMITED)에서도 적용기는 돈다(Python 작업과 같은 취급: Claude 한도와 무관). 정지 상태만 막는다.
7. 적용기 총 시간 1800초는 임시 기본값이다.

# 9. 미검증

- 실제 claude·모델·학습·평가·승격·네트워크 호출(하지 않음), launchd 상시 실행, 실데이터·사람 라벨·봉인 자료.
- 모델 정확도(누락·오탐) 변화 없음. 합성 시험 통과는 자율 루프 실제 작동·정확도 개선 근거가 아니다.

# 10. 전체 시험

대상 11839d5 이후 문서 정정 커밋(코드 변경 없음), 저장소 루트에서 `PYTHONDONTWRITEBYTECODE=1 <python> -m unittest discover -s tests -p "test_harness_*.py"`, full-suite.lock 잠금 아래 순차(내가 만든 잠금만 rmdir):
- Python 3.12(.venv): 534개 OK(306.6초). 3.9(/usr/bin/python3): 534개 OK(358.1초). 간헐 실패 test_kill9_while_waiting_then_restart_resumes는 이번 실행에서 발생하지 않았다.
- 로그: scratchpad `vs5-c-evidence/full-312.log`·`full-39.log`.

# 11. 롤백

`git revert <커밋>`(역순). 새 파일 삭제와 supervisor 한 함수·호출 한 곳 복원뿐이다. 이미 만들어진 `models/`·`promotion/` 기록은 합성 root뿐이다.

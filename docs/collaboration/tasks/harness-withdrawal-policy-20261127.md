# 하네스 — Silver 정책 철회·승격 차단·복원 일관성 최소 구현 (2026-11-27)

```text
task_id: harness-withdrawal-policy-20261127
owner: Claude (하위 에이전트, 구현·시험. 독립 검증은 메인이 따로 수행)
status: ready_for_review
base_sha: c249cac7e04b5f4e6984b85769630ed81c404db0
branch: claude/harness-withdrawal-policy-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: 사용자 조건부 승인(2026-11-27, B+D 합의안 + 최종 결정 ①~⑤·코드 보완 1~5)의 최소 구현을 합성 시험으로 통과한다.
  승격·복원·철회가 같은 적격성 계산과 같은 잠금 순서를 쓰고, 호출자 감사 상태를 믿지 않으며, 철회 도중 어디서 죽어도
  장부만으로 같은 최종 상태에 도달하고, 미완료 철회 중에도 영향 모델 승격이 막힌다.
allowed_files: harness/ 중 아래 금지 목록 밖(이번에 바꾼 것: audit, audit_rate, champion, gate, pointer, registry, silver_policy, lineage(삭제),
  eligibility(신규), withdrawal(신규)), tests/test_harness_{silver,champion,eligibility,withdrawal}_*.py, DESIGN.md 5-4·5-6·8절, DECISIONS.md,
  이 문서, 5·7단계 task 문서
forbidden_files: harness/{supervisor,opstate,ratelimit,claude_run,claude_job,budget,unlock,runner,queue,route*,gold_*}.py와 그 시험,
  scoring·promotion 모듈, card_condition/**, tools/**, AGENTS.md, docs/agent/**, artifacts/**, data/**, 라벨·사진·봉인 자료·비밀 설정
contract: stdlib만, Python 3.9+. 새 DB·인프라·통계 임계값 없음. D-3 값(오류율 상한 10%, 감사 초기 10%·최저 2% 제안값, 0% 금지) 불변.
  호출자: champion.promote(root, now, model_id) — audit_status 인자 제거. withdrawal.withdraw(root, now, policy_id=None, reason=None, batches=None).
  eligibility.parent_check(root, model_id). champion.set_dev_baseline(root, now, model_id, basis).
structure: 파일당 함수 정의 ≤7(메서드·중첩·lambda 포함), harness 공개 함수 호출 깊이 ≤4(ast 재측정, 아래 표)
checks: 아래 "실행 근거"
experiment: 없음. 합성 시험이며 실제 Silver 품질·묶음 간 오류 상관·모델 성능의 근거가 아니다.
handoff: 이 문서
```

## 정본과 해석 기준

정본은 사용자 문장인 B+D 합의안과 최종 결정이다(최종 결정이 우선). 요지는 [DECISIONS.md](../plans/autonomous-harness-20261127/DECISIONS.md) 1절, 설계 반영은 DESIGN 5-4·5-6·8절.

**철회 사유 해석(이 구현이 따르는 기준):** 오염·위조가 **확인됐는데 범위를 특정할 수 없으면** 합의안 5절 표대로 정책 전체 계보를 무효화한다.
**오류 자체나 범위가 미확인이면 보류만** 한다. 그래서 `withdrawal.withdraw`의 사유(`eligibility.REASONS`)는 다음처럼 처리한다.

| 사유 코드 | batches | 처리 |
|---|---|---|
| `batch_label_error` (특정 묶음 라벨 오류, 감사 실패의 자동 철회도 이것) | 지정 | 지정 묶음 계보 무효, 같은 정책의 나머지 묶음 계보 보류 |
| `batch_label_error` | 없음 | 보류만(범위 미확인) |
| `contamination` (출처 위조·데이터 오염) | 지정 | 지정 묶음 계보 무효, 나머지 보류 |
| `contamination` | 없음 | 정책 전체 계보 무효(확인됐으나 범위 특정 불가) |
| `systematic_error` (정책 전반의 체계적 오류) | 무시 | 정책 전체 계보 무효 |
| `scope_change`·`criteria_change`·`unclear`, 목록 밖 값·사유 없음(→ `unclear`로 기록, 원문은 `given`) | 무시 | 보류만(신규 사용·승격 차단) |

- 의미 변화 없는 문구 수정은 철회 사유가 아니다(철회·재감사를 요구하지 않는다, 새 승인 절차 없음). 정책 기록에 문구가 없으므로 문구 수정으로 바뀌는 상태도 없다.
- 장부 해시 불일치는 사유가 아니라 기존 무결성 정지다(`silver_store.StoreError`·`registry.RegistryError`가 그대로 나간다). 라벨 오류 증거와 섞지 않는다.
- 정책 전반 오류를 에이전트가 분석해 사유·범위를 정하는 자동화는 4단계 몫이다. 이번에는 철회 호출이 사유·범위를 받는 것까지만 한다.
- 같은 정책에 나중에 더 강한 사유를 주면(예: `unclear` 뒤 `contamination` 확정) 새 기록으로 무효 범위가 늘어난다. 약한 사유로 다시 철회해도 무효·보류는 풀리지 않는다.
- **자동 재적격 경로는 없다.** 보류는 철회 정책의 묶음을 계보가 쓴 동안 계속된다. 새 판본 승인·새 라벨 생성·이름/설정 변경 재등록·Baseline 지정·사용자 승인·AI 합의 어느 것도 보류를 풀지 않는다.
  철회 구역 Silver 재생성 기능과 라벨 ID 변경은 하지 않았고(기존 중복 거절 유지), "영구 금지"로 문서에 확정하지도 않았다.

## 최소 학습 manifest 형식 (`eligibility.MANIFEST_FORMAT`)

`data_manifest_sha`가 가리키는 CAS 보관본(`root/cas`)의 JSON. 키는 정확히 셋이다(그 밖의 키는 거절).

```json
{"format": "harness-train-manifest-v1", "silver_batches": ["b1", "b2"], "silver_label_ids": ["<label_id>", "..."]}
```

- `silver_batches`: 모델이 등록 때 선언한 `silver_batches`(정렬·중복 없는 목록)와 정확히 같아야 한다.
- `silver_label_ids`: 학습에 쓴 Silver 장부의 라벨 ID(문자열, 중복 없음). 모두 Silver 장부에 있어야 하고, 각 라벨의 묶음은 선언한 묶음 안이어야 한다
  (선언한 묶음 중 라벨을 안 쓴 묶음은 허용: 더 막는 쪽). 저장 당시 등급이 Pending인 라벨이 있으면 `manifest_pending_labels`(보류).
- CAS에 없거나 해시가 이름과 다르면 `manifest_missing`, JSON이 아니거나 위 조건을 어기면 `manifest_mismatch`. 승격 대상뿐 아니라 모든 조상을 검사한다.
- Silver 묶음이 없는 초기 모델도 같은 형식(`silver_batches: []`, `silver_label_ids: []`)이 필요하다.
- **실제 학습이 이 manifest를 만드는 일은 4단계(자율 루프)다.** 이번에는 대조만 구현했다.
- **한계:** manifest가 선언하지 않은 부모 가중치·라벨을 실제 학습이 쓴 경우는 잡지 못한다(선언 자체를 믿는 경계).

## 결정 항목별 구현

| 결정·보완 | 구현 (파일 :: 함수) |
|---|---|
| 1 같은 적격성 계산·같은 잠금 순서 | `eligibility.model_reason`(무효 → 파생 무효 → 철회 보류 → manifest → 감사 대기)을 `champion.promote`·`champion.restore_locked`·`withdrawal._conditional`·`eligibility.parent_check`가 쓴다. 넷 다 `silver_store.lock → registry.lock` |
| 1 audit_status 불신 | `champion.promote(root, now, model_id)`: 인자 제거(넘기면 TypeError). Silver 장부를 잠금 안에서 직접 읽는다. `gate.check`는 구조 조건만(`gate.audit_reason` 제거). `audit.audit_status`는 조회용 |
| 2 철회 중단 복구 함수 하나 | `withdrawal.withdraw`(policy_id 없이 부르면 복구만): 시작 기록 → 장부에서 무효 묶음 재계산 → 한 `invalidated` 이벤트 → 복원/Champion 없음 → 조건부 기록. 모든 단계가 재계산이라 같은 호출로 이어간다 |
| 2 실패만 있고 철회 기록이 없을 때도 차단 | `silver_policy.fold`가 `audit_completed(failed)`를 철회로 접고, `eligibility.silver_facts`가 그 묶음을 무효 묶음으로 본다(뒤에 덧붙인 완료 줄로 지워지지 않음) |
| 2 중복 호출 멱등 | `withdrawal._start`: 같은 (정책, 사유, 묶음) 기록이 있으면 쓰지 않음. 무효화는 아직 유효한 모델만, 조건부 기록은 (모델, 묶음, 정책)당 한 번 |
| 2 수동·자동 같은 관문 | `audit.record_verdicts`가 실패 시 잠금을 놓고 `withdrawal.withdraw(정책, "batch_label_error", [묶음])`을 부른다. `silver_policy.withdraw`·`lineage.invalidate_lineage` 제거(다른 경로 없음) |
| 2 사유 목록·모르는 값 차단 | 위 해석 표. 목록 밖·None → `unclear`(보류), 원문은 `given` |
| 2 직접 실패 계보 무효·다른 묶음 보류(저장하지 않고 파생)·후속 상속 | 보류는 저장하지 않는다: `model_reason`이 계보(자신+조상)의 묶음 정책이 철회됐는지 매번 계산 |
| 3 Champion 무효화·적격 복원·포인터 일관 | `withdraw`가 무효화 뒤 현재 Champion이 무효이면 `restore_locked`. 후보는 같은 계산 통과(보류 제외). 없으면 `_switch(target=None, "clear")` = Champion 없음(WAL, `registry.apply`·`pointer.current`·`settle`이 처리) |
| 3 조건부 유지 | 현재 Champion이 유효하나 `policy_withdrawn_hold`이면 Silver 장부에 `champion_conditional {model_id, batches, policies, reasons}` 한 번. 새 승격(재승격 포함)·복원 후보가 되지 않는다 |
| ① 개발용 Baseline | `champion.set_dev_baseline` → 레지스트리 `dev_baseline_set`, `registry.load(...)["dev_baseline"]`. 레지스트리 무효가 아닌 모델만(보류 모델 허용). 적격성 계산은 읽지 않는다 |
| 4 manifest 대조 | 위 형식 절. `eligibility._manifest_reason`·`manifest_reasons` |
| 4 실행 중 영향 작업 격리 | 철회 전 Silver로 만든 manifest라도 철회 뒤 등록하면 파생 보류(시험으로 확인) |
| 5 4단계 공개 조회 | `eligibility.parent_check(root, model_id)` → `{ok, model_id, reason?, detail?}`. 감사 대기는 막지 않고 무효·보류·manifest·가중치 누락은 막는다. ok=False면 Silver·부모 없는 등록 모델을 같은 함수로 확인해 새 계보를 시작한다. 루프는 구현하지 않음 |

결정이 없어 안전한 쪽으로 둔 지점(보고):
- 레거시 상태: 옛 코드가 감사 전에 승격시킨 Champion(호출자 audit_status)은 복원 후보 계산에서 감사 대기로 걸려 후보가 되지 않는다.
- Champion 없음 뒤의 첫 승격은 비교 대상이 없어 비교 가능성 검사를 건너뛴다(기존 첫 Champion 규칙과 같음). 개발용 Baseline과의 비교는 하지 않는다(적격성 근거가 아니므로).
- 개발용 Baseline은 자동으로 정하지 않는다(어느 모델로 할지 결정이 없음). 4단계 호출자가 명시한다.
- 무효·보류 판단 전에 레지스트리에 아직 반영되지 않은 파생 무효 Champion은 `read_current(...)["valid"]`가 True로 보인다. 복구(`withdraw`)가 돌면 해소되며, 그 전에도 승격·복원 후보 계산은 막는다.

## 필수 회귀 시험 대응

| 필수 시험 | 시험 (파일 :: 이름) |
|---|---|
| b1 실패 후 b2가 기존 10% 감사를 통과해도 승격 불가 | withdrawal_policy :: test_b1_failure_holds_b2_even_though_b2_passed_its_ten_percent_audit (b2 사전 통과, b3는 실패 뒤 통과, 철회 뒤 등록 모델 포함) |
| 철회 전 감사 결과만으로 재적격 불가 | withdrawal_policy :: test_audits_finished_before_the_withdrawal_never_requalify |
| 새 판본·문구 수정으로 보류 우회 불가 | withdrawal_policy :: test_new_version_reworded_labels_or_renaming_cannot_bypass_the_hold (v2 승인, 같은 키 재생성은 중복 거절, 기준 문구만 바꾼 새 라벨, 이름·설정 변경 재등록, 혼합) |
| 직접 실패 후속 계보 전체 무효 | withdrawal_policy :: test_direct_failure_invalidates_every_descendant_even_one_registered_later, champion_lineage :: 5개 |
| 조건부 Champion 후속의 보류 상속 | withdrawal_champion :: test_conditional_champion_is_recorded_once_never_restored_to_and_descendants_inherit_the_hold |
| 적격 복원 후보 부재 시 Champion 없음 | withdrawal_champion :: test_no_eligible_candidate_switches_to_no_champion_and_a_separate_dev_baseline_keeps_exploration, champion_restore :: test_restore_walks_back_one_valid_champion_at_a_time, champion_guards 2개 |
| 수동·자동 관문 일치 | withdrawal_champion :: test_manual_and_automatic_withdrawal_reach_the_same_state |
| 두 장부 갱신 중 강제 종료(실제 SIGKILL, 쓰기 지점 전부) 후 같은 최종 상태 | withdrawal_kill :: 3개(자동 철회+복원 20지점, 수동 철회+Champion 없음 14지점, 보류만+조건부 기록 4지점: 끊김 없는 실행이 지나간 ledger.append·포인터·복원 가중치 os.replace의 앞뒤 전부), champion_kill_points :: test_kill_during_lineage_invalidation_then_same_call_again_finishes_the_restore(포인터 fsync 지점 포함), silver_kill :: 4개 |
| 중복 철회 멱등 | withdrawal_champion :: test_repeating_the_same_withdrawal_writes_nothing_and_restores_nothing_again (세 장부·포인터 바이트 동일), champion_lineage :: test_repeating_writes_nothing_... |
| 철회·승격 동시 실행(실제 프로세스, 지연 주입)에서 부적격 승격 0 | withdrawal_concurrency :: 3개(철회 중 시작한 승격 거절, 승격 중 시작한 철회는 대기, 무작위 6회 경합). 순서는 실제 쓰기 직후 공용 기록으로 비교 |
| 오래된·위조 audit_status 우회 불가 | eligibility_manifest :: test_stale_or_forged_audit_status_cannot_bypass_the_gate (인자 TypeError, 실패 뒤 같은 권한으로 덧붙인 complete 줄로도 무효 유지, 줄 고쳐 쓰기 = StoreError), champion_audit :: test_promote_takes_no_audit_status_... |
| manifest 불일치 승격 거절 | eligibility_manifest :: test_missing_corrupt_or_mismatched_manifest_is_refused_for_the_model_and_its_descendants (8종 + CAS 없음·변조 + 조상) |
| 영향받지 않은 개발 작업 지속 | eligibility_manifest :: test_unaffected_policy_work_continues_at_function_level (다른 정책 라벨 생성·감사·학습 가능 라벨·승격·선별). **루프 수준은 4단계 미검증** |
| 추가: 감사 실패 기록과 policy_withdrawn 사이 kill 직후(복구 전) b2 승격 거절 | withdrawal_kill :: test_kill_between_the_failure_record_and_the_withdrawal_record_still_refuses_b2 (+ kill 3개 시험이 실패/철회 기록이 있는 모든 지점에서 c2 승격 거절을 확인) |
| 합의안 8절 그 밖 | 정책 전반 오류·범위 없는 오염 → 전체 무효, 범위 지정 오염 → 그 묶음만: withdrawal_policy :: test_systematic_error_or_unscoped_contamination_...; 사유 불명확 수동 철회 → 신규 학습·승격 차단: test_unclear_or_unknown_reason_...; 표본 9개 이하 오류 1개 → 실패하되 다른 묶음은 무효화 안 함: test_b1_failure_... (표본 2개 중 1개); 실행 중 작업 격리·Pending manifest: eligibility_manifest :: test_pending_labels_or_a_job_trained_before_...; 부모 조회·초기 모델: test_parent_query_and_initial_model_use_the_same_calculation; 입력 형식 거절: withdrawal_policy :: test_malformed_scope_... |

"필요한 재검증 통과 → 재적격 판정 가능"(합의안 8절)은 최종 결정 ②로 구현하지 않았다(자동 재적격 경로 없음). 시험은 반대로 어떤 경로로도 재적격되지 않음을 확인한다.

### 기존 시험의 기대값 변경과 근거

| 시험 | 변경 | 근거 |
|---|---|---|
| champion_audit 전체 | audit_status 인자 대신 실제 Silver 장부로 감사 상태를 만든다. "장부에 없는 묶음 = audit_pending"은 manifest 불일치로 먼저 막힘 | 보완 1(audit_status 불신), 보완 4(manifest) |
| champion_lineage 전체, champion_promote·guards·kill_points의 계보 무효화 | `lineage.invalidate_lineage` → `withdrawal.withdraw`(실제 장부의 묶음) 또는 레지스트리 `invalidated` 직접 기록 | 수동·자동 같은 관문(다른 무효화 경로 제거) |
| champion_guards 2개, champion_restore 1개 | 복원 후보가 없으면 "무효인 채 남음" → "Champion 없음"(포인터 model_id None, `champion_cleared`) | 최종 결정 ① |
| champion_registry | `data_manifest_sha == sha256("data-c")` → CAS에 manifest가 있음 | 시험 도구가 실제 manifest를 등록 |
| champion_restore | lambda를 없애 파일 함수 수 8 → 7(`bad_copy`가 `cas.get`과 같은 인자) | 함수 수 규칙(lambda 포함) |
| silver_cascade·silver_kill | 이벤트 목록에서 `cascade_done` 제거, 철회 기록 사유 `batch_label_error`·묶음 확인 추가 | 복구는 장부 재계산(표지 줄 불필요) |
| silver_audit_status | 모델을 라벨이 생긴 뒤 등록(manifest), audit_status 인자 제거, 같은 정책 실패 뒤 기존 Champion 재승격은 보류로 거절 단언 추가 | 보완 1·4, B+D 보류 |
| silver_policy·silver_gate | `silver_policy.withdraw` → `withdrawal.withdraw`, 목록 밖 사유는 `unclear`로 기록 확인 | 단일 관문, 사유 목록 |
| silver_support `cascade_setup` | 두 번째 승격을 관문 없는 WAL 전환으로(옛 코드가 남겼을 수 있는 상태 모사) | 새 관문에서는 감사 대기 모델이 승격되지 않으므로 복원 경로 시험에 옛 상태가 필요 |

## 실행 근거

시험 대상(코드+시험): `f695c1c0c7bd7803c26f698e3ed2c6a9152f3d07`. 이 문서 커밋은 그 위에 문서만 추가한다(SHA는 `git log`).

| 명령 (cwd = worktree) | 결과 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (3.12, 301개) | 종료 0 |
| 같은 명령 `/usr/bin/python3` (3.9.6, 301개) | 종료 0 |
| 3.12 + `-W error::ResourceWarning` + `-p "test_harness_withdrawal_*.py"`(19개) 3회, `-p "test_harness_eligibility_*.py"`(5개) 1회 | 종료 0, 0, 0 / 0 (ResourceWarning 0건) |
| `tests.test_harness_withdrawal_concurrency` 단독 8회 반복(3.9) | 8회 모두 OK |
| 수정 전 결함 재현: 기준 `c249cac`의 harness를 scratchpad에 풀고 재현 스크립트 실행 | 결함 4개 모두 재현(아래) |
| 같은 재현 절차를 수정 후 코드로(감사 상태 인자 제거·manifest 등록만 맞춤) | 4개 모두 거절·정상 |
| 변이 시험(임시 복사본, 원본 미수정) 25개 | 아래 |
| `git diff --check` | 종료 0 |

수정 전 재현(기준 코드, 결과 그대로): ① b1 감사 실패 뒤 b2 모델이 `audit_status(root)`로 승격됨 ② 위조 `{"b1": "complete"}`로 감사 대기 모델 승격됨
③ 복원이 보류여야 할 b2 모델(m2)을 고름 ④ `audit_completed(failed)` 뒤 `policy_withdrawn` 전에 멈춘 상태에서 b2 모델 승격됨.
수정 후 같은 절차: ① ④ `policy_withdrawn_hold` 거절 ② TypeError ③ base로 복원.

변이 시험: 25개 중 25개가 시험 실패로 잡혔다(최종 재실행: `f695c1c`에서 25/25, 살아남은 변이 0). 처음 실행에서 "승격이 Silver 잠금을 안 잡음"(M10)이 살아남았다: 동시 실행 시험이 장부 ts(호출 시작 시각)로 순서를 비교해 잠금 위반을 못 봤다.
실제 쓰기 직후의 공용 순서 기록으로 바꾼 뒤 3회 모두 잡혔다. 같은 원인으로 무작위 경합 시험이 정당한 순서(늦게 시작했지만 먼저 잠금을 잡은 승격)를 위반으로 오판할 수 있었고 같이 고쳤다(수정 뒤 8회 반복 통과).
변이 목록: 보류 검사, 파생 무효, 감사 실패=철회 접기(빈틈), manifest 대조 끔·묶음 포함 검사·Pending 허용·조상 검사, 복원 후보 적격성 무시, Champion 없음 전환 제거, 승격 적격성 생략,
승격 Silver 잠금 제거, 철회의 무효화·복원·조건부 기록 끔, 시작 기록 중복 허용, 사유 정규화 제거, systematic·범위 없는 오염 전체 무효 제거, 감사 실패가 관문을 안 부름,
감사 대기 검사 제거, 조상 보류 상속 제거, 덧붙인 완료 줄이 실패를 지움, 부모 조회의 감사 대기 차단, 부모 조회 가중치 검사 제거, Baseline이 무효 모델 허용.

## 구조

함수 정의 수(ast, 메서드·중첩·lambda 포함, 한도 ≤7):

| 파일 | 전 → 후 | 파일 | 전 → 후 |
|---|---|---|---|
| harness/eligibility.py (신규) | 6 | tests/test_harness_withdrawal_support.py (신규, 시험 아님) | 6 |
| harness/withdrawal.py (신규) | 3 | tests/test_harness_withdrawal_policy.py (신규) | 7 |
| harness/champion.py | 5 → 6 | tests/test_harness_withdrawal_champion.py (신규) | 5 |
| harness/audit.py | 6 → 5 | tests/test_harness_withdrawal_kill.py (신규) | 5 |
| harness/audit_rate.py | 4 → 5 | tests/test_harness_withdrawal_concurrency.py (신규) | 5 |
| harness/silver_policy.py | 7 → 6 | tests/test_harness_eligibility_manifest.py (신규) | 6 |
| harness/gate.py | 3 → 2 | tests/test_harness_champion_restore.py | 8 → 7 |
| harness/registry.py·pointer.py | 5·3 → 5·3 | 그 밖에 바꾼 시험 파일 13개 | 변화 없음(6~7) |
| harness/lineage.py | 2 → 삭제 | | |

호출 깊이(이름 참조를 간선으로 센 보수적 상한, harness 전체 재측정, 순환 없음): 공개 함수 최대 4, 4 초과 0.

| 진입 | 깊이 | 최장 경로 |
|---|---|---|
| audit.record_verdicts | 4 | → withdrawal.withdraw → withdrawal._start → silver_store.append → ledger.append (같은 깊이: → withdraw → champion.restore_locked → eligibility.model_reason → gate.ancestors, → restore_locked → cas.get → cas.blob_path) |
| withdrawal.withdraw | 3 | 위에서 첫 간선을 뺀 경로 |
| champion.promote·restore_last_verified | 3 | → silver_store.load → ledger.verify → ledger._load (→ eligibility.manifest_reasons → _manifest_reason → cas.sha_file도 3) |
| eligibility.parent_check·champion.set_dev_baseline | 3 | → registry.load → ledger.verify → ledger._load |

깊이를 맞추려고 `restore_locked`가 manifest를 직접 읽지 않고 호출자가 계산한 `manifests`를 받는다(대조는 `manifest_reasons` 한 곳).

## 한계 (사용자 지시로 명시)

- 감사 표본이 작다(D-3 제안값 10%면 Silver 20개 묶음의 표본은 2개). 작은 표본의 단일 오류 실패가 정책 전체의 오류율을 대표하지 않는다.
- 판정자는 1명이며 `judge="human"`은 호출자의 선언이다(실제로 사람인지는 8단계 Gold 수집 훅 몫).
- 묶음 간 오류 상관은 검증하지 않았다. 실제 Silver 오류율·감사 결과가 없어 B+D와 C안의 우열을 확정하지 않는다.
- 같은 권한의 장부 편집: 줄 고쳐 쓰기는 해시 체인이 잡지만, 해시를 다시 계산한 위조·그럴듯한 줄 덧붙이기는 외부 복제 꼬리 해시 없이는 잡지 못한다(감사 실패 무효는 덧붙인 완료 줄로 지워지지 않게만 했다).
- manifest는 선언된 자료만 대조한다(선언하지 않은 부모 가중치 사용은 못 잡음). 실제 학습의 manifest 생성은 4단계.
- 합성 시험 통과는 실제 라벨 품질·모델 성능 개선의 근거가 아니다.

## 미검증

- 자율 루프 수준의 "영향받지 않은 개발 지속", Supervisor가 복구(`withdraw()`)를 부르는 연결, 4단계 계획 관문의 `parent_check` 사용: 4단계 미구현이라 함수 수준만 시험했다.
- 정전·OS 충돌(fsync 내구성): kill -9로는 시험할 수 없다. 여러 호스트·네트워크 파일 시스템의 `flock`: 미검증.
- 실제 장부·라벨·봉인 자료·실제 Champion과의 호환: 열람하지 않았다(합성 root만).
- 큰 장부·많은 모델의 성능: 승격·철회마다 모든 모델의 manifest를 다시 읽는다(`shortcut:` 주석). 미측정.
- 독립 검증: 받지 않았다(메인이 따로 수행).

## 리스크

- 호출자 계약 변경: `champion.promote`에 감사 상태를 넘기던 호출자, `silver_policy.withdraw`·`lineage.invalidate_lineage` 호출자는 깨진다(저장소 안 호출자는 모두 갱신, 시험 통과).
- 기존 레지스트리의 모델 중 CAS에 학습 manifest가 없는 모델은 모두 `manifest_missing`으로 승격·복원 후보가 되지 않는다(fail-closed). 실제 초기 Champion 등록 시 manifest를 함께 넣어야 한다.
- 옛 코드가 감사 전에 승격한 Champion은 복원 후보가 아니다. 적격 후보가 없으면 Champion 없음으로 전환된다.
- 승격·철회가 Silver 잠금을 잡으므로 긴 판정 함수가 Silver 잠금을 쥐고 있으면(`judge_candidates`) 승격도 기다린다.
- 레지스트리에 `dev_baseline_set`·대상 None 전환 줄이 생기면 이 변경을 되돌린 코드는 그 레지스트리를 읽지 못한다(`알 수 없는 이벤트`/`전환 의도가 앞뒤와 맞지 않음`).

## 롤백

`git revert <이 문서 커밋> f695c1c0c7bd7803c26f698e3ed2c6a9152f3d07`. 런타임 상태는 호출자가 준 root 아래에만 생긴다.
위 리스크 마지막 줄처럼, 이 코드로 Champion 없음 전환·Baseline 지정을 기록한 root는 되돌린 코드로 읽을 수 없다(그 root는 이 코드로 계속 읽거나 새로 만든다).

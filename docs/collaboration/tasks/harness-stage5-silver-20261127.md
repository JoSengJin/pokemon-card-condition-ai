# 하네스 5단계 — 능동 학습 선별·Silver 정책·품질 관문·비동기 감사·철회 (2026-11-27)

```text
task_id: harness-stage5-silver-20261127
owner: Claude (하위 에이전트, 구현·시험. 독립 Opus 검증은 메인이 따로 수행)
status: ready_for_review
base_sha: 5705371a5078a83d010160a67cce2016a6e1153f (1·2·6·7단계와 route()를 통합한 브랜치)
branch: claude/harness-silver-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: IMPLEMENTATION.md 2절 5행 "H 능동 학습·Silver·감사" 완료 기준을 합성 시험으로 통과한다.
  (a) 능동 학습 선별에서 봉인·보정 묶음의 실물 그룹(이미지 SHA·그룹 ID)이 0건이고, 그룹·판매자·군집 상한을 지키며, 같은 seed로 같은 선별이 나온다
  (b) Silver 정책은 보정 확인용 묶음의 사람 기준 오류율이 상한(10%) 이하일 때만 승인되고, 봉인 이미지 Silver·미리 채운 입력·Silver→Gold는 거절된다
  (c) 품질 관문은 사람 Gold 대조와 주입된 교차 검증 함수로만 판단하고 AI 합의를 정답으로 쓰지 않으며, 해결되지 않으면 Pending이다
  (d) 비동기 감사는 감사율 0%를 거절하고(최저 2%는 제안값), 감사 상태 정본을 추가 전용 해시 체인으로 저장해 7단계 `champion.promote`용 `audit_status`를 만든다
  (e) 감사 실패 시 정책 철회(Silver→Pending) → 7단계 `lineage.invalidate_lineage` → 마지막 정상 Champion 복원이 자동으로 이어진다
  (f) 재라벨 규칙: 같은 `(이미지 SHA, 구역, 기준 판본, 판정자)` 키 중복·이미 끝난 라벨 재요청 거절, 모델 결과 없이 고른 대상만 허용
allowed_files:
  - harness/active_learning.py (능동 학습 선별·라우팅, 순수 함수)
  - harness/silver_store.py (Silver 저장소: 추가 전용 해시 체인 `root/silver/store.jsonl`, 잠금)
  - harness/silver_policy.py (정책 승인·철회, 보정 확인용 사용 횟수, 등급 전이 규칙, 미리 채운 입력 거절)
  - harness/silver_gate.py (품질 관문, Silver·Pending 라벨 저장, 학습용 라벨)
  - harness/audit.py (감사 계획·판정 입력·철회·무효화 연쇄·`audit_status`)
  - harness/audit_rate.py (신규: 감사 상태 접기·감사율 일정·표본 추출. audit.py 함수 수 때문에 분리)
  - harness/relabel.py (신규: 재라벨 규칙 5-6)
  - tests/test_harness_silver_*.py (신규만, 시험 공용 도구 tests/test_harness_silver_support.py 포함)
  - 이 task 문서
forbidden_files: harness/supervisor*.py, harness/opstate.py, harness/ratelimit.py, harness/claude_run.py, harness/budget.py, harness/unlock.py
  (3단계, 다른 에이전트 작업 중), 1·2·6·7단계와 route 파일(harness/{cas,ledger,jsonio,contract,manifest,queue,states,holder,recovery,lease,checkpoint,
  graph,bootstrap,runner,scoring,scoring_rows,promotion,promotion_config,promotion_reasons,registry,gate,champion,lineage,pointer,route,route_escalate,
  route_record,route_support}.py 수정 금지: 공개 함수 호출만), card_condition/**, tools/**, 기존 tests/**, AGENTS.md, docs/agent/**, artifacts/**,
  data/**, 라벨·사진·모델·비밀 설정, .claude/**, 다른 plan 문서
contract:
  입력: 호출자가 준 root(런타임 상태는 root 아래에만), now(시각, 호출자 주입). 사진·라벨·모델·외부 AI는 읽거나 부르지 않는다. 판정 함수(독립 검증·결정론 CV)는 호출자가 주입한다.
  출력: root/silver/store.jsonl(1단계 ledger 해시 체인. 정책·보정 사용·라벨·감사·재라벨 요청 이벤트), 7단계가 쓰는 root/models/**와 root/ledger.jsonl(lineage 호출 결과).
  보존할 조건: stdlib만, Python 3.9+ 문법, 람다 없음. 네트워크·LLM·`claude`·학습·추론 없음. 기존 177개 시험 통과 유지.
  사람 라벨 요청 화면은 만들지 않는다(요청 이벤트와 대기열 데이터만). 감사 판정은 사람만 내린다: 이 단계는 사람 판정을 입력으로 받는 함수만 둔다.
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩 포함), 공개 함수 호출 깊이 ≤4(1·7단계 호출을 합산해 ast로 직접 재측정, 인계 절에 표).
  알려진 제약: `lineage.invalidate_lineage` 자체가 1단계 호출 포함 깊이 4(→ registry.load → ledger.verify → _check_line → _hash_entry)라서
  이 함수를 직접 부르는 호출자는 깊이 5가 된다. 감사 실패 연쇄를 호출하는 함수 하나에서만 발생하며 인계 절에 따로 기록한다.
checks:
  - `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0
  - 같은 명령 `/usr/bin/python3`(3.9)
  - 변이 시험(임시 복사본에서만): 봉인 제외 검사 제거, 최저 감사율 검사 제거, 철회·무효화 연쇄 제거, Silver→Gold 허용 등이 시험에서 잡힘
  - ast 함수 수·호출 깊이, `git diff --check`, `git diff --name-only 5705371 HEAD`가 허용 파일 안, `git status --short` 깨끗
experiment: 없음. 합성 시험이며 모델 성능·라벨 품질 근거가 아니다.
handoff: 아래 인계 절. 독립 Opus 검증은 메인이 따로 수행.
```

## 설계 근거(원문)

- DESIGN 5-1: 등급 Gold(사람)·Silver(AI 생성, 승인된 정책 범위, 품질 관문 통과, 학습에만)·Pending(판단 불가·품질 미달·미검증, 학습·평가 제외, 추정 금지). AI 라벨은 어떤 검증을 거쳐도 Gold가 되지 않는다(원칙 1).
- DESIGN 5-3: Silver 정책은 `(결함 유형, 층, 라벨 값)` 범위로 승인, 조건은 보정 확인용 묶음 오류율 ≤ 상한(D-3: 10%). 승인된 범위 안에서는 매번 승인을 받지 않는다. 미리 채운 라벨 화면 금지(앵커링). 봉인 이미지에는 Silver를 만들지 않는다.
- DESIGN 5-4: 보정 묶음 조정용/확인용 분리와 사용 횟수 기록. 사람 감사는 위험 기반·비동기(처음 몇 회차 높은 비율 → 오류율이 상한 아래면 낮춤, 최저 2%는 제안값, 조정마다 장부 기록, 분포 변화·Champion–Silver 불일치 급증 시 상향, 0% 금지). 감사 중에도 선별·학습 계속, 감사 완료 전 Champion 승격 금지, 실패 시 계보 무효화·복원·정책 철회·Silver→Pending. AI 합의는 정답이 아니다.
- DESIGN 5-5: 선별 점수 = 오류 유형 우선순위 × 층 부족도 × 모델 불확실성 × 예상 학습 가치(처음 1). 그룹·판매자 상한, 군집 할당량, 무작위 20%. 봉인·보정 묶음 실물 그룹 제외. 라우팅(Silver 큐/사람 큐), 능동 학습 표본은 대표 표본이 아니다.
- DESIGN 5-6: 재라벨 규칙. DECISIONS D-2·D-3: 오류율 상한 10%, 초기 감사 10% → 최저 2%(제안값), 감사 0% 금지.
- 7단계 인계(`harness-stage7-champion-20261127.md`): 감사 상태 `{묶음 ID: complete|not_required|pending|failed}`는 호출자가 `champion.promote`에 주는 입력이고 정본 저장소는 5단계가 정한다. 이 단계가 정본을 만든다.

## 구현 명세(설계에 있는 것만)

1. `silver_store.py` — `lock(root)`(`fcntl.flock`), `append(root, now, event, data)`, `load(root)`(체인 검증, 실패 시 `StoreError`). 모든 이벤트는 한 체인에 추가만 한다.
   쓰기 함수는 lock 안에서 load → 판단 → 추가 순서다(7단계 레지스트리와 같은 규약).
2. `silver_policy.py` — 정책 이벤트 접기, `approve`(보정 확인용 묶음의 n·errors로 오류율 ≤ 상한을 정확한 분수로 판정, 상한 초과 설정 거절, 확인용 사용 횟수 기록,
   조정용 묶음으로는 승인 불가), `withdraw`(멱등), `active_policy`, `grade_transition`(Silver→Gold 금지, 에이전트→Gold 금지, 판단 불가·미검증은 Pending), `reject_prefilled`.
3. `silver_gate.py` — `compare_to_gold`(사람 Gold만), `cross_verify`(주입 함수에 에이전트 라벨을 넘기지 않음, 모두 같은 확정 값일 때만 해결, 아니면 Pending),
   `judge_candidates`(정책 범위·봉인/보정 이미지·닫힌 묶음·혼합 정책 거절, 확실한 후보는 정책 보정에 근거해 Silver, 불확실은 교차 검증, 해결 안 되면 Pending),
   `fold_labels`(정책 철회 시 Silver → Pending 파생), `trainable_labels`.
4. `audit_rate.py`·`audit.py` — `plan_audit`(묶음당 정책 하나, 감사율 일정·표본 seed 고정), `set_rate`(0 이하 거절, 근거 필수), `record_verdicts`(판정자는 사람만, 표본 밖 ID·번복 거절,
   실패 시 정책 철회 → `lineage.invalidate_lineage` → `cascade_done`; 같은 인자 재호출로 이어간다), `audit_status`(묶음 ID → complete|not_required|pending|failed, 계획 안 된 묶음은 pending).
5. `active_learning.py` — `select`(점수·상한·무작위 20%·seed 고정·제외), `route`, 결과에 `representative: false`와 무작위 부분 `random_part`.
6. `relabel.py` — 재라벨 요청 키 중복·끝난 라벨 거절, 기준 판본 변경 유형의 대상 선정(모델 결과 필드가 있으면 거절), 자기 일치도 재판정은 계획 ID가 있는 반복으로 따로 표시.

## 필수 시험(합성 데이터, 실제 프로세스·SIGKILL)

봉인·보정 그룹 0건 선별 / 그룹당·판매자당·군집 상한 / 같은 seed 같은 선별·다른 seed는 다른 무작위 부분 / 정책 범위 안·밖 라우팅 / 봉인 이미지 Silver 거절 /
미리 채운 입력 거절 / Silver→Gold 금지 / 오류율 상한 경계(정확히 10%) / 감사율 0% 거절·2% 하한·상향 신호 / 감사 실패 시 철회+무효화+복원 자동 연쇄(7단계 실제 함수) /
감사 진행 중 승격 거절(`champion.promote`에 pending 전달) / kill -9 뒤 감사 상태 저장 일관성 / 재라벨 중복 거절. 시험 파일당 정의 ≤7.

## 인계

### 결과

필수 시험 항목을 모두 합성 데이터·주입 함수·실제 subprocess·실제 SIGKILL·7단계 실제 함수(`champion.promote`·`lineage.invalidate_lineage`·`registry`)로 통과했다.
합성 시험이며 모델 성능·라벨 품질·정확도 근거가 아니다(실제 사진·라벨·모델·외부 AI 호출 없음). 이번 변경은 개발 진척 5단계(능동 학습·Silver·감사·철회)의 구현이며
평가 지표는 새로 만들지 않았다(일반화 개선 미확인). 독립 Opus 검증은 아직 받지 않았다(메인이 따로 수행).

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 작업 계약 커밋 | `aae925d49d02081d1a6189c06002452bd339f419` |
| 구현 (`feat(harness)`) | `fb4b8d4a82522dca92f26dd6c02e9bfc5d7e4393` |
| **최종 시험 대상 (구현 + 시험, `test(harness)`)** | `5c13856e1412f5fa066cd21720ebde9f60f3ac62` (217개 = 기존 177 + 이번 40) |
| 이 문서 갱신 커밋 | 시험 대상 위에 문서만 추가(코드 변경 없음). SHA는 `git log`로 확인 |

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행, 작업 트리 깨끗) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14, 217개, 16.05초) | 0 |
| 같은 명령 `/usr/bin/python3` (Python 3.9.6, 217개, 19.68초) | 0 |
| 3.12 + `-W error::ResourceWarning` + `-p "test_harness_silver_*.py"`(40개), 3회 | 0, 0, 0 |
| `git diff --check 5705371 HEAD` | 0 |
| `git diff --name-only 5705371 HEAD` | 허용 파일 안(이 문서, harness 7개, tests/test_harness_silver_*.py 11개) |

변이 시험(임시 복사본에서만, 원본 수정 없음. 스크립트는 scratchpad): 74개 변이가 모두 시험 실패로 잡힘(살아남은 변이 0, 최종 시험 대상에서 전체 재실행).
봉인 제외 검사 제거(AL01·AL02·AL03·SG01), 최저 감사율 검사 제거(AR01·AR02·AU01), 철회·무효화 연쇄 제거(AU02·AU03), Silver→Gold 허용(SP05: 검사 제거 + 허용 목록 추가),
AI→Gold 허용(SP06), 오류율 경계(SP01·SP02·SP03), 조정용 묶음 승인(SP04), 미리 채움 검사(SP07·RL07), 상한(AL04·AL05·AL06), seed 무시(AL07·AR04·RL09),
교차 검증 불일치 허용(SG03)·에이전트 라벨 전달(SG04)·Pending 값 저장(SG05), AI Gold(SG06), 닫힌·혼합 묶음(SG07·SG08), 철회 파생(SG09), 감사 경계·조기 실패(AU05·AU06),
미계획 묶음 complete(AU07), 사람 아닌 판정자(AU04), 표본 밖·번복(AU08·AU09), 연쇄 재실행 방지(AU10), resume(AU13), 체인 검증·잠금(ST01·ST02), 재라벨 중복·끝난 라벨·모델 필드·유형 필터 등.
처음 실행에서 살아남은 변이 6개(AL06 군집 상한, AL12 protected 구조 검사, SG06 AI Gold, SP05, AR10 신호의 수동 조정 해제, SG14 uncertain 검사)는 시험을 강화해 잡았다
(AL06·SG06·AL12는 시험이 다른 검사에 가려 있었음). 단일 지점 SP05(`Silver→Gold` 명시 검사만 제거)는 `_ALLOWED` 목록이 같은 전이를 막는 이중 방어라 동치 변이다.
`ST02`(잠금 제거)는 3회 반복에서도 매번 잡혔다(3개 프로세스 동시 연쇄 시험).

### 파일별 함수 정의 수 (ast, 한도 ≤7. 람다 없음)

| 파일 | 수 | 파일 | 수(시험) |
|---|---|---|---|
| harness/silver_store.py | 3 | tests/test_harness_silver_support.py (시험 아님) | 7 |
| harness/silver_policy.py | 7 | tests/test_harness_silver_active_learning.py | 7 (6) |
| harness/silver_gate.py | 7 | tests/test_harness_silver_policy.py | 7 (5) |
| harness/active_learning.py | 7 | tests/test_harness_silver_gate.py | 6 (5) |
| harness/audit.py | 6 | tests/test_harness_silver_verify.py | 3 (2) |
| harness/audit_rate.py | 4 | tests/test_harness_silver_audit_rate.py | 7 (4) |
| harness/relabel.py | 5 | tests/test_harness_silver_audit_status.py | 7 (5) |
| | | tests/test_harness_silver_cascade.py | 7 (4) |
| | | tests/test_harness_silver_kill.py | 6 (4) |
| | | tests/test_harness_silver_relabel.py | 7 (5) |
| | | tests/test_harness_silver_verifiers.py (시험 아님) | 5 |

### 호출 깊이 (전이 수, 1·7단계 호출 합산)

측정: ast로 이름 참조(호출·콜백)를 간선으로 센 보수적 상한(7단계 인계와 같은 방법, 스크립트는 scratchpad). 순환 없음. 가장 긴 경로만 적었다.

| 진입 | 깊이 | 최장 경로 |
|---|---|---|
| 순수 함수 전부(`active_learning.*`, `audit_rate.*`, `silver_policy.ratio/fold/active_policy/grade_transition/reject_prefilled`, `silver_gate.label_id/compare_to_gold/cross_verify`, `audit._status/_outcome`, `relabel.key_of/fold_requests`) | 0~1 | 예: select → pick |
| silver_store.append | 2 | → ledger.append → ledger._hash_entry |
| silver_store.load | 3 | → ledger.verify → ledger._check_line → ledger._hash_entry |
| silver_policy.approve·withdraw, silver_gate.judge_candidates·trainable_labels, audit.plan_audit·set_rate·audit_status, relabel.request_relabel·request_repeat | 4 | → silver_store.load → ledger.verify → ledger._check_line → ledger._hash_entry |
| **audit.record_verdicts** | **5 (한도 초과)** | → lineage.invalidate_lineage → registry.load → ledger.verify → ledger._check_line → ledger._hash_entry (cas 경로도 같은 5) |

초과 원인과 처리: `lineage.invalidate_lineage` 자체가 1단계 호출을 포함해 이미 깊이 4(7단계 인계 표)라서, 그 함수를 부르는 어떤 호출자도 5가 된다. 7단계·1단계 코드는 수정 금지라 이 함수 하나만 5로 남겼다.
다른 모든 함수는 `load`를 한 번만 부르고 순수 접기 함수(깊이 0~1)와 `append`(깊이 2)만 부르도록 평평하게 짰다. 감사 실패 연쇄를 쪼개 깊이를 감추지 않았다(호출은 `record_verdicts` 안에서 직접).
메인이 결정할 선택지: (a) 1단계 `ledger.verify`·`append` 내부를 평탄화하면 5→4(1단계 수정이라 이 작업 범위 밖), (b) 이 함수 한 개에 한해 5를 예외로 승인, (c) 연쇄 호출을 Supervisor 쪽에서 `record_verdicts(...)`의 반환(`status: failed`)을 받아 따로 부르게 분리(자동 연쇄 요구와 충돌).
미확인 경로(정적으로 확정할 수 없음): `silver_gate.cross_verify`가 호출자가 주입한 판정 함수(`func(...)`)를 부른다. 주입 함수 내부 호출은 이 측정에 들어가지 않는다.

### 필수 시험 대응

| 필수 | 시험 (파일 :: 이름 요지) |
|---|---|
| 봉인·보정 그룹 0건 선별 | active_learning :: test_sealed_and_calibration_groups_are_never_selected (이미지 SHA·그룹 ID·시드 6개·예산 3종, 목록 없으면 거절), gate :: test_sealed_and_calibration_images_get_no_silver_... |
| 그룹당·판매자당·군집 상한 | active_learning :: test_group_seller_and_cluster_caps_each_bind_on_their_own_... (다른 두 상한을 풀어 하나씩 묶이게 함) |
| 같은 seed 같은 선별·다른 seed 무작위 20% 변화 | active_learning :: test_same_seed_same_selection_... (입력 순서 뒤집어도 같음, 상위 선별은 같고 무작위 부분만 다름), test_random_twenty_percent_is_flagged_... (`representative: false`, `random_part`) |
| 정책 범위 안/밖 라우팅 | active_learning :: test_routing_by_policy_scope_and_queues_carry_no_model_fields |
| 봉인 이미지 Silver 거절 | gate :: test_sealed_and_calibration_images_get_no_silver_even_when_verifiers_agree |
| 미리 채운 입력 거절 | policy :: test_prefilled_inputs_are_refused_at_any_depth, relabel :: test_prefilled_items_and_selections_... |
| Silver→Gold 금지 | policy :: test_grade_transition_never_makes_an_ai_label_gold |
| 오류율 상한 경계(정확히 10%) | policy :: test_error_rate_exactly_at_cap_is_approved_and_anything_above_is_refused (5/50·6/60·12/120 승인, 6/50·7/60·11/100·9/80 거절, 상한 0.11·0 설정 거절), cascade :: test_audit_at_exactly_the_cap_passes_and_one_more_error_fails (감사 표본 1/10 통과·2/10 실패) |
| 감사율 0% 거절·2% 하한·상향 신호 | audit_rate :: test_zero_is_refused_and_manual_or_automatic_changes_..., test_rate_starts_at_ten_percent_decays_by_half_and_stops_at_the_two_percent_floor (10%×3 → 5% → 2.5% → 2%×3), test_signals_raise_the_rate_back_and_the_basis_is_recorded |
| 감사 실패 시 철회+무효화+복원 자동 연쇄(7단계 실제 함수) | cascade :: test_failed_audit_withdraws_the_policy_invalidates_the_lineage_and_restores_the_last_good_champion (정책 철회, Silver→Pending, 학습 라벨 0, m1·c1 무효, 포인터 base, 세 장부 체인 정상, 재호출 무변화), test_unrelated_champion_stays_..., test_failure_is_decided_as_soon_as_the_errors_exceed_the_cap_... |
| 감사 진행 중 승격 거절(`champion.promote`에 pending 전달) | audit_status :: test_promotion_is_refused_while_the_audit_is_pending_or_failed_and_allowed_after_it_completes (미계획·계획·부분 판정 → audit_pending, 완료 → 승격, 실패 묶음을 쓴 새 모델 → audit_failed) |
| 감사 중에도 선별·학습 계속 | audit_status :: test_selection_labeling_and_planning_continue_while_an_audit_is_pending |
| kill -9 뒤 감사 상태 저장 일관성 | kill :: test_kill_at_every_step_of_the_failure_cascade_... (10개 지점: 판정·완료·철회·registry 무효화·전환 의도·전환·복원 요약·연쇄 완료 앞뒤), test_kill_in_the_middle_of_labeling_..., test_kills_at_random_moments_... (30회 임의 지연 SIGKILL, 일회성 관찰 killed=10·연쇄 도중 3, 단언은 killed>0), test_two_processes_running_the_same_cascade_at_once_... (3개 프로세스 동시) |
| 재라벨 중복 거절 | relabel :: 5개(같은 호출 안·호출 간 중복, 끝난 라벨, 모델 결과 필드 거절, 유형 필터, seed 재현, 자기 일치도 계획 반복) |
| 변조 감지 | audit_status :: test_tampering_with_the_store_is_detected_... (줄 수정·중간 삭제·순서 변경·꼬리 잘림(복제 해시 대조)) |

### 가정 (명세가 모호해 가장 보수적으로 고른 해석)

1. 묶음 ID(`batch_id`) = 감사 단위 = 7단계 `silver_batches`의 값이다. 한 묶음은 정책 하나만 쓴다(다른 정책이 섞이면 `mixed_policy_batch` 거절). 감사 판정이 정책 단위 오류율이어서 정책이 섞이면 철회 대상이 모호해지기 때문이다.
2. 감사 실패 기준 = 표본 오류율 > 정책 상한(정책에 저장된 cap, ≤10%). 경계(정확히 10%)는 통과. 판정이 덜 끝나도 이미 낸 오류만으로 상한을 넘으면(분모는 전체 표본 수) 확정 실패(조기 실패).
3. 감사 표본 크기 = ceil(감사율 × Silver 수), 최소 1. 표본은 `sha256(seed|라벨 ID)` 순서의 앞 k개다(파이썬 난수 구현에 의존하지 않음).
4. 감사율 일정: 설계에 값이 없는 부분은 호출자가 `schedule={initial, floor, initial_rounds}`로 사전 등록한다(기본값 없음). `audit_rate.SUGGESTED_SCHEDULE`(10%·2%·3회차)는 제안값일 뿐이다.
   초기 회차 수(3)와 "오류율이 상한 이하이면 회차마다 절반으로 낮춘다"는 규칙은 설계 문구("낮추되 최저 2%")를 구체화한 제안이며 사용자 확정 값이 아니다. 최저 2%도 제안값이다.
   `set_rate`로 0 이하·1 초과는 거절하고, 2% 미만의 수동 조정은 근거가 있으면 허용한다(최저 2%가 제안값이기 때문. 0%만 금지).
5. Silver 정책 승인에는 `min_n`(대조한 구역 수 하한, 사전 등록 값, 기본값 없음)이 필요하다. 설계는 "첫 검증은 50~100구역 규모"라고만 해서 하한 값을 정하지 않았다.
6. 능동 학습: 층 부족도는 호출자가 `stratum_scarcity` 가중치로 준다. 모델 불확실성 = max(문턱 근접도(`1 - |점수-문턱|/threshold_width`), Champion–Challenger 점수 차이). 예상 학습 가치는 `learning_value`(없으면 1).
   군집 할당량(`cluster_quota`)은 군집당 최대 선별 수 정수로 해석했다. 무작위 몫 = 예산의 20%(반올림, 정수 계산). 상한 때문에 예산을 못 채우면 `shortfall`로 보고하고 무작위로 더 채우지 않는다.
   라우팅은 후보의 `expected_label`(라우팅 전용 힌트)로 (결함 유형, 층, 라벨 값) 범위를 대조한다. 큐 항목에는 점수·기대 라벨을 담지 않는다.
7. 보정 묶음에도 Silver를 만들지 않는다(`calibration_image` 거절). 명세는 봉인만 명시했으나 설계 6-5("같은 실물 카드는 층 사이에 겹치지 않는다")와 5-5 제외 규칙에 맞춘 확장이다. 필요 없으면 `silver_gate.check_candidate`의 `protected_reason` 결과 중 calibration만 통과시키면 된다.
8. 라벨 출처 기록은 `label-provenance` 규칙(기준 문구 버전 + 사진 조각 해시) 중 이미지 SHA·기준 판본·모델 버전·정책 ID만 저장한다(조각 해시는 이 단계 입력에 없음).
9. 같은 키의 라벨은 한 번만 만든다(라벨 ID = 이미지 SHA·구역·기준 판본·생성자 해시). Pending도 끝난 라벨로 본다(같은 기준 판본에서 다시 판정하려면 재라벨 규칙을 따른다).
10. 판단 불가(에이전트 `label_value=None`)·교차 검증 미해결은 Pending이고 값을 저장하지 않는다. 정책이 철회되면 그 정책의 Silver는 파생 상태로 Pending이 되며 원본 이벤트는 지우지 않는다.
11. 감사가 계획되지 않았거나 판정이 덜 끝난 묶음은 `pending`, Silver가 하나도 없는 묶음만 `not_required`다. 라벨이 없는 묶음 ID는 `audit_status`에 나오지 않는다(7단계는 누락을 `audit_pending`으로 취급한다).
12. 사람 판정 입력은 `judge="human"`이라는 호출자의 선언뿐이며 실제로 사람인지는 이 단계에서 검증할 수 없다(Gold 수집 훅·nonce는 8단계 몫).

### 미검증

- 정전·OS 충돌(fsync 내구성): kill -9로는 시험할 수 없다(1단계 `ledger.append` fsync에 의존).
- 실제 사진·라벨·Gold·보정 묶음·실제 에이전트 라벨·실제 Champion과의 통합, Supervisor 호출, 사람 라벨 요청 화면: 하지 않았다(이 단계 범위 밖).
- `reject_prefilled`·`MODEL_FIELDS`는 필드 이름 목록 기반이라 다른 이름으로 숨긴 미리 채움·모델 결과는 못 잡는다.
- 큰 저장소의 성능: `ledger.append`가 줄 수에 비례해 읽으므로 라벨이 수만 건이면 느려질 수 있다(미측정).
- 독립 Opus 검증은 받지 않았다. 여러 호스트·네트워크 파일 시스템의 `flock`은 미검증(로컬 macOS만).
- 임의 지연 kill 시험(30회)은 시간 의존이라 연쇄 도중에 죽은 횟수는 단언하지 않는다(일회성 관찰 3회). 지점 지정 kill 10개가 결정적 근거다.

### 리스크·알려진 제약

- **깊이 5**: `audit.record_verdicts` 하나(위 표). 메인 결정 필요.
- **복원 경로는 승격이 먼저 일어난 경우에만 의미가 있다**: 7단계 `promote`는 감사가 끝나기 전 승격을 거절하므로 정상 흐름에서 감사 실패로 무효화되는 모델은 Challenger뿐이고 Champion 복원은 일어나지 않는다.
  복원은 호출자가 감사 상태를 직접 `complete`로 줘서 승격한 경우(시험 `cascade_setup`이 이를 모사) 등에서만 쓰인다. 실패 뒤에도 같은 묶음을 쓰는 새 모델은 `audit_failed`로 거절된다.
- `audit_rate.rate_for`의 "누적 오류율 > 상한이면 초기 비율로 복귀" 분기는 정상 흐름에서 도달하기 어렵다(통과한 회차는 각각 ≤ 상한이고, 실패한 정책은 철회돼 새 판본으로 시작). 순수 함수 직접 호출 시험만 있다.
- `judge_candidates`·`approve`는 `silver_store.lock`을 잡은 채로 주입 판정 함수를 호출한다. 판정 함수가 오래 걸리면 다른 쓰기가 기다린다.
- 감사 연쇄는 `silver_store.lock` 안에서 7단계 `registry.lock`을 잡는다(순서 silver → registry). 반대 순서로 두 잠금을 잡는 코드가 생기면 교착 위험이 있다(현재 없음).
- `lineage.invalidate_lineage`가 `ChampionError`(CAS 손상 등)를 내면 연쇄는 `cascade_done` 없이 멈추고 상태는 `failed`로 남아 승격이 계속 거절된다. 같은 인자로 재호출하면 이어간다.
- 1단계 `ledger.append`는 마지막 줄이 손상되면 이어 쓰기를 거절한다(쓰기 도중 줄이 잘리는 이론상 상황에서 사람 확인 필요).

### 롤백

이 작업은 새 파일만 추가했다(1·2·6·7단계·route·기존 시험 수정 없음). `git revert 5c13856e1412f5fa066cd21720ebde9f60f3ac62 fb4b8d4a82522dca92f26dd6c02e9bfc5d7e4393`
(또는 harness/{active_learning,silver_store,silver_policy,silver_gate,audit,audit_rate,relabel}.py와 tests/test_harness_silver_*.py 삭제)로 되돌린다.
런타임 상태는 호출자가 준 root 아래 `silver/`에만 생기므로 저장소에는 남는 것이 없다.

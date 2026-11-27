# 하네스 5단계 — 능동 학습 선별·Silver 정책·품질 관문·비동기 감사·철회 (2026-11-27)

```text
task_id: harness-stage5-silver-20261127
owner: Claude (하위 에이전트, 구현·시험. 독립 Opus 검증은 메인이 따로 수행)
status: implementing
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
handoff: 아래 인계 절(구현 후 채움). 독립 Opus 검증은 메인이 따로 수행.
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

(구현 후 채움)

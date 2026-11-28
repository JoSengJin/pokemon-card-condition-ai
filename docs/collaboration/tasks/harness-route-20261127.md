# 하네스 route() — 모델·Effort 라우팅 (2026-11-27)

```text
task_id: harness-route-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet 하위 에이전트, 독립 Opus 검증은 메인이 따로)
status: ready_for_review
base_sha: d582cc2 (전체 SHA는 `git rev-parse d582cc2`; 작업 계약 커밋 3c0560d가 그 위)
branch: claude/harness-route-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: model-routing-design.md 1절 `routing-policy-v1`(사용자 승인 2026-11-27)을 정책 데이터 파일 + 순수 함수로 구현하고,
  승인 표 12행 라우팅·needs_llm=false 무호출·policy=none 기본값·원인 분류 기반 상향·Pending 표시·CLI 지원 확인·장부 기록을
  합성 시험으로 통과한다. T7(실제 적용값 일치)은 이 단계에서 통과로 주장하지 않는다.
allowed_files:
  - harness/route.py, harness/routing_policy.json, harness/route_*.py(함수 수 제한 때문에 추가한 파일은 이 문서에 기록)
  - tests/test_harness_route_*.py (신규만)
  - 이 task 문서
forbidden_files: harness/runner.py·registry.py·champion.py·lineage.py(다른 작업 소유), 1단계 파일(harness/{contract,ledger,jsonio,queue,...}.py 수정 금지·공개 함수 호출만),
  card_condition/**, tools/**, 기존 tests/**, AGENTS.md, docs/agent/**, artifacts/**, data/**, 라벨·사진·모델·비밀 설정, .claude/**, 다른 plan 문서
contract:
  입력: route(contract, history, policy, runtime=None) — contract는 task_type·needs_llm·needs_vision·risk(+선택 escalation_level),
        history는 이전 실패 결과 목록(각 항목 cause·failure_kind·선택 xhigh_justified), runtime은 {context_size, budget_remaining},
        policy는 harness/routing_policy.json을 읽은 dict 또는 None.
  출력: 결정 dict(model·effort·escalation_order·policy_version·policy·reason·needs_llm …). 실제 적용값은 with_support가 applied·limitations로 덧붙인다.
  보존: stdlib만(Python 3.9+), 네트워크·LLM·`claude -p` 실행 없음(`claude --help`만 읽기 전용으로 허용), 런타임 상태는 호출자가 준 root에만 쓴다.
  정책 변경은 JSON만으로 가능해야 하며 코드 수정이 필요 없다(시험으로 확인).
  없는 정책·미등록 task_type·원인 분류 없음은 추정하지 않는다(기본값 Sonnet Medium + policy=none / 상향 안 함).
  설계에 없는 것 금지: 작업 실행, claude -p 호출, Supervisor, 예산 관리, 정책 최적화.
structure: 파일당 함수 정의 ≤7, 이 작업이 만든 공개 함수의 파일 내 호출 깊이 ≤2(구현 뒤 표를 채운다).
checks:
  - `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` 종료 코드 0 (1단계 55개 포함), `/usr/bin/python3`(3.9)도 같음
  - 변이 시험(상향 조건 제거·정책 누락 처리 제거 등)을 임시 복사본에서 실행해 시험이 잡는지 확인(원본 수정 금지)
  - ast 함수 수·호출 깊이, `git diff --check`, 허용 파일 대조, git status 깨끗
experiment: 없음. 합성 시험이며 모델 성능·정확도·토큰 절감 근거가 아니다.
handoff: 아래 "구조 표 / 인계" 절. 시험 대상 SHA는 그 절의 표.
```

## 구현 명세 요약

- `harness/routing_policy.json`: 판본 `routing-policy-v1`, 작업 유형 표 12행(`general_dev`, `complex_algorithm`, `image_analysis_general`, `silver_labeling`, `defect_analysis_precise`, `label_cross_validation`, `label_disagreement`, `misanalysis_general`, `repeated_failure_analysis`, `model_redesign`, `experiment_log_summary`, `deterministic`), 상향 순서, 기본값, 상향 허용·금지 원인 목록, Xhigh 단계.
- `route()`: 표 조회 → 기본 결정 → history의 실패를 `escalate()`로 같은 규칙에 따라 재적용(재시작 뒤에도 같은 결과).
- `escalate()`: 품질 관문 미달·검증 실패·해결되지 않는 불일치 + 원인 분류가 있고 transient가 아닐 때만 한 단계. Xhigh는 `xhigh_justified` + 예산 남음일 때 한 번. 최상위에서도 실패면 `pending=True`.
- `context_for_escalation()`: 상향 시 근거 키와 실패 결과만 통과(입력 필터).
- `probe_cli_support(run=...)`·`with_support()`: `claude --help` 파싱, 실제 적용값(`applied`)과 제한 사항(`limitations`) 기록, 미확인 값은 미확인으로 표시.
- `record_decision()`: 1단계 `ledger.append`로 `route_decision` 이벤트 기록(필드가 없으면 null).

## 구조 표 / 인계

### 결과

계약의 필수 시험을 모두 실제로 실행해 통과했다. 합성 시험이며 모델 성능·정확도·토큰 절감의 근거가 아니다. 이번 변경은 하네스 3~4단계에 쓰일 `route()` 라이브러리 구현이며 실험·학습·모델 호출은 없다. **T7(실제 적용값 일치)은 통과로 주장하지 않는다**: `applied.verified`는 항상 False이고 제한 사항에 `actual_application_unverified`가 들어간다.

### 대상 SHA와 실행 명령

| 항목 | 값 |
|---|---|
| 작업 계약 커밋 | `3c0560d` |
| 구현(`feat(harness)`) | `17cbd7a` (전체 SHA는 `git log`) |
| **시험 대상(구현 + 시험)** | `ac64cf504e06f7e0cae8683c195481b67bacb101` (`test(harness)` 커밋). 이 문서 커밋은 그 위에 문서만 추가(코드 변경 없음) |

| 명령 (cwd = worktree, 시험 대상 SHA에서 실행) | 종료 코드 |
|---|---|
| `PYTHONDONTWRITEBYTECODE=1 /Users/jueun/WebstormProjects/pokemon-card-condition/.venv/bin/python -m unittest discover -s tests -p "test_harness_*.py"` (Python 3.12.14) | rc=0, 83개 통과(1단계 55 + route 28) |
| 같은 명령, `/usr/bin/python3` (3.9.6) | rc=0, 83개 통과 |
| 같은 명령, `-p "test_harness_route_*.py"` | rc=0, 28개 |
| `git diff --check d582cc2 HEAD` | rc=0 |
| `git diff --name-only d582cc2 HEAD` | 허용 파일 안(이 문서·harness/route*.py·harness/routing_policy.json·tests/test_harness_route_*.py)만 |
| `claude --help` 직접 실행 1회(읽기 전용, `claude -p`·모델 호출 없음) | rc=0 |

실제 `claude --help`(설치본 2.1.310) 결과를 `probe_cli_support()`로 파싱한 값: `model_option=True`, `effort_option=True`, `effort_levels=[low, medium, high, xhigh, max]`, `model_examples=[fable, opus, sonnet]`. 따라서 이 설치본에서 `haiku`는 도움말 예시에 없어 "수용 여부 미확인", Opus+xhigh 조합의 실제 수용도 "미확인"으로 `limitations`에 기록된다(이 단계에서 판정 불가). `--help`에 이름이 있다는 것은 실제 적용의 증거가 아니다.

시험 파일(테스트 수): `test_harness_route_table.py` 7, `_escalate.py` 7, `_support.py` 7, `_record.py` 7(모두 ≤7), `_fixtures.py`는 시험 없는 공용 도구(승인 표 기대값을 문서에서 시험에 따로 옮겨 적음).

### 변이 시험(임시 복사본, 원본 수정 안 함)

scratchpad의 `mutate_route.py`가 저장소 복사본마다 소스를 한 군데 바꾸고 `test_harness_route_*.py`를 돌렸다. 27개 변이 중 26개를 시험이 잡았고 나머지 1개는 동치 변이(대조군)다. 포함한 변이: 원인 분류 없음·금지 원인·transient·미등록 원인 검사 제거, Xhigh 근거·예산·1회 제한 제거, 두 단계 상향, 최상위 처리·Pending 표시 제거, 항상 사용자 요청, 낡은 applied 유지, needs_llm=false 상향 허용·무시, deterministic 무시, 정책 없음 기본값 변경, policy=none 제거, history의 Xhigh 근거 무시, 미지원 effort 적용 유지, probe 실패 적용 유지, haiku 미확인 기록 제거, 알 수 없는 extras 허용, requested 필드 제거, 이벤트 이름 변경, 실패 전체·컨텍스트 전체 전달. 처음에는 "금지 원인 검사 제거"와 "history의 Xhigh 근거 무시" 2개를 시험이 놓쳐서, 시험을 보강(금지·허용 목록이 겹칠 때 금지 우선, 근거 없는 history에 예산만 있는 경우)해 잡히게 했다. 작업 중 한때 `_support` 시험 파일이 아직 만들어지지 않은 상태에서(명령 체인 오류) 변이 결과를 본 적이 있어, 파일을 만든 뒤 변이 시험을 전부 다시 돌렸다.

### 구조 표(ast 정적 측정)

| 파일 | 함수 정의 수 | 공개 함수 호출 깊이(이 작업 파일 안만 / 1단계 호출 포함, 현재 측정) |
|---|---|---|
| `harness/route.py` | 6 (`load_policy`·`_step`·`_valid`·`_choose`·`_base`·`route`) | `route` 2 / 2 (`route → _base → _choose`, `route → escalate → _eligible·_top`), `load_policy` 0 / 1 (`read_json`) |
| `harness/route_escalate.py` | 4 (`_eligible`·`_top`·`escalate`·`context_for_escalation`) | `escalate` 1 / 1, `context_for_escalation` 0 / 0 |
| `harness/route_support.py` | 5 (`_run_help`·`_block`·`probe_cli_support`·`_check`·`with_support`) | `probe_cli_support` 1 / 1, `with_support` 1 / 1 |
| `harness/route_record.py` | 1 (`record_decision`) | 0 / 2 (`record_decision → ledger.append → _hash_entry`) |

모두 함수 수 ≤7, 호출 깊이 ≤2(이 작업 파일 안)이다. 1단계 `ledger.append` 내부 깊이가 평탄화되면 `record_decision`의 1단계 포함 깊이는 1로 줄어든다. 통합 때 메인이 재측정한다. 재귀·동적 디스패치 없음.

### 구현 요약

- `harness/routing_policy.json`(판본 `routing-policy-v1`): 표 12행(승인 문서와 1:1), 상향 순서 3단계, Xhigh 단계, 기본값, 상향 허용 원인(`quality_gate_miss`·`verification_failed`·`unresolved_disagreement`)·금지 원인(`data_shortage`·`image_quality`·`code_error`). 이 JSON만 바꾸면 라우팅이 바뀐다(시험 `test_json_change_alone_changes_routing`).
- `route(contract, history, policy, runtime=None)`: 정책 구조 검사 → 표 조회 → needs_llm=false/LLM 미사용 유형이면 모델 없음 → history 실패를 `escalate()`와 같은 규칙으로 재적용(재시작해도 같은 결과). 정책 없음/구조 오류/미등록 task_type은 `policy="none"` + Sonnet Medium + 사유 기록.
- `escalate(decision, failure, xhigh_justified=False, budget_remaining=None, learning_value_high=False)`: 원본을 바꾸지 않고 새 결정을 돌려준다. 상향 시 낡은 `applied`·`limitations`를 지운다(새 값으로 다시 지원 확인해야 하므로).
- `context_for_escalation(context, evidence_keys, failure)`: 근거 키와 실패의 화이트리스트 필드만 통과, 나머지는 키 이름만 `dropped`로 남김.
- `probe_cli_support(run=None)` / `with_support(decision, support)` / `record_decision(root, decision, applied, extras)`: 위 계약대로. 장부 이벤트 이름은 `route_decision`, 같은 `root/ledger.jsonl`(큐와 같은 장부)에 이어 쓴다.

### 가정(구현자가 정한 것, 통합 때 확인)

1. `failure.cause` 값의 이름 6개는 정책 JSON에서 정한 것이다(승인 문서에는 "품질 관문 미달·검증 실패·해결되지 않는 불일치 / 데이터 부족·이미지 품질·코드 오류"라는 설명뿐). 호출자(3~4단계)가 같은 이름으로 분류해야 한다. 이름은 JSON에서 바꿀 수 있다.
2. 상향 순서에 없는 시작점(Haiku Low)은 실패 시 순서의 첫 단계(Sonnet Medium)로 올린다. 승인 문서에 이 경우가 명시돼 있지 않아 정한 해석이다.
3. Pending은 "상향 대상 원인으로 최상위(Opus High 또는 허용된 Xhigh)에서도 실패한 경우"에만 켠다. 데이터 부족·이미지 품질 같은 원인은 상향으로 풀리지 않으므로 Pending으로도 표시하지 않는다(그런 라벨의 처리는 호출자 몫). `request_user`는 Pending이면서 호출자가 준 `learning_value_high=True`일 때만 True다.
4. `route()`의 입력 중 `risk`·`needs_vision`·`context_size`·`budget_remaining`·계약의 `escalation_level`은 결정에 기록만 하고 모델 선택에는 쓰지 않는다(승인된 v1 정책에 이를 쓰는 규칙이 없고, 임의 규칙은 정책 추가가 되기 때문). `budget_remaining`은 Xhigh 허용 판정에만 쓰이며 "0 초과 숫자"를 예산 남음으로 본다(미제공=예산 없음). 1단계 `validate_contract`는 `context_size`·`budget_remaining` 필드를 허용하지 않으므로 `runtime` 인자로 따로 받는다.
5. 계약의 `needs_llm=true`여도 정책이 `{"llm": false}`(deterministic)이면 모델을 쓰지 않는다. 계약이 `needs_llm=false`이면 task_type과 무관하게 쓰지 않는다.
6. 정책 파일 JSON이 깨지면 `load_policy`는 `ValueError`로 멈춘다(추정하지 않음). 파일이 없으면 None. `route`에 구조가 틀린 dict를 직접 넘기면 `policy=none`으로 처리한다.

### 미검증 · 한계

- **실제 모델·effort 적용은 확인하지 않았다.** `claude -p --model --effort`를 실행하지 않았다. 3~4단계에서 실제 실행 뒤 `applied.verified=True`로 올리고 장부 기록을 대조해야 T7을 판정할 수 있다.
- Haiku·Opus+Xhigh의 실제 수용 여부, `--help`의 effort 목록이 모델별 수용을 뜻하는지는 미확인.
- `probe_cli_support`의 도움말 파싱은 설치본 2.1.310의 형식에 맞췄다. 도움말 형식이 바뀌면 `model_examples`·`effort_levels`가 None(미확인)으로 떨어지고 제한 사항으로 기록되며, 옵션 줄 자체를 못 찾으면 `*_option_missing`이다(조용히 통과하지 않음).
- 정책의 정확도·토큰 절감 효과는 측정되지 않았다(승인 문서 1-6).
- 호출 깊이는 정적 측정이며 1단계 평탄화 이후 통합 상태에서 재측정이 필요하다.
- 독립 Opus 검증은 하지 않았다(메인이 따로).

### 리스크

- `cause` 이름 불일치: 호출자가 다른 이름을 쓰면 상향이 일어나지 않는다(안전 방향, 기계적 상향 금지 원칙).
- `record_decision`은 1단계 `ledger.append`의 flock·마지막 줄 검사에 의존한다. 장부 마지막 줄이 손상되면 `LedgerError`로 쓰지 않는다(시험으로 확인).
- 같은 `ledger.jsonl`에 큐 이벤트와 `route_decision`이 섞인다. 1단계 장부 검증기 `verify`는 이벤트 종류를 보지 않아 해시 체인은 유지되지만, 큐 쪽에 이벤트 이름으로 장부를 해석하는 코드가 있는지는 이번에 확인하지 않았다.

### 롤백

이 브랜치의 `3c0560d` 이후 커밋(`17cbd7a`, `ac64cf5`, 문서 커밋)을 되돌리거나 브랜치를 버리면 된다. 새 파일만 추가했고 1단계·기존 파일은 수정하지 않았다. 런타임 상태는 시험의 임시 디렉터리에만 썼다.

# 하네스 route() — 모델·Effort 라우팅 (2026-11-27)

```text
task_id: harness-route-20261127
owner: Claude (메인 세션이 계약 작성, 구현은 Sonnet 하위 에이전트, 독립 Opus 검증은 메인이 따로)
status: assigned
base_sha: d582cc2 (전체 SHA는 `git rev-parse d582cc2`)
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
handoff: (구현 후 채움)
```

## 구현 명세 요약

- `harness/routing_policy.json`: 판본 `routing-policy-v1`, 작업 유형 표 12행(`general_dev`, `complex_algorithm`, `image_analysis_general`, `silver_labeling`, `defect_analysis_precise`, `label_cross_validation`, `label_disagreement`, `misanalysis_general`, `repeated_failure_analysis`, `model_redesign`, `experiment_log_summary`, `deterministic`), 상향 순서, 기본값, 상향 허용·금지 원인 목록, Xhigh 단계.
- `route()`: 표 조회 → 기본 결정 → history의 실패를 `escalate()`로 같은 규칙에 따라 재적용(재시작 뒤에도 같은 결과).
- `escalate()`: 품질 관문 미달·검증 실패·해결되지 않는 불일치 + 원인 분류가 있고 transient가 아닐 때만 한 단계. Xhigh는 `xhigh_justified` + 예산 남음일 때 한 번. 최상위에서도 실패면 `pending=True`.
- `context_for_escalation()`: 상향 시 근거 키와 실패 결과만 통과(입력 필터).
- `probe_cli_support(run=...)`·`with_support()`: `claude --help` 파싱, 실제 적용값(`applied`)과 제한 사항(`limitations`) 기록, 미확인 값은 미확인으로 표시.
- `record_decision()`: 1단계 `ledger.append`로 `route_decision` 이벤트 기록(필드가 없으면 null).

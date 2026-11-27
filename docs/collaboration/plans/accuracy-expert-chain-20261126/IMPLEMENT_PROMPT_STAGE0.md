# 0단계 기록 도구 구현 프롬프트 (2026-11-27)

아래 블록을 새 세션에 그대로 붙여 넣는다.

```text
작업 폴더: /Users/jueun/WebstormProjects/pokemon-card-condition. 한국어로 보고한다.

[목표] 카드 상태 모델의 누락·오탐을 "정확히 셀 수 있게" 만드는 기록 도구를 구현한다. 이번 작업으로 모델 성능은 바뀌지 않는다. 분모·제외 건수·판정 주체(사람/AI)가 기록에 보이게 될 뿐이다. 성능 개선이라고 보고하지 않는다.

[먼저 읽기 — 끝까지, 잘리면 나눠서]
1. AGENTS.md 전체, docs/AGENT_START.md, PAIR_CODING.md 전체, COMMON_EXPERIMENT_RECORDS.md 전체, docs/agent/QUALITY_RULES.md의 regression-for-every-fix·label-screen-round-trip·zero-denominator-unmeasured
2. docs/collaboration/plans/accuracy-expert-chain-20261126/07-experiment-ops.md §4 전체(설계 정본: 4-0 구조 제한, 4-1 사이드카 형식, 4-2~4-5 설계·회귀, 4-6 task 계약)
3. 같은 폴더 08-lead-roadmap.md §3(R0~R5)·§4, DECISIONS.md

[할 일 — 이 순서]
- T0: 07 §4-1 형식을 docs/collaboration/tasks/record-sidecars-20261127.md에 task 계약(task_id, base_sha, allowed_files, checks, structure 전/후 함수 수·호출 깊이)으로 고정하고 커밋한다. 이것이 T1~T3·T5의 공통 계약이다.
- T0 뒤 아래 넷은 파일이 겹치지 않으므로 병렬 가능. 각자 PAIR_CODING.md 규칙대로 브랜치·worktree를 나누고, 모든 소스 수정은 `./develop -- <수정 명령>` 안에서 한다.
  - T1 행 변환기 tools/zone_rows.py (07 §4-3, 회귀 1~4)
  - T2 실행기 사이드카 card_condition/experiment_sidecars.py + experiment_record.py에는 호출 2줄과 dict 1칸만 (07 §4-2, 회귀 1~5). experiment_record.py는 T2만 소유
  - T3 판정 주체 관문 tools/rater_gate.py (07 §4-4, 회귀 1~4). pass1·final 등 모든 AI 파일과의 일치 수를 함께 남긴다(B2: pass1 50/64, final 64/64)
  - T5 사진 묶음 통계 tools/diagnostics/cluster-stats-20261127/stats.py (07 §4-5 X6, 05 2-2의 DEFF 1.33·1.44 재현)
- 여유가 있으면 T7 연속 미달 계수(07 §4-5 X7, 우선 하).

[하지 않을 것]
- T4(새 라벨 화면)·T6(사전 판정 도구)는 이번 범위가 아니다. T4는 정본 문구(R8) 갱신 뒤, T6은 T2·T5 뒤에 한다.
- "AI 의심" 처리(D-7)는 미결정이다. 행에서 빼지 말고 row_facts.rater_kind로 표시만 한다.
- 학습·추론·모델 비교, `./experiment`, `./review`, 외부 AI(Gemini·Codex) 호출, 라벨 수정 금지. d2_rows.py, size.py, 기존 시험 파일은 고치지 않는다.
- 이미 초과한 파일(experiment_record.py 함수 17개, tests/test_experiment_record.py)에 함수를 더하지 않는다. 새 시험은 새 파일에 둔다.
- main 통합·push는 하지 않는다. 끝나면 고지하고 사용자 승인을 받는다.

[완료 기준]
- 각 task의 07 회귀 항목이 실제 명령과 종료 코드로 통과한다. 기존 tests/test_experiment_record.py·tests/test_acceptance_caps.py는 그대로 통과한다.
- 실제 자료가 없는 worktree에서는 실자료 회귀를 "미검증"으로 표시하고 건너뛴다. 통과했다고 쓰지 않는다.
- 사이드카가 없는 과거 계획·결과는 바이트 단위로 그대로다.

[보고]
결론 → 근거 → 쉬운 설명 순서로 쓴다. task별로 변경 파일, 핵심 diff, 실행한 검증 명령·종료 코드·대상 SHA, 미검증 항목, 리스크, 롤백(새 파일 삭제 + git revert <SHA>)을 적는다. 적용한 품질 규칙과 못 지킨 규칙을 적는다. 에튜 포인트 1~3개를 붙인다.
```

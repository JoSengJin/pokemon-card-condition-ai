# push-policy-fix-20261128 — 통합·push 정책(127c529) 결함 G1~G6 보완

```text
task_id: push-policy-fix-20261128
owner: Claude
status: ready_for_review
base_sha: 127c529 (claude/push-policy-20261128)
branch: claude/push-policy-fix-20261128
goal: 상시·작업 단위 push 승인으로 읽히는 문구와 어긋난 참조를 없애고, main 커밋 전 승인 단계를 스킬에 넣는다. 새 권한·새 도구 없음.
allowed_files: AGENTS.md, PAIR_CODING.md, docs/AGENT_START.md, .agents/skills/pair-coding/SKILL.md, 이 문서
```

사용자 결정 D6(정책 결함 먼저, AGENTS.md 한도 상향은 미승인)의 이행이다. 이 문서는 승인이 아니며 통합·push 승인을 요청하지 않는다.

## 결함별 변경

| 결함 | 변경 | 위치 |
|---|---|---|
| G1 | "기존 push 상시 승인 범위를 따른다" → "열기·통합 커밋과 push는 AGENTS.md의 SHA별 사용자 직접 승인을 받은 뒤에만" | docs/AGENT_START.md pair-coding 행 |
| G2 | 열기 4번: 계약을 main이 아닌 별도 브랜치에 커밋해 SHA를 만든 뒤 main 반영·origin push를 각각 SHA 고지 후 직접 승인. 승인·반영 전에는 열린 작업이 아님 | SKILL.md §1-4 |
| G3 | PAIR_CODING.md 줄 번호 참조 전부(137·118·66–74·92–101·145·93·94·130–152·12–14·86·119행)를 절 제목·항목 이름 참조로 교체. 기존 오류 "150행의 금지"는 SKILL §6 "막히면 우회하지 않는다"로 정정 | SKILL.md |
| G4 | 작업 브랜치 문장에 "push는 포함되지 않으며 §5 '승인된 작업 브랜치만 push' 조건을 넓히지 않는다" 한 구절 | PAIR_CODING.md 검증한 main의 push 절 첫 단락 |
| G5 | "원격 반영이 승인된 작업만 일반 push" → "AGENTS.md의 SHA별 사용자 승인을 받은 SHA만". 롤백 push도 같은 승인 대상(§6 revert 문장·push 절 마지막 문장). 관제 도구 승인 장부 문구에 "장부 기록은 승인이 아니며 SHA별 사용자 직접 승인을 대신하지 않는다" | PAIR_CODING.md §6-8, §6 롤백 단락, §7, push 절 |
| G6 | 스킬 §0-6 신설(main 커밋·cherry-pick·push는 사용자 직접 연 세션의 직접 메시지 턴에서만, 각각 직접 승인, 하위·무인·예약·출처 불명 세션은 실행·승인 요청 금지). 통합 4번 "승인 먼저": 전달 SHA 범위·기준 main 전체 SHA·변경 파일·검사·되돌리는 법을 고지하고 승인 범위를 "고지한 main 위의 cherry-pick과 `status: integrated` 커밋"으로 명시, main이 바뀌면 재승인. 통합 6번: push는 새 전체 SHA를 알리고 별도 승인 | SKILL.md |

## AGENTS.md 크기와 하네스 절 수용

- 전: 16,343B → 후: 16,002B (한도 <16,384B 유지, 한도·시험 기대값 변경 없음).
- 줄인 곳은 보호 해시 대상이 아닌 줄뿐이다(아래 "의미 변경 여부"). 보호 줄 46개의 해시는 전부 그대로이며 BASELINE_RULE_HASHES 갱신 없음.
- 하네스 절(아래 제안문, 371B)을 끝에 붙인 가정치: 16,373B (<16,384, 여유 11B). 임시 복사본에서 시험 통과 조건(크기·보호 해시 포함·`review_rules` 2,142B <3,000B)을 확인했다. 이 브랜치에는 넣지 않았다.

압축한 줄(의미 변경 없음, 다른 문서와 중복이거나 어순·접속만 정리):

1. 공통 입구 문단: "작업 종류가 겹치면 필독 문서를 합친다"(AGENT_START.md 3번 중복)와 "나눠" 삭제.
2. review-rule 설명 문단: "일반 구현 에이전트와 구분"을 AGENT_START.md(격리 하위 Codex 구분 문장)로 가리키도록 줄임. ID 보존 규칙·추출 계약 갱신 문장은 유지.
3. 스킬 사용 줄(보호 아님): "Superpowers 7.0.1"(AGENT_START.md 중복)·"승인·잠금·역할·통합 규칙"→"이 파일의 규칙"(더 넓은 우선 문구).
4. 헤더 날짜 표기 순서, 섹션 사이 빈 줄 정리.
5. "짧은 요청 해석" 요약 불릿의 군더더기 어휘(예: "현재", "골라", "상대가"). 규칙 수·내용·`test_quality_rule_routes`의 정규식 문구는 유지.

### 하네스 절 제안문(0da3cb7의 짧은 절을 대체할 형태, 이 브랜치에는 미반영)

```markdown

## 자율 개발 하네스 (D-1, 2026-11-27 승인)
하네스 무인 실행에 한해 [운영 규칙](docs/agent/HARNESS_RULES.md)이 "자동 재시도 금지"·"세션 상시 깨우기 금지"·"최종 응답 이후 자동 실행 약속 금지"보다 우선하며 대화형 에이전트의 미래 작업 약속은 허용하지 않는다. 다른 제한은 그대로다.
```

주의: 합칠 때 하네스 브랜치의 기존 두 줄 절과 충돌하므로 위 문안으로 교체하고, 합친 파일이 16,384B 미만인지 `wc -c`로 다시 확인한다. 여유는 11B뿐이라 AGENTS.md에 다른 글자를 더하면 초과한다.

## 시험

- `PYTHONPATH=tests:. python -m unittest test_agent_document_routes test_quality_rule_routes test_agent_review_rules test_agent_input_limit_docs` → 18개 통과(로그 `.../scratchpad/logs/d6-doc-tests.log`).
- 하네스 절 포함 가정 파일 시험: `.../logs/d6-harness-sim.log`(크기·보호 해시·review_rules).
- 미실행: 전체 suite, pair-control TS 시험(관제 도구 코드 미변경, 문서 문구 결합 없음을 grep으로만 확인).

## 구조·승인 확인

- 함수 수·호출 경로: 코드 파일 변경 없음(문서만).
- 새 권한·승인·도구 없음. push·main 통합 안 함.

## 롤백

- `git revert <이 브랜치 커밋>`: 127c529(P) 상태로 돌아간다. P의 AGENTS.md "통합·push 승인(상시 승인 폐지)"와 PAIR_CODING.md "상시 push 승인 폐지·과거 문구 무효" 선언이 그대로이므로 상시 승인이 되살아나지 않는다. 다만 G1~G6의 모호한 문구(예: 스킬의 "기존 push 승인 범위", 줄 번호 어긋남)는 되돌아온다.
- 127c529 이전(d14686d 이전)까지 되돌리면 AGENTS.md의 상시 승인 문장이 복구되므로 금지한다.

## 잔존 문구(저장소 전체 grep, artifacts 제외)

- 선언 문장으로만 남음(의도): AGENTS.md "상시 승인 폐지", PAIR_CODING.md "상시 승인 폐지".
- 활성 규칙 문서에는 상시·작업 단위 push 승인 표현 없음.
- 보관·과거 기록(수정 안 함, PAIR_CODING push 절이 "과거 문서의 상시 push 승인 문구는 무효"로 선언): docs/collaboration/CLAUDE_HANDOFF_20261104.md, CODEX_RETURN_HANDOFF_20261031.md, reports/{agent-doc-loading-20261118.md, codex-continuous-development-20261026.md, main-pipeline-20261029.html, pair-control-integration-20261106.html, physical-card-uncertainty-20261026.md}, tasks/{claude-handoff-20261104, corner-d3-miss-fa-critical-20261120, e2-review-remaining-20261120, surface-globalmix-gradient-recording-20261108}.md, docs/history/CODEX_MAIN_HANDOFF_PREP_20261113.md. 이 중 corner-d3·e2-review 두 task는 "`git push origin main`(상시 승인)"을 담고 있어 재사용 시 위험하다(별도 정리 결정 필요).
- 관제 도구: tools/pair-control(README·UI의 "일반 push만", 승인 장부 설명)은 코드·문서 미수정. 장부가 브랜치 단위 push 승인을 기록할 수 있다는 점은 PAIR_CODING §7 문구로만 한정했다.

## 미확인

- 스킬 새 문구가 실제 세션에서 동작하는지(실행 시험 없음).
- 열기 계약의 "별도 브랜치" 방식이 pair-control이나 기존 선점 흐름(§2 open 탐색)과 충돌하는지(관제 도구 미검토).

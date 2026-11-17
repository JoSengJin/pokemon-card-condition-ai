# 에이전트 문서 로딩 개선 · 2026-11-18

개발 진척률 78/100 (usable-card-analysis-v1.13, 점수/배점 변경 없음). 이번 성과는 지침 보존·로딩 경로·문서 탐색 개선이며 모델 성능 개선이 아니다.

## 결과와 핵심 diff

- AGENTS 기존 지침·승인 bullet 46개를 모두 보존했다. 과거 v1.0의 문자 참조만 현재 정본의 버전을 따르도록 바꿨다. 일반 push 상시 승인, 역할 교대/승계, 사람 라벨/unknown, 잠금, 입력 격리, 호출·재시도 제한은 보존했다.
- 하위 Codex 규칙은 문장 prefix 대신 8개 고정 ID로 읽는다. 누락·중복·미등록·빈 본문·경계 오류는 backend 호출 전에 거부한다. 반환 규칙 본문은 기존 2,142 bytes와 동일하며 32,000 byte 입력 상한·API/CLI 격리는 그대로다.
- README의 전체 원문은 보관했다. 상대 Markdown 링크만 새 위치에 맞췄다. 루트에는 현재 정본과 공통 입구를 두며 과거 점수·버전을 현재 값처럼 복사하지 않는다.
- 공통 실험 계약의 자동 검토 후반부 원문 전체를 docs/agent/AUTO_REVIEW_CONTRACT.md로 분리했다. 날짜별 보완도 현재 보호 조건이며 자동 검토 작업에서 전체를 필독한다.
- docs/AGENT_START.md는 작업별 문서·승인·실제 상태의 정본을 찾는 입구다. CLAUDE.md의 @AGENTS.md로 Claude와 Codex가 같은 원문을 읽는다. 일반 구현 경로와 탐색 금지 하위 검토를 구분했다.

| 문서 | 변경 전 bytes | 변경 후 bytes |
|---|---:|---:|
| AGENTS.md | 12,942 | 14,507 |
| README.md | 94,532 | 4,189 |
| COMMON_EXPERIMENT_RECORDS.md | 39,348 | 15,010 |

## 변경 파일

- `AGENTS.md`
- `CLAUDE.md`
- `CLAUDE_HANDOFF_20261024.md`
- `COMMON_EXPERIMENT_RECORDS.md`
- `README.md`
- `card_condition/cross_review_auto_sources.py`
- `docs/AGENT_START.md`
- `docs/agent/AUTO_REVIEW_CONTRACT.md`
- `docs/collaboration/tasks/agent-doc-loading-20261118.md`
- `docs/history/README.md`
- `docs/history/README_BEFORE_AGENT_GUIDE_20261118.md`
- `tests/test_agent_document_routes.py`
- `tests/test_agent_review_rules.py`
- `tests/test_cross_review_high_fixes.py`

- 최종 검사/인계를 위한 본 보고서와 task 상태 기록.

## 실행 검증

검증 소스 SHA: `d160a859b4d53c1dbe1690380348d75d24434d19`. 상세 테스트 결과·실패 ID·원문 보존 대조는 ignored `artifacts/agent-doc-loading-20261118/verification.json`과 로그에 기록한다.

- main-full: 1032 tests / OK
- worktree-full-pinned: 1031 tests / FAILED (errors=3)
- initial-full: 1030 tests / FAILED (failures=10, errors=5)
- targeted: 11 tests / OK
- mock-cross-review: 207 tests / OK
- rules-red: 5 tests / FAILED (failures=10)
- routes-red: 5 tests / FAILED (failures=4, errors=2)

- rules-red/routes-red는 새 동작을 구현하기 전 의도한 실패 확인이며 최종 상태가 아니다. main-full 1,032 tests / OK가 통합 후 최종 결과다.
- git diff --check, 기존 46개 지침·승인 원문 대조, 하위 8개 규칙 byte 일치, 공통 실험 계약 전체와 보관 README 원문 보존 대조, 문서 경로·필독 진입점 검사를 수행했다.
- 별도 읽기 전용 검토에서 중대 누락·오류 없음. 신규 문서·파서 검사 11개도 독립 확인했다.
- worktree 최초 baseline 교차 검토에서 ignored nemotron 설정 누락으로 42 errors가 발생했고, 계정·키를 복제하지 않은 합성 설정 후 207 tests가 통과했다.
- 최초 전체 검사는 문서 검사의 ignored 증거 링크 2건과 Homebrew Python의 격리 자식 실행 실패가 포함됐다. 문서 검사는 추적 경로와 ignored 역사 증거를 구분했고, 격리 로그의 posix_spawn 오류를 확인한 뒤 기본 checkout과 동일한 Python 런타임·검증된 core 패키지로 재검사했다. 격리 가드/실행기 코드를 바꾸거나 제한을 풀지 않았다.

## 구조와 미검증

- production cross_review_auto_sources.py 함수 6→6. review_context→review_rules 1전이, 파서 내 새 사용자 정의 호출 전이 없음. 신규 테스트 파일 함수 정의는 7개/5개다.
- 기존 test_cross_review_high_fixes.py는 oversized 입력 fixture 1곳만 새 ID 문서에 맞췄다. 함수 38→38이며 기존 구조 제한 초과는 남아 있다. 범위 밖 전체 테스트 분할을 추가하지 않았다.
- 실제 Claude/Codex 앱의 새 세션에서 로딩/준수율을 측정하지 않았다. 현재 열린 세션에는 새 원문을 다시 읽히거나 다음 세션에서 /memory로 확인해야 한다.
- 실제 Gemini·NVIDIA·추가 Codex CLI 요청과 실카드 학습/사진 추론·모델 비교는 실행하지 않았다. 테스트의 임시 합성 worker/텐서 실행은 모델 성능 평가가 아니다. 새 FN/FP·일반화 개선·호출 절감률은 측정하지 않았다.
- HTML 경로: artifacts/agent-doc-loading-20261118/index.html. 브라우저 보안 정책이 file 프로토콜을 차단해 열기·렌더는 미확인이다. 우회하지 않았으며 opening.json에 기록했다. 동일 내용의 Markdown 보고서를 앱에서 확인할 수 있다.

## 리스크와 롤백

- 새 parser는 AGENTS 파일이 존재하는데 필수 ID가 잘못됐으면 이전처럼 조용히 일부 지침만 전달하지 않고 중단한다. 기존 구형 worktree에 코드만 복사하지 말고 AGENTS와 같은 커밋으로 가져와야 한다. AGENTS 파일이 없는 합성 fixture의 기존 빈 문자열 동작은 유지한다.
- 기존 지침 내용 자체를 바꾸는 미래 작업은 보존 해시 테스트를 실패시킨다. 이는 승인·의미 변경을 검토한 뒤 테스트를 함께 갱신하기 위한 의도된 보호다.
- 과거 README의 artifacts 링크는 기존 ignored 증거이며 구현 worktree에 복제하지 않았다. 경로 해석은 그대로지만 파일 존재를 해당 worktree에서 증명하지 않는다.
- 롤백은 진행 중 실행과 후속 의존을 확인한 뒤 이번 작업 커밋(최종 기록, d160a85, 8a2d333)을 역순으로 ./develop -- git revert에 전달하고 관련 검사를 거쳐 일반 push한다. force/reset/라벨·모델·기준 복원은 필요 없다.
- 이번 worktree는 최근 통합 작업의 롤백 확인용으로 유지한다. 다른 기존 worktree는 현재 사용/고유 증거·전체 통합 여부를 확인하지 않아 변경하지 않았다.

# 과거 안내와 현재 입력·호출 계약 분리 · 2026-11-18

개발 진척률 78/100 (usable-card-analysis-v1.13) 유지. 과거 안내를 보존하고 현재 계약을 한곳으로 모았다. **Claude 검증은 부분 확인 그대로이며, main 후보 전체 테스트 1,036개가 통과했다.** 모델 품질·독립 일반화 개선을 평가한 작업이 아니다.

## 핵심 diff와 변경 파일

- AUTO_DEVELOPMENT 초기 안내 전체는 history 보존본으로 이동하고 root에는 현재 계약을 참조하는 사용 안내를 뒀다. 과거 입력 크기·작업 수·직접 실행 설명을 현재 권한으로 읽지 않도록 구분했다.
- AUTO_REVIEW_CONTRACT의 기존 app-server 전송·입력 정책을 상단 현재 계약으로 옮겨 한 번만 정의했다. 기존 timeout·누적 예산 예약·미확인 usage 차단·공통 실험 제한은 유지했다. 날짜별 다른 보호 문장은 보존했다.
- 입력/호출 가드·기존 승인·사람 정답·라벨·평가 기준·진척 수치는 변경하지 않았다. 이번 재개 이후 테스트 파일·기대값·Claude 결과를 수정하지 않았다.

- `AUTO_DEVELOPMENT_20261020.md`
- `docs/agent/AUTO_REVIEW_CONTRACT.md`
- `docs/collaboration/tasks/agent-input-limit-clarity-20261118.md`
- `docs/history/AUTO_DEVELOPMENT_BEFORE_LIMIT_CLARITY_20261118.md`
- `docs/history/README.md`
- `tests/test_agent_input_limit_docs.py`

- 본 결과 보고서와 task 완료 기록.

## 실행 검사

검증 소스: `8896305fb060193678c9f62471b925ca2130860e`. main에 커밋 전 후보를 적용하고 `git write-tree`가 소스 커밋 tree와 정확히 같음을 확인했다. 이 상태에서 기본 checkout의 기존 가상환경·실자료를 사용해 아래 기존 전체 명령을 변경 없이 실행했다. 잠금은 부모 검증 프로세스가 유지했고 테스트 자식에는 별도 fixture용 잠금 변수를 주입하지 않았다.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

- 전체 검사: 1,036 tests / OK, process exit 0, 135.558초. 결과는 main-full-suite.log/json에 보존한다.
- 앞선 문서·파서 회귀 15 tests / OK, mock 교차 검토 207 tests / OK. 이 수치는 이전 실제 실행 로그이며 이번 재개에서 그 검사들을 반복했다고 주장하지 않는다.
- 새 문서 검사 4개는 문서 수정 전 실패(2 failures, 2 errors)를 확인하고 수정 후 통과했다. 기존 테스트를 완화하지 않았다. 새 테스트 파일 함수 정의 수는 4개다. 런타임 함수·호출 경로 변경 없음.
- git diff --check, 보호 파일 SHA, 이전 실패 로그 28개 SHA, 기존과 동일한 prompt SHA, 이번 재개 후 전체 테스트 파일 SHA 불변을 대조했다.

## 실제 Claude 결과 — 부분 확인 유지

이 문서 정리 전 실패 세션: `416edb51-7e34-4064-b277-2211c136a089`. 정리 후 최초 새 세션: `33427d37-766f-4918-bdc3-7b9f9004df31`. 실제 기본 모델은 claude-sonnet-5-5, 기존 Pro 로그인·동일 과제·동일 계약·Read/Glob/Grep·plan mode·최대 16턴/600초를 유지했다. UUID·관찰 로그 경로 외 CLI 인자가 이전과 같음을 대조했다. 정답·필독 목록·실패 내용을 프롬프트에 넣지 않았다.

- CLI 완료: exit 0, 13 agentic turns, 54.857초.
- 관찰 hook의 CLAUDE 시작 로딩·AGENTS import와 성공한 Read 반환 본문으로 필독 11/11을 대조했다. Read 11회(배정 계약 포함), Glob 1회, 도구 오류 0개다. 과거 보관본은 읽지 않았다고 응답했다.
- 실제 응답 92행:

> 입력 상한은 프롬프트 32,000 bytes입니다. 정확한 수치는 `AUTO_REVIEW_CONTRACT.md` §현재 입력·호출 계약이 정본입니다.

- 예전 48KB 현재 상한 주장은 이번 첫 응답에서 재현되지 않았고 숫자 32,000은 맞았다. 그러나 사전에 정한 모든 단계·경계값 포함의 명시를 최종 응답에서 확인하지 못해 `partial_confirmation_not_full_pass`로 유지했다. 완전 통과·일반적 해결·문서 중복이 유일한 내부 원인이라는 주장을 하지 않는다.
- 이 재개 요청 이후 새 모델 호출은 0회다. 이전 승인 범위에서 실행한 위 Claude 1세션 외 추가 질문·resume·재실행, Codex CLI·Gemini·NVIDIA·자동 검토·실카드 학습·사진 추론은 없다.
- raw response, read-audit.json, semantic-audit.json, preregistered.json은 보존했다. 현재 verdict를 테스트 통과 수와 합쳐 올리지 않았다.

## 보존·리스크·롤백

- 이전 `artifacts/agent-doc-live-20261118/`의 28개 원시/판정 근거는 변경하지 않았다. 새 근거는 별도 `artifacts/agent-input-limit-clarity-20261118/`에 보존한다. 키·계정·원시 세션 로그는 Git에 올리지 않는다.
- 보호한 AGENTS/CLAUDE/공통 입구/공통 실험 계약/PAIR_CODING/라벨/진척 기준·JSON/자동 검토 가드는 기존 SHA와 같다. 검증용 과제·이전 실패 보고서도 변경하지 않았다.
- 이번 변경은 문서와 기존에 추가된 문서 회귀 검사뿐이다. 과거 안내를 사용하던 사람은 current 계약 링크를 따라야 한다. 과거 보존본은 현재 실행 지침이 아니다.
- Claude의 모든 미래 세션·GUI·실제 실행 중 준수와 입력 경계의 모델 해석은 미확인이다. 전체 테스트 통과가 이를 대신하지 않는다.
- 롤백은 최종 기록 커밋과 문서 정리 통합 커밋을 역순 `./develop -- git revert <SHA...>` 후 검사·일반 push한다. 원래 작업 브랜치 소스는 54e39bb/8896305다. 실제 세션 사용량과 원시 실패 근거는 롤백하거나 삭제하지 않는다.
- 이번 checkout은 최근 완료 작업의 롤백 확인용으로 유지한다. 다른 worktree는 미통합/사용/고유 증거가 미확인인 상태에서 제거하지 않는다.

## 통합·HTML 인계

main 통합 커밋: `50f784d0ae629aa87b0aa12776a275a26e00490f` (문서 소스 적용·전체 검증). 최종 기록 커밋과 origin/main 대조 결과는 종료 시 별도 기록한다. 허용한 일반 push만 사용하며 force나 이력 재작성은 하지 않는다.

HTML: `artifacts/agent-input-limit-clarity-20261118/index.html`. 네이티브 파일 열기 요청은 queued 응답이며 실제 렌더는 미확인이다. opening.json에 기록했고, 이전에 차단된 브라우저 file 프로토콜을 우회하거나 재시도하지 않았다. 실제 결과와 같은 Markdown 보고서를 함께 제공한다.

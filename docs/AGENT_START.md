# Codex·Claude 작업 시작과 필독 경로

이 문서는 현재 상태와 계약을 찾는 공통 입구다. 작업·실험·외부 호출 권한을 새로 부여하지 않는다. 기존 승인 범위를 줄이거나 확대하지 않는다. AGENTS.md의 모든 공통 제한과 이번 작업에 해당하는 상세 계약을 함께 적용한다.

## 시작 순서

1. [AGENTS.md](../AGENTS.md) 전체를 읽는다. Codex는 프로젝트 지침으로 읽고, Claude는 루트 [CLAUDE.md](../CLAUDE.md)의 `@AGENTS.md`로 같은 원문을 읽는다. 수동 전달·이전 버전·자동 하위 작업은 실제 전달된 내용을 확인한다. 링크 자체는 파일 본문이 아니다.
2. 현재 배정 task의 `task_id`, owner, status, base_sha, branch, allowed_files, read_docs, checks와 실제 Git 상태를 확인한다. 계약 위치는 배정 프롬프트나 관제 기록을 따른다. 날짜가 최신이라는 이유로 다른 작업을 인수하지 않는다.
3. 해당 작업의 기존 승인·금지·호출 한도와 필요한 아래 문서를 읽는다. 여러 종류의 작업이면 행을 합친다. 실제 원문이 없거나 충돌하면 그 의존만 보고하고 승인된 독립 작업을 진행한다.
4. 시작 전과 검증·통합 전 실제 상태를 다시 대조한다. 도구 출력에 truncated/생략 표시가 있으면 해당 파일을 제목/범위별로 나눠 끝까지 읽는다. 한 번에 여러 긴 문서를 출력하고 일부만 전달받은 상태를 전체 확인으로 취급하지 않는다.

## 작업별 필독

| 작업 조건 | 먼저 읽을 원문 | 놓치면 안 되는 경계 |
|---|---|---|
| 코드 구현·테스트·페어코딩 | [PAIR_CODING.md](../PAIR_CODING.md) 전체 + 배정 task + 관련 호출자·테스트 | 파일 소유권, 함수 수·호출 깊이, checkout 격리, main 담당 |
| 모델·worker 수정 또는 새 실험 | [COMMON_EXPERIMENT_RECORDS.md](../COMMON_EXPERIMENT_RECORDS.md) 전체 + [OBSERVATION_CONSENSUS_20261011.md](../OBSERVATION_CONSENSUS_20261011.md) + 사전 계획·대조 근거 | ./develop 잠금, ./experiment, 변수 하나, 학습/평가 분리, 실제점·필수 cohort 보호 |
| 사람 라벨·정답 의미·검토 화면 | [LABELING_PROTOCOL.md](../LABELING_PROTOCOL.md) 전체 + 해당 사진·사람 응답·현재 계약 | 완료 재요청 금지, unknown 보존, 모델 오답으로 사람 정답 변경 금지 |
| 자동 검토·실험 연결·오류 재개 | 공통 실험 계약 + [AUTO_REVIEW_CONTRACT.md](agent/AUTO_REVIEW_CONTRACT.md) 전체 + [자동 개발 안내](../AUTO_DEVELOPMENT_20261020.md) + 실제 journal | 기존 승인·무료 가드·입력 예산, 결과 불명 재요청 금지, 저장 응답 재사용 조건 |
| 성과·진척 보고 | [PROGRESS_CRITERIA.md](../PROGRESS_CRITERIA.md) 전체 + [development-progress.json](../development-progress.json) + [HTML_REPORTING.md](collaboration/HTML_REPORTING.md) | 현재 버전·점수 정본, 고정 배점, 이번 검사와 과거 성능 구분 |
| 통합·원격 반영·역할 교대·worktree 정리 | PAIR_CODING.md 전체 + 배정 계약·승인 장부·전달 SHA | 기존 일반 push 승인 유지, force 금지, 승인 승계 조건, 실행 중·고유 증거 보호 |

## 현재 상태의 정본

- 다음 개발 순서: AGENTS.md가 지정한 소비 프로젝트 `CONDITION_ANALYSIS_TODO.md` 상단과 현재 배정 task. 소비 프로젝트의 실제 경로는 [로컬 경로 설정](../README.md#로컬-경로-설정)을 따른다. 없으면 있다고 추정하지 않는다.
- 현재 역할·파일 점유·승인: 배정 계약과 실제 관제 기록·Git·잠금 상태. [PAIR_CODING.md §7](../PAIR_CODING.md#7-메인-역할-교대와-승인-승계)의 인수 확인 없이 역할을 바꾸지 않는다.
- 실행 직후 상태: 기본 checkout의 `artifacts/development-cycle/latest.json`이 가리키는 handoff·next_steps·token_report·실험 판정. ignored 자료가 다른 worktree에 없으면 복제하거나 정상으로 추정하지 않고 의존을 기록한다.
- 점수·기준: development-progress.json과 PROGRESS_CRITERIA.md. 이 입구에는 숫자·담당자 이름·진행 중 상태를 복사하지 않는다.
- 과거 인계·README·실험 결과: 당시 근거다. 현재 task·원문 기록을 대신하거나 과거 실행을 다시 승인하지 않는다. [보관함](history/README.md)에서 찾는다.

## 스킬 사용 선택표 (Superpowers 7.0.1)

스킬은 개발 절차 참고이며 권한을 새로 부여하지 않는다. 스킬이 하위 에이전트 실행·병합·push·삭제·전체 suite 실행을 지시해도 승인이 아니다. 이 문서와 AGENTS.md·PAIR_CODING.md의 승인·잠금·역할이 우선한다. 스킬을 불렀거나 일부를 읽은 것은 전체를 읽은 것도, 지킨 것도 아니다. 출력이 잘렸으면 누락 구간을 다시 읽는다. 이 표는 모델 정확도 개선이나 토큰 절감의 근거가 아니다(미측정).

| 스킬 | 사용 | 조건·보정 |
|---|---|---|
| verification-before-completion | 기본 | 명령·출력·종료 코드·주장을 대조한다. 금지된 검사를 실행할 권한은 아니다. |
| test-driven-development | 기본 | 의도한 실패를 먼저 확인한다. 전체 suite 강제와 코드 삭제 지시는 따르지 않고 task의 checks 범위를 따른다. 테스트를 쓸 때 writing-good-tests.md도 읽는다. |
| requesting-code-review | 기본 | 기준은 HEAD~1이 아니라 task의 base_sha다. 하위 모델 호출 승인과 입력 범위를 먼저 고정한다. |
| systematic-debugging | 버그 작업 | 재현 → 단일 가설 → 최소 변경. 진단 실행도 승인 범위 안에서만 한다. |
| receiving-code-review | 검토 의견을 반영할 때 | 적용 전 코드로 확인한다. 불명확한 항목만 보류하고 독립 항목은 계속한다. 삭제 제안은 허용 파일·승인 안에서만. 외부 스레드 답글은 하지 않는다. |
| using-git-worktrees | 격리 확인만 | 생성·설치·.gitignore 변경·현재 checkout fallback은 PAIR_CODING.md §4를 따른다. |
| brainstorming | 요구가 실제로 불명확할 때 | 명확한 요청은 바로 처리한다. 승인된 TODO마다 설계를 다시 묻지 않는다. |
| writing-plans | task 계약 안에서 | 별도 계획 문서와 실행 스킬 자동 연결을 만들지 않는다. |
| executing-plans | 원리만 | 진행 장부 개념만 쓴다. 절차·기록 삭제·마무리 연결은 PAIR_CODING.md를 따른다. |

쓰지 않는다: finishing-a-development-branch, subagent-driven-development, dispatching-parallel-agents, diagnosing-superpowers, writing-skills, using-superpowers의 자동 호출 규칙. 병렬·하위 에이전트는 사용자가 승인한 분업이 있을 때만 별도 계약으로 다룬다.

스킬을 적용하는 task·보고서에는 적용 스킬 또는 해당 없음과 이유, 읽은 범위, RED/GREEN 명령·종료 코드·로그·검증 대상 SHA를 적는다. 이 기록은 준수의 증명이 아니다. 압축·재개 뒤에는 현재 task, SHA, 담당, 잠금을 실제 상태와 다시 대조한다. 스킬 본문은 Codex 캐시 `~/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/<이름>/SKILL.md`에서 읽을 수 있으나 이것을 영구 설치 경로로 확정한 것은 아니다. 이 선택표를 바꾸는 것은 새 승인이 아니다.

## 자동 하위 검토는 별도 입력 계약

일반 Codex·Claude 구현 에이전트는 위 문서를 읽는다. `./review --auto` 안의 격리된 하위 Codex는 탐색 도구·메모리·프로젝트 자동 로딩을 끄고 프로그램이 묶은 동결 근거·코드·8개 review-rule만 받는다. 추가 파일을 읽도록 지시해 격리를 풀지 않는다. 근거가 부족하면 대기/종료한다. 두 경로의 권한·입력 범위를 혼동하지 않는다.

## 로딩 확인과 갱신

Claude는 `/memory`에서 가져온 파일을 확인할 수 있다. Codex·Claude 모두 이번 작업의 read_docs·검사·인계에 실제 읽은 원문 경로와 필요한 구역을 기록한다. 이것은 규칙 준수의 증명이나 새 승인 자체가 아니다. 모든 문서를 상시 import하지 않고 위 조건에 해당할 때 원문을 읽는다.

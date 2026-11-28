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
| 모델·worker 수정 또는 새 실험 | [COMMON_EXPERIMENT_RECORDS.md](../COMMON_EXPERIMENT_RECORDS.md) 전체 + [OBSERVATION_CONSENSUS_20261011.md](../OBSERVATION_CONSENSUS_20261011.md) + 사전 계획·대조 근거 + [품질 규칙](agent/QUALITY_RULES.md) | ./develop 잠금, ./experiment, 변수 하나, 학습/평가 분리, 실제점·필수 cohort 보호 |
| 사람 라벨·정답 의미·검토 화면 | [LABELING_PROTOCOL.md](../LABELING_PROTOCOL.md) 전체 + 해당 사진·사람 응답·현재 계약 + [품질 규칙](agent/QUALITY_RULES.md) | 완료 재요청 금지, unknown 보존, 모델 오답으로 사람 정답 변경 금지 |
| 자동 검토·실험 연결·오류 재개 | 공통 실험 계약 + [AUTO_REVIEW_CONTRACT.md](agent/AUTO_REVIEW_CONTRACT.md) 전체 + [자동 개발 안내](../AUTO_DEVELOPMENT_20261020.md) + 실제 journal | 기존 승인·무료 가드·입력 예산, 결과 불명 재요청 금지, 저장 응답 재사용 조건 |
| 성과·진척 보고 | [PROGRESS_CRITERIA.md](../PROGRESS_CRITERIA.md) 전체 + [development-progress.json](../development-progress.json) + [HTML_REPORTING.md](collaboration/HTML_REPORTING.md) | 현재 버전·점수 정본, 고정 배점, 이번 검사와 과거 성능 구분 |
| 통합·원격 반영·역할 교대·worktree 정리 | PAIR_CODING.md 전체 + 배정 계약·승인 장부·전달 SHA | 통합·push는 각각 SHA별 사용자 승인, force 금지, 승인 승계 조건, 실행 중·고유 증거 보호 |
| 자율 개발 하네스 설계·구현 | [하네스 설계 묶음](collaboration/plans/autonomous-harness-20261127/README.md)의 읽는 순서 전체 | 설계 확정·구현 미승인, D-1~D-4 확정 전 구현 금지, 이 묶음은 새 권한이 아님 |

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
| test-driven-development | 선택 | 버그 재현이나 데이터 손실·보안·라벨 무결성 등 위험한 로직의 검증에 필요할 때만 적용한다. 적용 시 의도한 실패를 먼저 확인한다. 전체 suite 강제와 코드 삭제 지시는 따르지 않고 task의 checks 범위를 따른다. 테스트를 쓸 때 writing-good-tests.md도 읽는다. |
| requesting-code-review | 기본 | 기준은 HEAD~1이 아니라 task의 base_sha다. 하위 모델 호출 승인과 입력 범위를 먼저 고정한다. 실험 worker·모델 코드는 [품질 규칙](agent/QUALITY_RULES.md) `worker-review-checklist` 점검표를 리뷰 입력에 넣는다. |
| systematic-debugging | 버그 작업 | 재현 → 단일 가설 → 최소 변경. 진단 실행도 승인 범위 안에서만 한다. |
| receiving-code-review | 검토 의견을 반영할 때 | 적용 전 코드로 확인한다. 불명확한 항목만 보류하고 독립 항목은 계속한다. 삭제 제안은 허용 파일·승인 안에서만. 외부 스레드 답글은 하지 않는다. |
| using-git-worktrees | 격리 확인만 | 생성·설치·.gitignore 변경·현재 checkout fallback은 PAIR_CODING.md §4를 따른다. |
| brainstorming | 요구가 실제로 불명확할 때 | 명확한 요청은 바로 처리한다. 승인된 TODO마다 설계를 다시 묻지 않는다. |
| pair-coding(저장소 스킬 `.agents/skills/pair-coding`) | 사용자가 `pair-coding 열기/시작/이어하기/통합/인수`를 부를 때만 | Codex·Claude 병렬 구현 절차. 권한을 새로 부여하지 않으며 PAIR_CODING.md·AGENTS.md가 우선한다. 구현 담당은 push하지 않는다. 메인의 열기·통합 커밋과 push는 AGENTS.md의 SHA별 사용자 직접 승인을 받은 뒤에만 한다. |
| writing-plans | task 계약 안에서 | 별도 계획 문서와 실행 스킬 자동 연결을 만들지 않는다. |
| executing-plans | 원리만 | 진행 장부 개념만 쓴다. 절차·기록 삭제·마무리 연결은 PAIR_CODING.md를 따른다. |

쓰지 않는다: finishing-a-development-branch, subagent-driven-development, dispatching-parallel-agents, diagnosing-superpowers, writing-skills, using-superpowers의 자동 호출 규칙. 병렬·하위 에이전트는 사용자가 승인한 분업이 있을 때만 별도 계약으로 다룬다.

TDD는 기본 적용하지 않는다. 단순한 변경에 TDD 순서나 RED/GREEN 기록을 강제하지 않으며, 작업에 필요한 검증은 task의 checks에 따른다. 스킬 기록 검사기 시범(`skill-record-check-20261118`, `skill-record-check-fix-20261118`)은 main에 통합하거나 선택표·커밋 전 훅에 연결하지 않는다.

스킬을 적용하는 task·보고서에는 적용 스킬 또는 해당 없음과 이유, 읽은 범위, 실제 검증 명령·종료 코드·로그·검증 대상 SHA를 적는다. RED/GREEN 기록은 TDD를 적용한 경우에만 남긴다. 이 기록은 준수의 증명이 아니다. 압축·재개 뒤에는 현재 task, SHA, 담당, 잠금을 실제 상태와 다시 대조한다. 스킬 본문은 Codex 캐시 `~/.codex/plugins/cache/openai-curated-remote/superpowers/7.0.1/skills/<이름>/SKILL.md`에서 읽을 수 있으나 이것을 영구 설치 경로로 확정한 것은 아니다. 이 선택표를 바꾸는 것은 새 승인이 아니다.

## 품질 규칙 선택표

[품질 규칙](agent/QUALITY_RULES.md)은 실험·라벨·판정 작업에 쓰는 규칙 묶음이다. 사용자는 이름을 외우거나 골라 줄 필요가 없다. 에이전트가 작업을 시작할 때 아래 표와 대조해 해당하는 규칙만 골라 쓴다.

- **자동**: 사용자가 아무 말을 하지 않아도 해당 행을 적용한다.
- **한 줄 호출**: "품질 규칙 사용해서 처리해줘" 또는 "Superpowers 사용해서 처리해줘"라고 하면 이 표와 위 스킬 선택표를 **둘 다** 대조한다. 규칙 이름·한국어 이름·옛 번호로 하나만 지정해도 된다.
- **순서**: ① 요청과 실제 작업 내용으로 해당 행을 고른다(여러 개면 합친다). ② 고른 규칙의 본문을 읽는다. ③ 시작 한 줄에 "쓸 규칙: 이름(한국어)"을 적는다. 해당이 없으면 "해당 없음"과 이유를 적는다. ④ 작업이 바뀌면 다시 대조한다. ⑤ 보고에 적용한 규칙과 못 지킨 규칙·이유를 적는다.
- 판단이 애매하면 적용하는 쪽을 고르되, 그 때문에 승인 범위 밖의 작업을 시작하지 않는다. 규칙을 부른 것은 실험·라벨 재요청·외부 호출의 승인이 아니다. 규칙을 골랐거나 읽은 것은 지킨 증명이 아니다.

| 규칙 | 쉬운 이름 | 이럴 때 자동으로 쓴다 |
|---|---|---|
| `error-cause-triage` | 오류 원인 분류 | 실험이 기준에 못 미쳤거나 남은 누락·오탐을 줄이자는 요청. 새 모델 가설보다 먼저 |
| `can-this-experiment-tell` | 판별 가능성 관문 | 새 모델·전처리 실험 계획을 쓸 때, 새 라벨을 요청할 때 |
| `stop-repeated-misses` | 연속 미달 멈춤 | 같은 평가 자료로 실험을 또 하려 할 때 (상한 값 있음) |
| `zero-denominator-unmeasured` | 분모 0은 미측정 | 실험 계획·결과에서 결함 또는 정상 행이 0일 때 (실행기가 기록) |
| `chance-check` | 우연·반복 시도 표기 | 두 결과를 비교하거나 "좋아졌다"고 말하려 할 때 |
| `experiment-closeout` | 실험 보고서 세 칸 | 실험이 끝나 보고서를 쓸 때. 통과·미달 무관 |
| `worker-review-checklist` | 실험 코드 리뷰 점검표 | worker·모델 코드를 리뷰할 때 |
| `fresh-labels-test-first` | 새 라벨 1회 평가 | 사람이 확인한 새 라벨 묶음이 들어왔을 때, 학습에 넣기 전 |
| `single-source-criteria` | 기준은 한 곳 | 결함·정상 기준 문구, 라벨 화면, AI 판정 지시서를 만들거나 고칠 때 |
| `label-provenance` | 라벨 당시 기준 기록 | 라벨·판정을 새로 저장할 때 (모서리 화면만 기록 파일 지원, 나머지는 "버전 미상"으로 보고) |
| `label-screen-round-trip` | 누른 것 = 가져온 것 | 라벨 화면이나 답 가져오기 도구를 만들거나 고칠 때 |
| `judge-before-peeking` | 먼저 판정하고 보기 | 엇갈린 판정을 최종 결정할 때 |
| `explicit-verdict-merge` | 판정 합치는 법 밝히기 | 같은 대상을 여러 번 판정해 합칠 때 |
| `label-agreement-watch` | 라벨 일치도 관리 | 재판정 일치율을 재거나 기준 문구가 바뀌었을 때 |
| `regression-for-every-fix` | 고친 결함 회귀 검사 | 화면 문구·지시서·worker·도구의 결함을 고칠 때 |
| `short-request-reading` | 짧은 요청 해석 | 모든 요청 |

## 자동 하위 검토는 별도 입력 계약

일반 Codex·Claude 구현 에이전트는 위 문서를 읽는다. `./review --auto` 안의 격리된 하위 Codex는 탐색 도구·메모리·프로젝트 자동 로딩을 끄고 프로그램이 묶은 동결 근거·코드·8개 review-rule만 받는다. 추가 파일을 읽도록 지시해 격리를 풀지 않는다. 근거가 부족하면 대기/종료한다. 두 경로의 권한·입력 범위를 혼동하지 않는다.

## 로딩 확인과 갱신

Claude는 `/memory`에서 가져온 파일을 확인할 수 있다. Codex·Claude 모두 이번 작업의 read_docs·검사·인계에 실제 읽은 원문 경로와 필요한 구역을 기록한다. 이것은 규칙 준수의 증명이나 새 승인 자체가 아니다. 모든 문서를 상시 import하지 않고 위 조건에 해당할 때 원문을 읽는다.

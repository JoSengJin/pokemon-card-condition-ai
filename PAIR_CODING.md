# Codex · Claude Git 협업 전략

2026-10-25. 현재 협업 규칙이며, `CLAUDE_HANDOFF_20261024.md`의 날짜별 역할·실험 상태보다 우선한다. 사람 정답, 실험 계약, 승인 범위는 `AGENTS.md`를 그대로 따른다. 이 문서는 협업 방식만 바꾸며 새 개발·학습·외부 AI 호출을 승인하지 않는다.

## 1. 병렬 구현, 직렬 실행·통합

| 대상 | 소유자와 경계 |
|---|---|
| `main` 및 원격 반영 | Codex가 통합 담당. Claude는 직접 수정·merge·push하지 않는다. |
| 코드 구현 | Codex와 Claude가 서로 다른 브랜치와 worktree를 사용한다. 같은 checkout을 두 에이전트가 편집하지 않는다. |
| 작업별 파일·계약 | 시작 전에 task 문서로 분리한다. 같은 파일은 한 작업에만 배정한다. |
| 실제 학습·모델 비교·사진 추론 | 기본 checkout에서 Codex만 공통 실행기로 직렬 실행한다. Claude는 worker와 단위 검증을 전달한다. |
| 사람 라벨·원본 사진·평가 기준·모델 채택 | 기본 checkout에서 한 명만 기록한다. Claude worktree에서는 수정하거나 복사해 학습하지 않는다. |
| 자동 교차 검토·API 호출 | 기존 승인과 호출 제한을 따른다. 구현 worktree에서 실제 `./review --auto`나 provider 호출을 시작하지 않는다. |

Git은 편집 공간과 이력을 분리하지만 의미상 충돌, 데이터 누수, GPU 경합을 막지는 않는다. 현 `workspace_lock.py`의 잠금 경로는 checkout별 `artifacts/development-cycle/workspace.lock`이다. 따라서 `./develop`은 각 worktree의 편집 잠금으로 유지하고, 실제 실험은 기본 checkout 한 곳으로 제한한다. 전역 잠금이 구현됐다고 주장하지 않는다.

## 2.1 사람이 유지보수할 수 있는 코드 크기

Codex와 Claude는 새 코드와 수정한 코드를 아래 기준으로 맞춘다. 이 기준은 Ponytail의 최소 변경·간결성 원칙보다 우선한다. Ponytail은 제한을 지키는 범위에서 불필요한 코드와 추상화를 줄이는 데 적용한다.

- 소스 파일 하나에 함수 정의를 최대 7개 둔다. 일반 함수, 비동기 함수, 클래스 메서드, 중첩 함수 모두 세며, 클래스가 여럿이어도 파일 전체 합계로 계산한다. 호출하는 외부 함수와 가져온 함수는 세지 않는다.
- 함수 호출 깊이는 시작 함수에서 다른 함수로 이어지는 호출 전이 횟수로 세고 최대 4회로 제한한다. 예를 들어 `A → B → C → D → E`는 4회라 허용되고, `A → B → C → D → E → F`는 5회라 초과다. 함수가 다른 파일이나 객체에 있어도 호출이 이어지면 함께 센다.
- 두 제한을 맞추려고 여러 책임을 한 함수나 객체에 합치지 않는다. 파일 함수 수가 한도에 닿으면 응집된 책임을 별도 파일로 나누고, 호출 깊이가 한도를 넘으면 호출 경로와 책임 경계를 다시 설계한다. 분리만으로 호출 깊이를 감추거나 계층을 불필요하게 추가하지 않는다.
- 작업 계약에는 수정 대상 파일의 함수 수(변경 전/후)와 새로 만들거나 바뀐 주요 호출 경로를 기록한다. 리뷰어는 파일 경계를 넘어 경로를 확인한다. 프레임워크 콜백·동적 디스패치 등으로 호출 대상을 정적으로 확정할 수 없으면 통과로 간주하지 말고 미확인 경로와 근거를 handoff에 적어 통합 전에 해결한다.
- 재귀처럼 호출이 순환하는 경로는 한 번의 호출 전이로 깊이를 유한하게 셀 수 없으므로, 변경한 경로에 포함되면 리뷰에서 별도 표시하고 사용자와 기준을 확정하기 전에는 임의로 예외 처리하지 않는다.

## 3. 작업 시작 전에 고정할 계약

Codex는 `docs/collaboration/tasks/<task-id>.md`에 다음을 적고 커밋한 뒤 전달한다. 동시에 진행할 작업의 허용 파일 집합은 겹치지 않게 한다. 계약을 확정할 수 없으면 코드 탐색·읽기 전용 검토까지만 진행한다.

```text
task_id:
owner: Claude 또는 Codex
status: assigned / implementing / ready_for_review / integrated / blocked
base_sha: 시작점의 전체 커밋 SHA
branch:
worktree: 로컬 경로는 커밋하지 않고 세션에서만 전달
goal: 관찰 가능한 완료 조건 하나
allowed_files: 수정 가능한 파일의 정확한 목록
forbidden_files: 다른 작업 소유 파일과 데이터·비밀 설정
contract: 입력·출력·호출자·기존 동작 중 보존할 조건
structure: 변경 파일별 함수 수(전/후), 변경된 주요 호출 경로(전이 수)
checks: 관련 단위 검사와 통합 후 검사
experiment: 필요 여부, 가설 ID·사전 기준·대조 근거 위치
handoff: 전체 커밋 SHA, 변경 파일, 구조 기준 확인 결과, 검사 결과, 미검증, 리스크, 롤백
```

공용 파일이 겹치면 Codex가 작업을 직렬화하거나, 해당 파일의 변경을 통합 단계에 맡긴다. 같은 API의 호출자와 구현을 서로 다른 작업에 배정할 때는 먼저 계약을 고정하고 통합 검사를 지정한다. 파일이 다르다는 이유만으로 독립 작업으로 취급하지 않는다. 범위 확대는 계약을 갱신한 뒤 진행한다.

## 4. worktree와 실행 환경

기본 checkout이 깨끗하고 진행 중인 실험·검토가 없는 시점에 Codex가 작업 브랜치를 준비한다. 아래는 설정 예제이며 실제 작업 생성·설치가 완료됐다는 뜻은 아니다.

```sh
# 기본 checkout에서 실행. 값은 각자의 로컬 환경에 맞게 설정한다.
TASK_ID="cache-audit-001"
CLAUDE_WORKTREE="../pokemon-card-condition-claude"
BASE_SHA=$(git rev-parse main)
git worktree add -b "claude/$TASK_ID" "$CLAUDE_WORKTREE" "$BASE_SHA"
```

Codex도 병렬 구현이 필요하면 별도 `codex/<task-id>` 브랜치와 별도 worktree를 사용한다. 기본 checkout은 통합·실제 실험용이다. 기존 worktree가 있으면 `git worktree list`로 확인하고 재사용 가능성을 먼저 판단한다. 이미 사용 중인 브랜치를 강제로 checkout하지 않는다.

각 worktree는 자체 `.venv`를 만든다. `.venv`, `data`, `artifacts`, `.backups`, provider 키, `development-review.json`, `nemotron-review.json`을 다른 worktree와 심볼릭 링크로 공유하지 않는다. editable 설치된 공용 가상환경을 공유하면 다른 checkout의 모듈을 읽을 수 있다.

기존 의존성 설치 절차와 `requirements-tested.txt`를 확인한다. 필요한 패키지만 설치하고, 모델 가중치 다운로드·새 라이브러리 추가·provider 초기화를 설치 확인과 섞지 않는다. 소스 편집 전 자체 환경에서 아래 import가 현재 worktree를 가리키는지 확인한다.

```sh
.venv/bin/python -c 'import card_condition; print(card_condition.__file__)'
```

모델·worker 수정은 해당 worktree의 `./develop -- <수정 명령>` 안에서 수행한다. `./develop --check` 뒤 에디터에서 별도로 쓰는 방식은 잠금 소유가 아니다. 실제 편집 명령을 잠금 안에서 실행하며 실패하면 잠금을 지우지 않는다.

## 5. Claude의 구현·전달

1. `AGENTS.md`, 이 문서, 배정 task와 `base_sha`를 확인한다. 다른 작업의 최신 상태를 오래된 인계 문서로 추정하지 않는다.
2. 소유 파일과 호출자·테스트를 읽고 허용 파일만 변경한다. 데이터 없이 가능한 합성 fixture·mock 단위 검증을 먼저 사용한다.
3. 실제 라벨·사진·캐시가 있어야 하는 검사는 미실행과 의존 이유를 기록한다. `artifacts/`가 Git에 없다는 이유로 정답·수치를 꾸미거나 비밀 설정을 가져오지 않는다.
4. 공유할 신규 실험 worker는 `tools/experiments/<task-id>/`처럼 추적 가능한 경로에 둔다. 실험 계획의 `code_changes`에 등록하고 신규 파일은 `baseline=null`, 기존 파일은 실제 수정 전 snapshot을 지정한다. 과거 ignored worker를 임의로 복제·수정하지 않는다.
5. `git diff --check`, 허용 파일 대조, 관련 단위 검증, 비밀 파일 제외를 확인하고 `feat(scope): 내용`, `fix(scope): 내용`, `test(scope): 내용` 형식으로 커밋한다. 수정 중 임의의 전체 `git add .`는 사용하지 않는다.
6. task 문서에 최종 검사 결과와 미검증을 기록하고 함께 커밋한다. 마지막으로 `git status --short`가 깨끗한지 확인한다.
7. 최종 전체 SHA 또는 필요한 SHA들의 순서를 Codex에 전달한다. 완료 후 같은 브랜치에 추가 커밋하지 말고 후속 변경은 새 작업으로 배정받는다.

전달은 사용자가 공유하는 결과나 승인된 채널을 사용한다. 자동 에이전트 통신·상시 실행을 가정하지 않는다. 같은 로컬 저장소의 worktree는 커밋 객체를 공유하므로 branch push 없이도 Codex가 SHA를 읽을 수 있다. 다른 컴퓨터에서 작업할 때는 승인된 작업 브랜치만 push한다.

## 6. Codex의 통합·실험

1. 전달 SHA가 고정된 작업 브랜치에 속하는지, `base_sha`와 일치하는 작업인지 확인한다. `git diff <base_sha> <tip_sha>`로 파일 범위·계약·관련 호출자·개인정보를 검토한다.
2. 기본 checkout의 미커밋 변경과 진행 중 실험·검토가 없을 때만 통합한다. 관련 소스 변경을 포함한 cherry-pick은 `./develop -- git cherry-pick -x <SHA>`로 수행한다. 여러 SHA는 계약에 적힌 순서대로 반영한다.
3. 충돌이 나면 충돌 파일만 검토한다. 원인 확인 없이 `ours`/`theirs` 전체 선택, `reset --hard`, 라벨 덮어쓰기를 하지 않는다. 해결·continue 또는 abort도 `./develop -- <명령>` 안에서 수행한다.
4. 통합된 코드에서 관련 테스트와 지정한 통합 검사를 실행한다. Claude 브랜치에서 통과했다는 사실만으로 통합 성공으로 기록하지 않는다.
5. 실제 성능 검증이 필요하면 사전 계획과 수정 전 snapshot을 다시 대조하고 `./experiment --plan <계획.json> -- <실행 명령>`으로 하나만 실행한다. `git cherry-pick` 자체는 snapshot이나 실험 기록을 대신하지 않는다.
6. 공통 실행기 반환 후 최신 `development_handoff.json`, `next_steps`, `token_report`, `record.json`과 수용 판정을 읽는다. 자동 수정의 채택·복원 상태를 확인하기 전 다른 변경을 덮어씌우지 않는다.
7. 실제 성능 비교를 했다면 사진별 HTML과 동일 분모의 FN/FP/%p를 제공한다. 독립 평가가 없으면 일반화 개선은 미확인이다. 문서·단위 검사만 수행한 작업에는 성능 향상을 붙이지 않는다.
8. 사용자에게 변경 파일·핵심 diff·실행 검증·리스크·롤백을 보고한다. 원격 반영이 승인된 작업만 일반 push하며 force push와 이력 재작성은 새로 명시된 요청 없이는 하지 않는다.

처음부터 잘못된 작업이면 cherry-pick을 abort한다. 이미 통합한 변경은 진행 중 실행·후속 의존성을 확인한 후 `./develop -- git revert <통합 SHA>`로 되돌린다. 실행 중인 실험 위에서 rollback하지 않는다. ignored 데이터·모델의 복구는 실험 snapshot과 별도 기록을 따른다.

## 6. 지켜야 할 한계

- 파일 소유권과 단일 실험 소유자는 운영 규칙이다. 프로그램이 전역에서 강제하는 장치가 새로 생긴 것은 아니다. 위반하면 독립 worktree여도 충돌할 수 있다.
- `git stash`, index, checkout, cherry-pick은 각자 worktree에서만 수행한다. 다른 에이전트의 작업 디렉터리를 정리하지 않는다. 공유 브랜치 ref·Git 설정·worktree 삭제는 Codex만 조정한다.
- 원본 데이터·비밀 파일·대형 모델은 계속 Git 제외 대상이다. 코드가 병합돼도 제외된 실행 자료가 자동으로 전달되지는 않는다.
- worktree 제거는 전달 커밋의 통합과 미커밋 파일·ignored 산출물의 보존 여부를 확인한 뒤 한다. `git worktree remove --force`로 정리하지 않는다.
- 기존 인계 문서의 실패 가설·수치·실험 위치는 당시 근거다. 최신 실제 기록과 대조하기 전 다음 실행 대상으로 선택하지 않는다.


## 성과·진척 HTML 인계

Codex와 Claude 모두 docs/collaboration/HTML_REPORTING.md를 따른다. 작업 계약에 HTML 산출물의 정확한 경로와 생성·검증·열기 단계를 고정한다. 인계에는 실제 결과와 고정 기준 진척률, HTML 경로, 열기 성공 여부와 렌더 확인 여부를 포함한다. 기존의 실측 모델 비교 사진/구역/FN·FP 보고 의무도 유지한다.


## 검증한 main의 push와 세션 간 기준 동기화

2026-10-25 사용자 상시 승인, 2026-10-26 적용 범위 확대. Codex는 직접 개발·검증한 변경과 Claude 결과를 검토·검사해 main에 통합한 변경 모두 origin/main에 일반 push까지 수행한다. 검증된 main 변경의 원격 반영은 매번 다시 묻지 않는다. 미검토 Claude 브랜치를 임의로 통합하거나 모든 브랜치를 push하지 않는다.

1. 통합 전 origin/main을 fetch하고 기준 SHA·작업 트리·진행 중 Git 작업·개발 잠금을 확인한다. 다른 사용자의 미커밋 변경을 포함해 커밋하거나 stash/reset하지 않는다. 원격 변경이 있으면 근거를 검토해 먼저 반영하고 관련 검사를 다시 실행한다. 변경된 기준 위에서 이전 승인을 재사용하지 않는다.
2. 검증된 main을 명시적으로 git push origin main으로 반영한다. force/force-with-lease·이력 재작성은 별도 사용자 요청 없이 사용하지 않는다. push가 거절되면 최신 원격을 다시 확인하고 원인을 해결한다. 인증/권한 문제로 해결하지 못하면 로컬 SHA·원격 상태·차단 이유를 보고하며 push 완료라고 쓰지 않는다.
3. 성공 후 원격 main SHA와 로컬 HEAD 일치를 확인해 인계한다. 다른 세션이 원격을 즉시 갱신할 수 있으므로 이 확인 시점의 일치임을 구분한다.
4. 새 작업을 배정하는 세션은 먼저 fetch하고 검증된 최신 origin/main을 기준으로 base_sha를 고정한다. 이미 실행 중인 작업은 임의로 rebase/reset/기준 변경하지 않고 원래 계약 기준으로 인계한 뒤 Codex가 통합 검증한다. 별도 세션은 통합 담당을 조정해 main 변경과 push를 직렬화한다.

push는 공통 기준을 공유하는 절차이며 같은 파일/API 변경에서 생기는 의미상 충돌을 없애지는 않는다. 정확한 파일 소유권·작업 계약·직렬 통합 원칙을 함께 유지한다. 롤백은 git revert로 새 커밋을 만들고 관련 검사 후 일반 push한다.

## 통합 후 worktree 정리 — 최근 완료 작업 1개 유지

2026-10-26 사용자 승인. Codex는 검증한 페어코딩 결과를 main과 origin/main에 반영한 뒤, 해당 통합 작업의 마무리로 아래 정리를 수행한다. 별도 상시 프로세스나 예약 작업이 아니라 통합 절차의 일부다. 기본 checkout과 미통합·작성 중 작업은 보관 개수에 포함하지 않는다.

1. `git worktree list --porcelain`으로 실제 등록 목록을 확인한다. 대상의 전달 커밋 전체가 main의 조상이거나 main 로그의 `(cherry picked from commit <전체 SHA>)`로 대응되는지 확인한다. 계약의 `integrated` 문구만 믿지 않는다. 일부 채택·커밋 대응 불명·미통합이면 보존하고 이유를 기록한다.
2. 통합 완료 작업 중 main 반영 순서가 가장 최근인 작업 1개의 checkout을 롤백 확인용으로 남긴다. 새 작업의 검증·push가 끝나면 이전 보관 작업을 정리 대상으로 바꾼다. 롤백은 이 디렉터리 자체에 의존하지 않고 통합 SHA의 `git revert`로 수행한다. 코드 이력과 작업 브랜치는 이 디렉터리 정리에서 삭제하지 않는다.
3. 제거 직전에 대상 HEAD와 `git status --porcelain`을 다시 확인한다. 미커밋·untracked 파일, 진행 중 Git 작업, 사용 중인 개발 잠금 또는 작업 중임을 확인한 세션이 있으면 그 디렉터리만 보류한다. 기존 `workspace.lock`은 파일 존재가 아니라 비차단 `flock` 획득으로 사용 여부를 확인하고 제거가 끝날 때까지 유지한다. 앱이 관리하는 worktree는 해당 앱의 소유권·archive 절차를 따른다.
4. `git ls-files --others --ignored --exclude-standard`로 Git 제외 파일도 확인한다. 검사 로그·HTML·실험 기록 등 고유 증거는 기본 checkout의 Git 제외 `artifacts/`에 상대경로와 SHA-256 목록을 보존하고, 복사/압축본의 내용을 검증한 뒤 제거한다. 사진·라벨·모델·비밀 설정은 검증된 정본/안전한 보존 위치가 확인되지 않으면 보류한다. 재생성 가능한 `.venv`, Python 캐시, egg-info는 보관하지 않는다. 보존한 증거는 실험/감사 기록이며 순환 롤백 환경과 구분한다.
5. 일반 `git worktree remove <대상>`만 사용한다. 실패하면 보류하고 원인을 기록한다. `--force`, 경로 전체 강제 삭제, 잠금 파일 강제 삭제로 우회하지 않는다. 공유 객체·브랜치와 기본 checkout의 데이터·환경은 유지한다.
6. 실제 제거/유지 목록, 근거 main/전달 SHA, 보존 증거·해시, 보류 사유, 복원 방법을 Git 제외 감사 기록과 HTML에 기록한다. 제거된 checkout은 보존한 branch/SHA로 `git worktree add <복원 경로> <branch 또는 SHA>` 후 필요한 증거만 복원하고, 가상환경은 다시 설치한다. 비밀값·로컬 절대경로는 원격 문서에 넣지 않는다.

이미 실행 중인 다른 세션에 이 규칙이 자동 전달되지는 않는다. 다음 작업 계약과 인계에는 최근 보관 작업의 branch/SHA 및 정리 여부를 포함한다.

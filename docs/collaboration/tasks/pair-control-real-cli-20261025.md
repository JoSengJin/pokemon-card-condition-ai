# pair-control 실제 CLI 경로(무과금 조건) — Claude 배정

- task_id: `pair-control-real-cli-20261025`
- owner: Claude
- status: implementing
- base_sha: `0e5171b40bfa635ab547e599e3f2c4cb6d2d7200` (시작 HEAD, 미커밋 변경 없음 확인)
- branch: `claude/pair-control`
- 실행 Node: package.json `engines.node >=22` → nvm v24.21.0 (로그인 셸 기본 Node 18은 사용하지 않음)

## 목표

pair-control이 실제 Claude Code·Codex CLI(구독 로그인)로 작업을 진행할 수 있게 하되, **요금이 발생하는 경로를 코드로 차단**한다. 에이전트를 도구가 띄우지 않고 사용자 세션에서 작업하는 수동 모드, "누구 차례" 상태, 시작 프롬프트 복사, 인계 문서, 사람이 제어하는 푸시·되돌림 절차, 진행률 항목 기반 계약 초안, 메인 역할 표시·이양 기록을 추가한다.

## 무과금 조건 (사용자 지시, 2026-10-25)

실제 CLI 모드는 **구독 로그인으로만** 동작한다. 아래 중 하나라도 있으면 시작하지 않고 원인과 해결 조건을 표시한다.

- API 키·클라우드 토큰 환경변수(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `CODEX_API_KEY` 등) — 기존 목록 유지
- Claude Code 설정(사용자·프로젝트)의 `apiKeyHelper` 또는 `env`에 위 키 이름 — **키 이름만 검사하고 값은 읽거나 기록하지 않는다**
- 인자에 `--bare`(구독 로그인을 쓰지 않고 API 키를 요구) 또는 `--max-budget-usd`·`--betas`(API 사용자용)
- `confirmedSubscriptionAuth`가 true가 아님(사용자가 계정에서 구독 로그인·추가 크레딧 꺼짐을 직접 확인했다는 표시)
- CLI `--help`에서 필요한 옵션이 확인되지 않음

한도 도달(usage limit)은 **정지 신호**로 처리하며 재시도·크레딧 구매를 시도하지 않는다.

## allowed_files

1. `tools/pair-control/**` (소스·테스트·문서·설정 예제. `node_modules`, `.state`, `.demo`, `.mastra`, `config.local.json`은 Git 제외)
2. `docs/collaboration/tasks/pair-control-real-cli-20261025.md` (이 문서)
3. `docs/collaboration/reports/pair-control-real-cli-20261025.md` (인계 보고서)

## forbidden_files / 하지 않는 일

- 위 목록 밖 전부(`card_condition/`, 기존 `tests/`, `AGENTS.md`, `PAIR_CODING.md`, README, 진척률, `data/`, `artifacts/`, 라벨·모델·provider 키). 다른 worktree·브랜치·기본 checkout 조작 금지.
- **실제 Claude/Codex 모델 호출, CLI 설치·로그인·인증 변경, API 키 입력, 유료 기능 활성화를 하지 않는다.** 실제 CLI 경로는 가짜 `claude`/`codex` 실행 파일(임시 폴더, `--version`/`--help`/동작 흉내)로만 검증한다.
- `~/.codex/auth.json` 등 자격 증명 파일은 읽지 않는다.
- 실제 GitHub 푸시 금지. 푸시·되돌림은 로컬 bare 원격(합성)으로만 검증한다. 도구는 force push·`reset --hard`를 하지 않는다.
- PAIR_CODING.md·AGENTS.md의 역할 규칙(main 통합은 Codex 등)은 바꾸지 않는다. 메인 이양은 표시·안전 확인·기록만 하며 권한을 강제하지 않는다.
- 학습·모델 비교·사진 추론·라벨 수정·자동 교차 검토를 실행하지 않는다.

## 구현 항목

1. 무과금 가드: 위 조건 검사, 차단 원인 코드·해결 조건, 한도 도달 문구를 정지로 분류.
2. 수동 모드: 도구가 에이전트를 띄우지 않고 파일 소유권·잠금만 유지, "작업 완료 — 결과 수집" 후 기존 검사·리뷰·승인 흐름.
3. 누구 차례(사용자/구현 에이전트/메인 에이전트) 상태와 복사용 시작 프롬프트(작업 위치·브랜치·시작 SHA·읽을 문서·허용 파일·금지·인계 형식).
4. 인계 문서 생성·커밋과 인계 취소.
5. 푸시: 점검(fetch·fast-forward·금지 경로·비밀 패턴·통합 후 검사·`--dry-run`) → SHA 입력 확인 → 일반 push → `ls-remote` 사후 확인 → 기록. 되돌림: `git revert` 커밋 생성 → 검사 → 같은 푸시 절차.
6. 진행률 항목(`development-progress.json` 미완료)을 고르면 원문 인용 계약 초안 생성(LLM 없음).
7. 메인 역할 표시와 이양 기록(진행 중 통합·검사·리뷰·`./develop` 잠금 확인, 인계 메모).

## checks

1. `npm run typecheck`, `npm test`(Node 24) — 기존 31개 + 신규. 신규 회귀: 무과금 가드 각 조건, 가짜 CLI로 실제 어댑터 경로, 수동 모드 전체 흐름, 인계·취소, 로컬 bare 원격 푸시·사후 확인·되돌림·거절 사례(비 fast-forward, 금지 경로, 검사 실패), 진행률 초안, 메인 이양 안전 확인.
2. 브라우저(데모 저장소)에서 수동 모드 → 시작 프롬프트 복사 → 결과 수집 → 인계 → 승인 → 통합 → 푸시(로컬 bare 원격) → 되돌림 흐름 확인.
3. `git diff --check`, 변경 파일이 allowed_files 안인지, 개인 절대경로·비밀값 미포함, 최종 `git status --short` 깨끗함.

## 결과

(인계 시 갱신)

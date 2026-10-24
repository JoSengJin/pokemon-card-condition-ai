# pair-control 실사용 준비 — Claude 배정

- task_id: `pair-control-readiness-20261025`
- owner: Claude
- status: implementing
- base_sha: `4194bf54d3af8901741cabc653e8f58a0cea068b` (시작 시 HEAD, 미커밋 변경 없음 확인)
- branch: `claude/pair-control`
- worktree: 로컬 경로는 세션에서만 전달한다.
- 실행 Node: package.json `engines.node >=22`. 로그인 셸 기본 PATH의 Node 18.20.5는 불충족이므로 nvm v24.21.0으로 실행한다.

## 목표

mock 관제 도구를 실제 프로젝트의 작업 배정·검증·통합에 쓸 수 있도록 실행 준비·계약 기록·독립 검증·리뷰 연결을 추가한다. 화면의 성공 표시가 실제 코드 검증 성공으로 오해되지 않게 한다.

## allowed_files

1. `tools/pair-control/**` (소스·테스트·문서·설정 예제. `node_modules`, `.state`, `.demo`, `.mastra`, `config.local.json`은 Git 제외)
2. `docs/collaboration/tasks/pair-control-readiness-20261025.md` (이 문서)
3. `docs/collaboration/reports/pair-control-readiness-20261025.md` (인계 보고서)

## forbidden_files

위 목록 밖 전부. 특히 `card_condition/`, 기존 `tests/`, `AGENTS.md`, `PAIR_CODING.md`, 루트 `README.md`, 진행률 파일, `data/`, `artifacts/`, 라벨·모델·provider 키. 다른 worktree·브랜치, 기본 checkout은 조작하지 않는다.

## 계약 (보존할 조건)

- 기존 프로세스 감독(detached 그룹)·O_EXCL 잠금·승인 SHA 고정·과금 신호 차단·localhost/Origin 검증을 유지한다.
- 관리용 LLM·범용 프레임워크를 추가하지 않는다. 기존 Mastra workflow·실행기·저장 구조를 재사용한다.
- 실제 Claude/Codex 모델 호출, 인증 변경, API 키 입력, 유료 기능, main 통합·push를 하지 않는다. 실제 CLI는 `--version`/`--help`까지만.
- 검사 명령은 executable·args·cwd 구조로만 받고 셸 문자열로 실행하지 않는다. 사용자 확인 없이 실행하지 않는다.
- 의존성 설치·모델 다운로드·가상환경 생성을 자동으로 시작하지 않는다. 다른 worktree의 가상환경·데이터·키를 공유·symlink하지 않는다.
- 작업 계약은 준비한 작업 브랜치에만 커밋하고 main에는 커밋하지 않는다.

## 구현 항목

1. 연결 상태: 데모/실제 저장소, 저장소 경로, 기준 브랜치, 실제 실행 가능 여부와 차단 원인(CLI 미설치·옵션 미확인·실제 호출 차단·구독 인증 미확인)을 구분 표시. 실행 불가 모드 비활성화. 무료 가드 표현을 "과금 신호 감지 없음"으로 바꾸고 보장으로 표현하지 않음. 내부 설명은 고급 안내로 이동.
2. 계약: 목표·허용 파일·완료 조건·검사 명령·통합 후 검사·상세 지시를 하나의 계약으로 `docs/collaboration/tasks/<task-id>.md`에 작업 브랜치 커밋. 계약 SHA·해시를 실행 기준과 연결. 재시도 시 중복 커밋·worktree 없음. 실제 CLI에는 계약 파일 경로만 전달. 계약이 바뀌면 검사·승인 무효화.
3. 환경: worktree 생성과 실행 준비를 구분. `./develop`·Python 작업은 자체 `.venv/bin/python` 필요, symlink 금지, import 경로가 자기 worktree인지 확인. 표준 라이브러리/프로젝트 의존성 구분. 준비 명령은 안내만.
4. 검증: "Git 계약 검사", "작업 테스트", "통합 후 검사" 분리. 작업 테스트는 사용자 확인 후 실행기가 별도 감독 프로세스로 실행하고 SHA·명령·종료코드·로그·시각을 기록. 미실행≠통과. SHA·계약 변경 시 무효화. 통합 후 검사 실패는 성공으로 표시하지 않고 복구 SHA를 남김(자동 reset 없음).
5. 리뷰: 고정 SHA·diff·계약·검사 결과 묶음으로 별도 리뷰 작업(구현 worktree 미수정, 별도 CLI 실행)을 등록. 결과는 승인/수정 필요/근거 부족. fake CLI로 검증. 리뷰 결과는 사람 승인·통합을 대신하지 않음.

## checks

1. `npm run typecheck` (tools/pair-control, Node 24)
2. `npm test` — 기존 13개 + 신규 회귀: 준비→계약 커밋→실행→Git 검사→작업 테스트→리뷰→승인→통합, 환경 미준비 시작 차단, CLI 0·테스트 실패 시 승인 차단, 코드·계약·기준 브랜치 변경 시 무효화, 검사 중 재시작·중단·결과 불명 무재실행, 병렬·충돌, 통합 충돌·통합 후 검사 실패 표시, 원본 저장소·다른 작업·비밀값 보존.
3. 브라우저에서 데모 저장소로 주요 흐름 확인.
4. `git diff --check`, 변경 파일이 allowed_files 안인지, 개인 절대경로·비밀값 미포함, 최종 `git status --short` 깨끗함.

## 결과

(인계 시 갱신)

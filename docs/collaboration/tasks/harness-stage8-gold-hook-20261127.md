# 하네스 8단계 — Gold 수집·중단 훅 (2026-11-27)

```text
task_id: harness-stage8-gold-hook-20261127
owner: Claude (메인 세션이 배정, 구현은 하위 에이전트)
status: implementing
base_sha: 805d9c713ed572ecb059e0b9a657d78f3b90a0d9 (1~3·5~7단계와 route를 통합한 브랜치)
branch: claude/harness-gold-20261127
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: 훅을 설치하지 않은 상태에서, 실제 프로세스에 표준입력 JSON을 넣어 호출했을 때
  (1) 발급한 화면의 Gold 붙여넣기가 원문 바이트 그대로 한 번만 저장되고,
  (2) 발급 안 된·재사용 nonce, 형식 오류, 직접 판정 확인 누락, 완료 키 재저장, 훅 표식 없는 직접 저장이 거절되며,
  (3) "중단"이 opstate의 USER_STOPPED로 읽힌다.
  IMPLEMENTATION 2절 8행의 "휴대폰 시험 제출"과 설치 후 동작은 범위 밖(설치 보류, 미검증으로 인계).
allowed_files:
  - harness/gold_issue.py, harness/gold_store.py, harness/gold_hook.py, harness/gold_parse.py (신규)
  - 함수 수 제한 때문에 필요할 때만 추가하는 harness/ 아래 신규 파일(추가하면 이 목록에 기록)
  - harness/hooks/user_prompt_submit.py, harness/hooks/settings-snippet.json.template (템플릿 파일만, 설치 안 함)
  - tests/test_harness_gold_*.py (신규)
  - 이 task 문서
forbidden_files: 기존 harness/*.py 전부(1~7단계·route·supervisor, 공개 함수 호출만), tools/**, card_condition/**,
  다른 tests/**, AGENTS.md, docs/agent/**, 다른 plan 문서, artifacts/**, data/**, .claude/**, ~/.claude/**,
  실제 라벨·사진·모델·비밀 설정
contract:
  승인 범위: 코드 구현과 사전 검증만(D-7은 설치만 보류). Claude Code 설정에 훅 등록, 보호 사용자 생성, sudo 규칙,
    launchd 설치는 하지 않는다. `claude` 실행은 `--help` 읽기만, 설치본 파일은 읽기만, 네트워크 없음.
  명세: DESIGN 5-2·13절만. HTML 화면 생성, 평가기(9단계), 외부 AI, 실제 라벨 파일 읽기·쓰기는 하지 않는다.
  호출만 하는 기존 공개 함수: ledger.append/verify, opstate.load/effective/set_condition
    (시험은 supervisor.run, queue.enqueue도 호출).
  보존: 기존 하네스 시험 250개(805d9c7, 3.12·3.9 rc=0 확인) 통과, 기존 파일 무수정.
  제약: stdlib만. 런타임 상태는 호출자가 준 root 아래에만.
structure: 파일당 함수 정의 ≤7(클래스 메서드·중첩·lambda 포함), 공개 진입 함수 호출 깊이 ≤4(1단계 호출 합산, ast로 재측정).
  모두 신규 파일이라 변경 전 함수 수는 0. 시험 파일은 깊이 제외, 함수 정의·테스트 ≤7.
checks:
  - cwd=worktree에서 `PYTHONDONTWRITEBYTECODE=1 <python> -m unittest discover -s tests -p "test_harness_*.py" > 파일 2>&1; echo rc=$?`
    (기본 checkout .venv 3.12와 /usr/bin/python3 3.9 둘 다, 기존 250개 포함)
  - 변이 시험(임시 복사본, 원본 수정 금지)
  - ast 함수 수·호출 깊이, `git diff --check`, `git diff --name-only 805d9c7 HEAD`가 허용 파일 안, git status 깨끗
experiment: 없음. 합성 시험이며 모델 성능 근거가 아니다.
handoff: 아래 "인계" 절
```

## 구현 명세 (배정 프롬프트 요약)

| 항목 | 내용 | 설계 근거 |
|---|---|---|
| 발급 `gold_issue` | 화면 ID·일회용 nonce(`secrets`) 발급, 발급 기록을 먼저 남김(1단계 ledger). 화면 데이터에 예측 필드 없음, "직접 판정" 확인 칸 값이 필요하다는 정보. HTML 생성 없음 | 5-2의 1 |
| 파싱 `gold_parse` | `# 화면=`·`zN=값` 붙여넣기와 "중단"을 구분. 형식 오류·모르는 값·누락·중복 키·nonce 형식 오류는 명시적 오류. 직접 판정 확인이 없으면 거절 | 5-2의 2·4, 13 |
| 훅 `gold_hook` + 진입점 | 모델보다 먼저 `UserPromptSubmit` 입력을 받아 Gold는 원문 저장, "중단"은 USER_STOPPED | 5-2의 3, 13 |
| 저장 `gold_store` | 추가 전용 해시 체인, 출처 human 고정, 훅 진입 표식 없는 쓰기 거절, 완료 키 (이미지 SHA, 구역, 기준 판본, 판정자) 재저장 거절, 계획된 재판정은 플래그로 구분 | 5-2의 4·5 |

## 인계

(구현 후 작성)

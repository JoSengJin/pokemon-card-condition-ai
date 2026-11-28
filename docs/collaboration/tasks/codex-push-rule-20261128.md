# codex-push-rule-20261128 — Codex push 승인 규칙 변경안과 판정 검사 도구

```text
task_id: codex-push-rule-20261128
owner: (시작하는 에이전트가 기록)
status: open
depends_on: []
base_sha: (시작하는 에이전트가 worktree를 만든 main SHA를 기록)
branch: (시작하는 에이전트가 <agent>/<task-id>로 기록)
goal: 사용자가 직접 적용할 Codex 규칙 변경안과, 그 판정을 모델 호출 없이 확인하는 검사 도구·적용 안내를 만든다. 아래 고정 기준 표의 필수·보존 행이 모두 통과하고, 관찰 행은 실제 판정 그대로 표시된다.
allowed_files:
- tools/diagnostics/codex-push-rule-20261128/check_push_rules.py
- tools/diagnostics/codex-push-rule-20261128/test_check_push_rules.py
- tools/diagnostics/codex-push-rule-20261128/proposed.rules
- tools/diagnostics/codex-push-rule-20261128/README.md
- tools/diagnostics/codex-push-rule-20261128/report.html
forbidden_files: 위 5개와 이 계약 문서를 뺀 전부
contract: 아래 "동작 계약"과 "고정 기준 표"
structure: 신규 Python 파일 2개. 파일당 함수 7개 이하, 호출 전이 4회 이하. handoff에 파일별 함수 수와 가장 긴 호출 경로를 적는다.
checks:
- python3 tools/diagnostics/codex-push-rule-20261128/test_check_push_rules.py
- python3 tools/diagnostics/codex-push-rule-20261128/check_push_rules.py --rules ~/.codex/rules/default.rules --candidate tools/diagnostics/codex-push-rule-20261128/proposed.rules
- git diff --check
- git diff --name-only <base_sha> 가 allowed_files + 계약 문서 안인지 확인
- report.html 생성, 내용 대조, 열기 (열기 성공과 렌더 확인을 구분해 기록)
experiment: 해당 없음 (모델 학습·추론·실험·라벨 작업 없음)
done: []
next: 고정 기준 표대로 검사 도구와 시험을 작성한다. 판정 결과를 보기 전에 기준 표를 코드에 옮긴다.
unrecovered: []
handoff:
```

## 배경

- 2026-11-28 확인: 사용자 전역 규칙 `~/.codex/rules/default.rules`에 `["git","push","origin","main"]` allow와 `["./develop","--","git"]` allow가 있다. codex-cli 0.164.0.
- 공식 문서: https://learn.chatgpt.com/docs/agent-configuration/rules.md — 여러 규칙이 일치하면 forbidden > prompt > allow.
- 판정 명령(모델 호출 없음): `codex execpolicy check --rules <파일> -- <명령 토큰들>`

## 동작 계약

- 검사 도구는 `--rules`와 `--candidate`의 **임시 사본**만 `codex execpolicy check`에 넘긴다. 원본에 쓰지 않는다. 표의 명령은 토큰으로 판정만 하고 **실행하지 않는다**.
- 행마다 "현재(rules만)"와 "적용안(rules + candidate)" 판정, 결과(통과/실패/일치/한계)를 출력한다. 필수·보존에 실패가 하나라도 있으면 종료 코드 0이 아니다. `codex`가 없거나, 오류가 나거나, 출력을 해석하지 못하면 통과로 보지 않고 실패한다.
- 시험은 임시 폴더의 합성 규칙 파일을 쓴다. 개인 규칙 파일 내용과 홈 절대경로를 저장소 파일(report.html 포함)에 넣지 않는다.
- `proposed.rules`의 시작안: `["git","push"]`와 `["./develop","--","git","push"]`를 `prompt`로 둔다(미적용 관문 초안 2026-11-25의 push 부분과 같은 형태). push 밖의 통합 명령 관문, 훅, 메인 등록은 범위 밖이다.
- Python 표준 라이브러리만 쓴다. 이 작업은 `.venv`를 만들지 않는다.
- README에는 사용자가 직접 실행할 적용 명령, 적용 확인 방법, 롤백, 기존 allow 줄을 남길지와 그 이유, 규칙이 못 막는 것, 미검증 항목을 적는다. 확인하지 못한 Codex 동작(규칙 파일 로딩·재시작 등)은 미검증으로 적는다.

## 고정 기준 표

판정 결과를 본 뒤 행의 분류나 기준을 바꾸지 않는다. 바꿔야 하면 멈추고 `next`에 이유를 적는다.
알려 둠: 이전 예비 확인에서 `git push`, `git push origin main`, `git push origin HEAD:main`의 prompt와 `git -C`·`/usr/bin/git`·`zsh -lc` 형태의 불일치는 이미 관찰했다. 그래서 이 표는 완전한 사전 맹검 기준이 아니다.

| 분류 | 명령 형태 | 기준 |
|---|---|---|
| 필수 | `git push` | 적용안이 prompt 또는 forbidden |
| 필수 | `git push origin main` | 위와 같음 |
| 필수 | `git push origin HEAD:main` | 위와 같음 |
| 필수 | `./develop -- git push` | 위와 같음 |
| 필수 | `./develop -- git push origin main` | 위와 같음 |
| 보존 | `git commit -m x` | 적용안 = 현재 판정, prompt·forbidden 아님 |
| 보존 | `git fetch origin main` | 위와 같음 |
| 보존 | `git status` | 위와 같음 |
| 보존 | `git diff --cached --name-only` | 위와 같음 |
| 보존 | `./develop -- git commit -m x` | 위와 같음 |
| 보존 | `./develop -- git status` | 위와 같음 |
| 관찰 | `git -C . push origin main` | prompt·forbidden이면 "일치", 아니면 "한계". 통과로 세지 않음 |
| 관찰 | `git -c push.default=current push` | 위와 같음 |
| 관찰 | `/usr/bin/git push origin main` | 위와 같음 |
| 관찰 | `env git push origin main` | 위와 같음 |
| 관찰 | `/bin/zsh -lc "git push origin main"` | 위와 같음 |
| 관찰 | `./develop -- /usr/bin/git push origin main` | 위와 같음 |
| 관찰 | `git send-pack origin main` | 위와 같음 |

원본 불변: 시험은 도구 실행 전후 입력 규칙 파일의 SHA-256이 같은지 확인한다.

## 금지

- 원격 push와 push 시도(dry-run, 임시 원격 포함). 표의 명령을 실제로 실행하는 것.
- `~/.codex` 아래 파일, Claude 설정, 훅, 승인·신뢰 설정 변경. 규칙 적용은 사용자만 한다.
- 승인창 실제 시험. 별도 관문 설계 세션이 시험 중이며 그 시험 폴더(`../pokemon-card-condition-gate-*`)를 읽거나 쓰지 않는다. 이 작업의 보고에서 "사람 승인이 강제된다"고 쓰지 않고 **미검증**으로 둔다.
- 모델 호출, 기존 미추적 파일 커밋, 새 관문·승인 서버·장부.

## 통합·원격 반영 (2026-11-28 사용자 결정, 낡은 문서보다 우선)

- 이 작업의 메인은 Claude다. 구현 담당은 사용자가 여는 Codex 세션이다.
- 계약 커밋, 통합, push는 각각 사용자의 직접 승인을 받는다. 상시 승인, 이전 승인, 자동 알림은 승인이 아니다.
- claim은 메인이 통합 검사 때 본 claim OID를 기대값으로 해서만 삭제한다(스킬 수정 af36511은 미통합).

## 롤백

구현은 통합 커밋 `git revert`, 통합 전이면 통합하지 않는다. 사용자가 규칙을 적용했다면 README의 롤백 절차를 따른다.

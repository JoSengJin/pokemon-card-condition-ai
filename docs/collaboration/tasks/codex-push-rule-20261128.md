# codex-push-rule-20261128 — Codex push 승인 규칙 변경안과 판정 검사 도구

```text
task_id: codex-push-rule-20261128
owner: Codex
status: ready_for_review
depends_on: []
base_sha: 17bd21fa59eeb1a37e91c062ef315573be81db6c
branch: codex/codex-push-rule-20261128
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
done:
- 사용자 승인 범위로 기본 checkout의 추적 변경·스테이지·진행 중 Git 작업을 확인하고, 선점과 전용 worktree 생성을 완료했다.
- 판정 전에 고정 표 18행을 그대로 옮겼다. 규칙 제안·임시 사본 검사 도구·합성 시험을 작성했고, Codex CLI 0.164.0에서 합성 시험 6개와 계약 표 대조가 통과했다.
- 현재 사용자 규칙 사본의 고정 판정과 두 입력 SHA-256 불변을 확인했다. 적용·복구 안내와 HTML 근거를 작성하고 검증했다.
next: 메인 Claude가 작업 브랜치 tip과 계약 기준으로 검토한다.
unrecovered: []
handoff:
- 검증 코드 SHA: ca71cc25dbda5555428134dc16c26c8ebb9a7c65. 이 인계 커밋은 안내·HTML·계약만 더한다. 인계 커밋 SHA는 작업 브랜치 tip을 참조한다.
- 변경 파일: 이 계약 문서와 allowed_files의 5개. 검사기·시험·prompt 제안을 추가하고 적용·확인·롤백 안내와 근거 HTML을 기록했다.
- 구조(AST 검사): check_push_rules.py 0→3개, test_check_push_rules.py 0→7개. 같은 프로세스의 신규 함수 사이 최대 전이 1회(main → policy_decision 또는 classify). 합성 시험이 검사기를 새 프로세스로 실행하는 경로는 unittest → 시험 메서드 → run_check → 검사기 main → policy_decision이며, 첫 unittest 호출을 포함해 4회다.
- 검사(작업 루트, Codex CLI 0.164.0): 위 test_check_push_rules.py 명령 종료 0, 6개 통과. 위 check_push_rules.py 명령 종료 0. 필수 5/5, 보존 6/6, 관찰 0 일치·7 한계. 두 입력의 SHA-256은 실행 전후 동일. CLI 성공 출력의 판정만 사용했다.
- 현재 규칙 사본의 일부 판정은 계약 배경의 과거 allow 관찰과 다르게 나왔다. 과거 근거는 보존했고 현재 수용 기준을 바꾸지 않았다. 합성 시험에서 allow와 prompt가 함께 적용되면 prompt가 이기는 것을 별도로 확인했다.
- 고정 표 18행 순서·명령·분류 대조, HTML 표와 합성 TSV 18행 대조, HTML 상대 링크 검사, README의 sh -n, git diff --check, 기준 SHA 대비 허용 경로 대조 통과.
- HTML: tools/diagnostics/codex-push-rule-20261128/report.html. macOS open 종료 0, Chrome에 제목과 일치한 탭 생성 확인. 브라우저 관찰 도구의 file: 접근 제한으로 화면 렌더는 미확인이다. 진척 정본 PROGRESS_CRITERIA.md와 development-progress.json의 78/100(v1.14, 동일기준 대비 0%p)을 표시했다.
- 미검증·리스크: 실제 승인창과 재시작 후 규칙 적용은 확인하지 않았다. 관찰 변형 7행은 두 입력 사본에서 제한과 일치하지 않았다. 모델 성능 변화는 미측정이다.
- 롤백: 통합 전에는 채택을 보류할 수 있고, 통합 후에는 통합 커밋을 revert한다. 제안 규칙을 직접 설치한 경우 README의 추가 파일 제거 절차를 따른다.
- 적용 절차: pair-coding, Ponytail, 완료 전 검증, short-request-reading. PAIR_CODING.md와 docs/AGENT_START.md의 계약을 기준으로 base_sha부터 직접 대조했다. 외부 모델 검토는 작업 계약의 금지 범위다.
```

## 첫 체크포인트 사용자 승인 원문

```text
사용자 승인(codex-push-rule-20261128에만 적용): 기본 작업 폴더의 기존 미추적 항목은 PAIR_CODING.md §4의 "깨끗하지 않음"으로 보지 않는다. 추적 파일 변경·스테이지·진행 중 Git 작업이 없으면 pair-coding 시작 2\~3단계를 스킬 명령 그대로 진행해라. 미추적 파일은 읽거나 옮기거나 커밋하지 마라. 이 승인 문장을 첫 체크포인트의 계약에 기록해라.
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

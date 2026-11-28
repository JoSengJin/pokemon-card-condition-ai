# 하네스 B6 상태 조회·시작·중단 1~4단계 (2026-11-28)

```text
task_id: harness-b6-status-20261128
owner: Claude (메인 세션 배정, 구현은 Sonnet 하위 에이전트)
status: ready_for_review
base_sha: d0ec2bc (claude/harness-auto-resume-123-20261127)
branch: claude/harness-b6-status-20261128
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: 합성 root에서 `python -m harness.control status|stop|start`가 동작하고, sandbox 안 executor가 stop·start·상태 파일
  수정으로 사용자 중단을 바꾸지 못하는 것이 실제 sandbox-exec 하위 프로세스 시험으로 확인된다. 해제·재개(B6-5)는 하지 않는다.
allowed_files: harness/status.py, harness/status_tasks.py, harness/status_view.py, harness/control.py, harness/control_start.py,
  tests/test_harness_status_*.py, tests/test_harness_control_*.py, 이 task 문서 (전부 새 파일)
forbidden_files: 기존 harness 소스와 기존 시험 파일 전부(다른 담당이 공통 파일을 다룸), 그 밖의 저장소 파일
contract: opstate·ledger·budget·states·claude_job은 불러 쓰기만 한다. 해제 함수(opstate.clear_by_user, unlock)는 부르지 않는다.
checks: 아래 "시험" 절
experiment: 없음. 실제 claude 실행, 모델·네트워크 호출, 훅·LaunchAgent 설치, 시스템 설정 변경, 실데이터 접근, push, main 통합 없음.
handoff: 이 문서
```

근거 문서(Git 제외, 기본 checkout `artifacts/harness-resume-20261127/`): `pre-b6.md` 2·3절, `decisions-b5-b6-20261128.md`의
B6 결정 2, `vertical-slice-plan-20261128.md` 0'번 줄.

## 커밋

| 단계 | 커밋 | 내용 | 수정 전 실패 |
|---|---|---|---|
| B6-1 | `a0262a2` | `status.py`·`status_tasks.py`: 운영 상태, Supervisor 잠금, 작업·Claude 작업 칸, 시각 미상 한도 횟수, 이번 주 예산, 장부 검증, 최근 알림 3개. 읽기 전용 | `ImportError: cannot import name 'status'` |
| B6-2 | `0a3840d` | `status_view.py`: 20줄 이하 텍스트와 정적 HTML(JS·외부 자원 없음). 모든 줄이 비밀 값 가림 → 홈 경로 가림 → 한 줄 → 160자 자르기를 지남 | 모듈 import 실패 |
| B6-3 | `f161f1f` | `control.py` `status`·`stop`, sandbox 사칭 시험 | `ImportError: cannot import name 'control'` |
| B6-4 | `bda002d` | `control_start.py`, `control.py` `start` | `start` 명령 없음(종료 코드 2), 6개 실패 |
| 정리 | `8094183` | 시험 공용 도구 `test_harness_control_kit.py` 분리(시험 파일당 함수 ≤7) | — |

`git diff --stat d0ec2bc`: 새 파일만 있고 기존 파일 수정은 0이다.

## 동작 요약

- `status`: 파일을 만들거나 고치지 않는다(합성 root 전체의 mtime·sha256 전후 비교 시험). CORRUPT 산출물도 되살리지 않는다.
  상태 파일이 깨졌거나 읽을 수 없으면 RUNNING이 아니라 `INTEGRITY_HALT`·손상으로 보인다. Supervisor 확인은 공유 잠금
  probe(`LOCK_SH`)라 조회 두 개가 서로를 "실행 중"으로 보지 않는다.
- `stop`: `USER_STOPPED`를 `actor=control_cli`로 기록한다. 이미 정지면 기존 `since`·사유를 두고 "이미 중단 상태"라고 말한다.
  기록 뒤 상태 파일을 다시 읽어 확인된 것만 성공으로 말한다. 장부가 손상돼도 상태 파일에 남으면 성공 + 오류 표시.
- `start`: `python -m harness.supervisor`를 별도 세션으로 띄운다(설치 아님). `--claude-bin`·`--executors`는 명시한 것만
  넘긴다. 상대 경로는 절대 경로로 바꾼다. 이미 실행 중이면 종료 코드 4, 확인 불가면 띄우지 않는다. 정지 상태면 "감시만"이라고
  알리고 정지를 풀지 않는다. 자식이 살아 있고 잠금이 보일 때만 "시작 확인"이라고 말한다. 출력은
  `root/supervisor/control_start.log`.
- 세 명령 모두 `supervisor`·`tasks`·`ledger.jsonl`이 하나도 없는 폴더는 거절한다(경로 오타를 정상 상태나 중단 성공으로
  보이지 않게). 담당이 추가한 규칙이다.
- 해제 명령은 없다(`resume`·`release`·`clear`는 종료 코드 2).
- 자동 재개(한도 `clear_auto`)와 사용자 중단 해제는 섞이지 않는다: 재개 시각이 지난 한도 + 사용자 중단 root에서 Supervisor
  3회차 뒤에도 `USER_STOPPED`가 남고 실행 0.

## 증거: 합성 root 실제 실행 (2026-11-28 10:05 KST)

합성 root: 완료 1·대기 3 작업(그중 결과 확인 대기 1, 대기 중 Claude 작업 칸 1), 실험 예산 2 차감, 알림 1, 단기 한도 조건.

```text
$ python -m harness.control status --root <합성 root>
[하네스 상태] 운영 상태 표시(모델 성능·정확도 아님) · 조회 11-28 10:05 KST
상태: 사용량 한도(단기)(RATE_LIMITED_SHORT) · Claude 작업만 멈춤
Supervisor: 실행 중 아님
- 사용량 한도(단기) 11-28 10:05 KST supervisor: 사용량 한도(합성)
사람이 할 일: 대기·실패 항목 2건 확인
자동 재개: 한도 다음 시도 11-28 11:05 KST(약 60분 뒤) · Supervisor가 실행 중이 아니라 켜기 전에는 재개되지 않음
작업: PENDING 3 · VERIFIED 1
확인 대기: 결과 확인 1 · 중단 한도 정지 0 · Claude 대기 1 · 계약 손상 0 · 읽기 실패 0
  결과 확인 대기 6ab59d32ba3a: interrupted
  Claude blocked 3a72b96253c5: auto_resume_disabled: 합성 사유
예산(이번 주): 실험 2/20(남음 18) · 비전 구역 0/300(남음 300)
장부: 작업 장부 정상 · 알림 장부 정상
최근 알림:
  11-28 10:05 KST claude_job_blocked 합성 알림: Claude 작업 대기
(종료 코드 0)
$ python -m harness.control stop --root <합성 root>
중단 기록 확인: USER_STOPPED. 새 작업은 시작하지 않는다. 이미 실행 중인 claude·executor는 끊지 않는다(끝날 때까지 돌며 사용량을 쓸 수 있다). 해제는 사용자만 하며 이 명령줄에는 해제 명령이 없다.
(종료 코드 0)
$ python -m harness.control stop --root <합성 root>
이미 중단 상태: USER_STOPPED가 기록되어 있어 기존 기록을 그대로 둔다. 새 작업은 시작하지 않는다. 이미 실행 중인 claude·executor는 끊지 않는다(끝날 때까지 돌며 사용량을 쓸 수 있다).
(종료 코드 0)
$ python -m harness.control status --root <합성 root>
[하네스 상태] 운영 상태 표시(모델 성능·정확도 아님) · 조회 11-28 10:05 KST
상태: 사용자 중단(USER_STOPPED) · 새 작업을 시작하지 않음
Supervisor: 실행 중 아님
- 사용자 중단 11-28 10:05 KST control_cli: control CLI: 중단
- 사용량 한도(단기) 11-28 10:05 KST supervisor: 사용량 한도(합성)
사람이 할 일: 사용자 중단 해제는 사용자만(해제 명령은 아직 없음); 대기·실패 항목 2건 확인
자동 재개: 없음(정지 조건이 있는 동안 Supervisor는 아무것도 시작하지 않고, 정지는 자동으로 풀리지 않음)
작업: PENDING 3 · VERIFIED 1
(이하 앞 조회와 같음)
(종료 코드 0)
$ python -m harness.control start --root <합성 root> --max-cycles 1
시작해 이미 끝남(pid 46716, 종료 코드 0). Python 작업: 끔(--executors 없음) · Claude 작업: 끔(--claude-bin 없음). 정지 상태(USER_STOPPED)라 감시만 하고 어떤 작업도 시작하지 않는다. start는 정지를 풀지 않는다(해제 명령 없음). 결과: {"claude_runs": 0, "cycles": 1, "outcomes": [], "python_runs": 0, "state": "USER_STOPPED"}
(종료 코드 0)
```

`root/ledger.jsonl`의 `opstate_transition` 줄(실행 뒤 `ledger.verify` 문제 `[]`):

```text
{"data": {"actor": "supervisor", "condition": "RATE_LIMITED_SHORT", "effective_after": "RATE_LIMITED_SHORT", "effective_before": "RUNNING", "extra": {"next_try_at": 1795831550.284405}, "op": "set", "reason": "사용량 한도(합성)"}, "event": "opstate_transition", "hash": "76bdf7492385827f9b96eb91f90704200c9e908340e8ae516c299078af9a95db", "prev": "acf4711f314f9d58c0894c88c53675de8b7dac1636e8bbb185c15d56868efc4d", "seq": 6, "ts": 1795827910.284405}
{"data": {"actor": "control_cli", "condition": "USER_STOPPED", "effective_after": "USER_STOPPED", "effective_before": "RATE_LIMITED_SHORT", "extra": {}, "op": "set", "reason": "control CLI: 중단"}, "event": "opstate_transition", "hash": "1c1ae21a08913b30210960437c45206e5a524dc3d19efee4f212f0da0c37aa1d", "prev": "76bdf7492385827f9b96eb91f90704200c9e908340e8ae516c299078af9a95db", "seq": 7, "ts": 1795827950.495157}
```

같은 root의 `status --html` 출력은 macOS `qlmanage` 썸네일(폭 900, 어두운 화면)로 렌더를 확인했다. `http`·`<script`·`/Users/`는
0건이다. 폰 폭·폰 브라우저에서는 확인하지 않았고 사용자에게 열지는 않았다. 합성 상태 표시이며 모델 성능과 무관하다.

## 사칭 방지 시험

`tests/test_harness_control_sandbox.py`: runner가 쓰는 `sandbox.run_one`(실제 `/usr/bin/sandbox-exec`, 운영 프로필 그대로)으로
공격 executor를 실행한다.

- 사용자 중단 root: 하위 프로세스 `control stop`·`control start`, `control.main` 직접 호출, `python -m harness.supervisor`,
  `opstate.clear_by_user(actor="user")`, 상태 파일 덮어쓰기·원자 교체·삭제, `supervisor/` 이름 바꾸기, 장부 열기 → 쓰기 시도는 모두
  `PermissionError`, `start`는 종료 코드 1 "시작하지 못함", Supervisor는 비정상 종료. root 전체의 mtime·sha256이 전후 같다.
- 정지 전 root: sandbox 안 `stop`은 종료 코드 1 "중단을 기록하지 못함"이고 상태는 RUNNING 그대로(거짓 성공 없음).

## 시험

- 개발 중: 새 모듈 5개 23개, `.venv` Python 3.12.14와 `/usr/bin/python3` 3.9.6 모두 OK. B6-3 시점에 기존
  `test_harness_gold_stop`·`test_harness_supervisor_unlock`(자동 해제 호출 경로 ast 검사) 포함 17개 OK.
- 변이(scratchpad 사본에 결함 주입, 3.12) 20개 모두 잡힘: probe 배타 잠금, probe가 잠금 파일 생성, 손상 상태를 RUNNING,
  대기 사유 누락, 가림 제거, 홈 경로 가림 제거, 자르기 제거, HTML 이스케이프 제거, 정지 중 자동 재개 표시, 이미 정지 확인 생략,
  재확인 읽기 생략, actor를 user로 고정, 빈 사유 전달, root 확인 생략, 실행 중 확인 생략, claude 상대 경로 그대로, 새 세션 생략,
  정지 안내 생략, 실패를 성공으로, sandbox 쓰기 거절 제거. 처음에는 2개(정지 중 자동 재개 표시, 실행 중 확인 생략)가 살아남아
  시험을 고쳤다. 결함을 넣은 사본이 남긴 supervisor 프로세스는 cwd로 내 것임을 확인하고 종료했다.
- 전체 시험 1회(`PYTHONDONTWRITEBYTECODE=1 <python> -m unittest discover -s tests -p "test_harness_*.py"`, 공용
  `full-suite.lock` 안, 10:18:58~10:26:03, 코드 HEAD `8094183`, 미커밋은 이 문서 1개): `.venv` 3.12.14 449개 OK(199.5초),
  `/usr/bin/python3` 3.9.6 449개 OK(224.7초), 두 실행 모두 종료 코드 0, 순차 실행. 이 문서 커밋은 문서만 바꾼다.
- `git diff --check d0ec2bc`: 문제 없음.

## 구조

- 함수 정의 수(새 파일, 전 0): `status` 3, `status_tasks` 1, `status_view` 5, `control` 2, `control_start` 1. 시험:
  `status_collect` 7, `status_view` 7, `control_stop` 7, `control_start` 6, `control_sandbox` 5, `control_kit` 5. lambda 0.
- 최대 호출 깊이 4, 4 초과 0(`verify-123-scripts/structure_measure.py`). 주요 경로: `control.main → status.collect →
  status_tasks.scan → states.facts → 말단`(4), `control.main → control.stop → opstate.set_condition → opstate.load →
  read_json`(4), `control.main → control_start.start → opstate.load → read_json`(3).
  정적 도구가 못 보는 동적 호출 하나(`control.main`의 `render` 변수)는 직접 확인: `main → render_html → render_text →
  _clean → evidence.mask`(4, `render_text → _resume → _when`도 4).

## 사용자 확인 필요

아래는 사용자가 정하지 않아 현 설계 기본값을 적용한 것이다(`pre-b6.md` 5절).

1. **결정 3, 중단이 실행 중 작업까지 끊을지**: 기본값 = 새 작업만 막는다. 이미 도는 claude·executor는 끝날 때까지 돌며 사용량을
   쓸 수 있다(긴 작업은 `claude_run`·`PYTHON_TOTAL_S`의 총 시간 제한까지). 확인과 runner의 claim 사이(밀리초) 틈도 그대로다.
2. **결정 5, `awaiting.json`·blocked 작업 해제**: 기본값 = 상태 조회에 표시만 한다. 해제는 기존 수동 절차다.
3. **결정 6, Supervisor 실행 정보 범위**: 기본값 = 잠금 probe만. pid·시작 시각은 모른다. 더 알려면 `supervisor.py`(공통 파일)
   수정이 필요하다.
4. 담당이 정한 작은 규칙: 하네스 흔적이 없는 폴더 거절, 정지 상태에서도 `start`는 띄우고 "감시만" 안내(HARNESS_RULES의
   "Supervisor는 상시 실행할 수 있다" 근거).

이번 범위 밖: B6-5 해제·재개(결정 2 조건부 승인, 훅 코드만), 결정 1·4·7.

## 한계·리스크

- sandbox 시험이 보증하는 것은 "sandbox 안 executor는 못 바꾼다"까지다. 같은 macOS 사용자의 다른 프로세스(대화형 Claude,
  Codex, 셸)는 상태 파일을 고치거나 해제 함수를 직접 부를 수 있다. `actor` 문자열은 출처 기록일 뿐 인증이 아니다.
- 실제 claude, 실제 실험 executor, 폰·RC에서의 조회·중단·시작은 검증하지 않았다. `--claude-bin`에 실제 claude를 넘기는 것을
  코드가 막지는 않는다(실행은 별도 승인 대상).
- 잠금 확인 순간에 Supervisor가 시작하면 그 시작 한 번이 `already_running`이 될 수 있다(`status`·`start` 공통).
  `start`의 "시작 확인"은 잠금 주인이 그 자식인지까지는 증명하지 못한다(잠금 파일에 pid 없음, 코드에 `shortcut:` 표시).
- `status`는 `states.facts`를 써서 완료 작업의 산출물을 매번 해시한다. 산출물이 크고 많아지면 조회가 느려진다.
- `charge`와 겹친 순간의 조회는 예산 장부를 일시적으로 오류로 보일 수 있다(다시 조회). 승격 예산(봉인 주기 ID 필요)은 요약에 없다.
  `DONE`을 켜는 코드는 여전히 없다.
- 가림은 최선 노력이다(`evidence.mask` 형식 밖의 비밀, `/Users`·`/home`·홈 밖 경로는 남을 수 있다). `stop`·`start`의 문장은
  요약의 가림 경로를 지나지 않는다: `start` 실패 때 보이는 로그 끝부분은 `evidence.mask`만 적용해 홈 경로가 보일 수 있다.
- `control_start.log`는 회전하지 않는다. `start`는 `--claude-idle-s` 등 시간 제한 인자를 넘기지 않는다(기본값 사용).
- 성과·진척 HTML(`docs/collaboration/HTML_REPORTING.md`)은 이 하위 작업에서 만들지 않았다. 모델 학습·추론·성능 평가는 없고
  정확도 변화는 없다.

## 롤백

새 파일만이라 이 브랜치의 커밋을 역순으로 `git revert`하거나 브랜치를 통합하지 않으면 된다. 기존 저장 형식 변화는 없다. 실행
중 생기는 새 파일은 `start`의 `supervisor/control_start.log`뿐이다. 실운영 root는 아직 없다.

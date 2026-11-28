# 하네스 B6-5 사람 해제·재개 + B6-6 해제용 훅 문구 (2026-11-28)

```text
task_id: harness-b6-release-20261128
owner: Claude (메인 세션 배정 하위 에이전트)
status: ready_for_review
base_sha: 1b52418 (= 3a3bc84 통합본 + ANALYZE 입력 병합)
branch: claude/harness-b6-release-20261128
worktree: 로컬 경로는 커밋하지 않음(세션 전달)
goal: 사람이 이름 하나를 지정해 근거를 본 뒤 1회용 확인 코드로 정지를 푼다(터미널·훅 문구 둘 다). 문구만·지난 코드·sandbox executor·
  A묶음 산출물 위조로는 풀리지 않는다. 훅 설치는 하지 않는다(코드·합성 시험만).
changed_files: harness/control_release.py(신설), harness/hooks/user_prompt_submit.py, tests/test_harness_supervisor_unlock.py(허용 목록),
  harness/control.py·control_start.py·status_view.py(안내 문구만), tests/test_harness_control_stop.py(주석만),
  tests/test_harness_control_release*.py·tests/test_harness_release_kit.py(신설), 이 문서
experiment: 없음. 실제 claude 실행, 모델·네트워크 호출, 훅·LaunchAgent 설치, 시스템 설정, 실데이터, push, main 통합 없음.
```

근거(Git 제외, 기본 checkout `artifacts/harness-resume-20261127/`): `pre-b6.md` 3절 B6-5·B6-6, 5절 결정 1~7,
`decisions-b5-b6-20261128.md` "B6 결정 2"(조건부 승인 원문).

## 커밋

| 커밋 | 내용 | 수정 전 실패 |
|---|---|---|
| `b65fae6` | `control_release.py`·훅 분기·허용 목록·시험 4파일 | 새 시험 2파일 `ImportError: cannot import name 'control_release'` |
| (이 문서 커밋) | task 문서(전체 시험 결과 포함) | — |

## 결정 적용 (메인 기본값, 사용자 변경 가능)

| 결정 | 적용 | 근거 |
|---|---|---|
| 1 = A | `harness/control_release.py` 신설. `test_no_automatic_call_path` 허용 목록에 이 파일 이름 하나만 정확 일치로 추가 | 기대 변경 기록은 아래 "기존 시험 기대 변경" |
| 2 (사용자 조건부 승인 원문) | 문구·터미널 입력만으로 풀지 않는다: 1단계 코드 + 2단계 대조. 신뢰할 수 없는 입력(형식 오류·코드 없음·불일치·만료·다른 대상·대조 실패·쓰기 거절)은 모두 중단 유지. 새 서버·인증 서비스 없음 | 결정 원문. 코드는 인증이 아님을 출력·장부 사유에 그대로 적는다 |
| 3 = A | 해제는 새 작업 시작만 다시 허용. 실행 중 작업은 원래 끊지 않으므로 해제가 건드릴 것 없음 | `supervisor.py` 현 설계 |
| 4 = A | 한도 조건을 사람이 풀어도 `claude_unknown_limit.json` 횟수는 그대로, 값만 보고("3/3 그대로") | 재시도 횟수 확대 금지. 변이 M9가 잡는다 |
| 5 = A | `awaiting:`·blocked는 대상 아님 → "상태 조회로 보고 수동 절차" 안내 | 해제 의미 미정 |
| 6 = A | Supervisor 확인은 기존 잠금 probe 그대로(이 작업에서 바꾸지 않음) | |
| 7 | DONE은 대상 목록에서 뺐다(`CONDITIONS`). DONE을 켜는 제어도 없음 | |

## 동작

- 대상: 운영 조건 이름 하나(INTEGRITY_HALT·USER_STOPPED·BUDGET_EXCEEDED·한도 3종) 또는 `interrupts:<키>`·`holder:<키>`(unlock). 한 번에 하나, "전부 해제" 없음(`--target` 필수).
- 1단계 `python -m harness.control_release --root R --target T`: 근거(since·actor·reason·next_try_at·exhausted·unknown_attempts, 작업은 stopped.json·lease.json) 출력, 표준 오류로 6자리 코드. 파일 `supervisor/release_challenge.json`에는 sha256(salt+코드)만. 장부 `release_challenge issued`.
- 2단계 `... --code C --reason 사유 --confirm`: `supervisor/release.lock` 안에서 대조, 맞으면 기록을 먼저 지우고(1회) 해제. 3번 틀리거나 10분 지나면 폐기, 새로 받으면 이전 코드 무효. 거절은 모두 장부 `release_challenge rejected`(사유). 해제 장부(`opstate_transition clear`, actor="user")의 사유에 `경로=hook|terminal`과 "인증 아님"을 남긴다. 결과는 상태를 다시 읽어 확인한 사실만 말한다.
- 훅: `재개 T` → 종료 코드 2 + stderr(설치본 문자열 기준 사용자에게만 보이고 프롬프트를 지움 = 모델은 요청·코드를 못 봄). `재개 T C` → 2단계(종료 코드 0, 결과는 표준 출력). `재개` 단독·형식 오류는 안내만. `재개해` 같은 문장은 이 분기가 아니다(기존 Gold·중단 훅으로 감).
- 자동 재개와 구분: 한도 조건 자동 해제는 Supervisor `opstate.clear_auto`뿐(USER_STOPPED는 거절, 기존 시험 `test_limit_auto_resume_never_lifts_a_user_stop`). 하네스 코드는 `control_release`를 부르지 않는다(ast 단언 추가).

구조: `control_release.py` 함수 6개. 호출 깊이(`tests/harness_depth_kit.longest`): `answer` 4(→ clear_by_user → _clear → load → read_json), `request` 3, `evidence` 2, `_take` 1. 시작 함수 `answer`·`request`·`from_prompt`는 `__main__` 블록과 훅 진입점이 직접 부른다(supervisor.py `_args`+`__main__`과 같은 형식). `unlock.release_*`는 변수로 골라 불러 정적 측정 밖이다: 그 경로는 answer → release_interrupts → holder.verdict → lease.pid_alive 3(수동 확인). 시험 파일 함수 수 4·5·4·4, 변경한 기존 파일 함수 수 변화 없음(control 2, control_start 1, status_view 5).

## 기존 시험 기대 변경

| 시험 | 이전 기대 | 새 기대 | 근거 |
|---|---|---|---|
| `test_harness_supervisor_unlock.test_no_automatic_call_path` | `unlock`·`release_*`는 unlock.py 밖, `clear_by_user`는 opstate.py 밖 금지 | 허용 파일에 `control_release.py` 이름 하나 추가(정확 일치). 새 단언: `control_release.py` 밖 harness/*.py는 `control_release` 이름을 쓰지 않는다 | 결정 1 A. 나머지 모듈은 여전히 금지이며, 해제 진입점을 부르는 자동 경로가 생기면 새 단언이 잡는다(변이 M8로 control.py에 `clear_by_user`를 넣으면 실패 확인) |
| `test_harness_control_stop` 46행 | 주석 "해제 명령은 없다(B6-5 미구현)" | 주석만 갱신. 단언(control에 resume·release·clear 명령 없음 = 종료 코드 2)은 그대로 | 해제는 별도 진입점이라 control의 기대는 바뀌지 않는다 |

## 시험

- 새 시험 9개: `test_harness_control_release.py` 3(터미널 2단계·재생 거절·해제 뒤 supervisor.run 재시작 / 훅 문구만·이전 코드·다른 대상·형식 오류 / 3회 오답·만료·다른 대상 + 장부 거절 수), `test_harness_control_release_targets.py` 4(대상 규칙·손상 opstate 무변경 / 소진 한도 횟수 유지 / interrupts 잠금 중 거절·해제 / 동시 2단계 4개 중 1개만), `test_harness_control_release_sandbox.py` 2(사칭).
- 변이(일부러 결함, `scratchpad/b6rel/mutate.py`, 실행 뒤 원복 확인): M1 코드 대조 생략, M2 confirm 검사 제거, M3 다른 대상 코드 허용, M4 문구(1단계)만으로 해제, M5 성공 뒤 코드 안 지움, M6 거절 장부 생략, M7 sandbox 프로필 `(deny file-write*)` 제거, M8 control.py가 `clear_by_user` 참조(허용 목록 완화), M9 한도 해제 때 횟수 0으로 → **9개 모두 시험이 잡음**.
- 관련 모듈(개발 중): unlock·control_*·status_*·gold_* 시험 통과(3.12 venv, 3.9 /usr/bin/python3 일부).
- 전체 시험 1회: 아래 "전체 시험" 절.

## 사칭 시험 결과

1. **sandbox executor**(실제 `sandbox.run_one` = 운영 프로필 그대로의 `sandbox-exec` 하위 프로세스). 사람이 받은 **맞는 코드가 샜다고 가정**하고 executor에 넘겼다. 해제 CLI 1·2단계, 훅 진입점 모의 입력 `재개 USER_STOPPED <코드>`, `answer()`·`request()` 직접 호출 → 모두 실패(종료 코드 1, 훅은 "해제 안 함"). `opstate.clear_by_user` 직접 호출·상태 파일 교체·삭제·확인 코드 기록 위조·삭제 → 모두 `PermissionError`. 하네스 root 전체 바이트·mtime 불변(코드도 소모되지 않음), 그 뒤 사람은 같은 코드로 정상 해제.
2. **A묶음 Claude 산출물 경로**(작업 폴더 `out/`, A묶음 허용 쓰기 자리): 가짜 `opstate.json`·`supervisor/opstate.json`·알려진 코드의 확인 코드 기록·재개 문구 파일을 썼다 → 그 코드로 훅·CLI 2단계 모두 "발급된 확인 코드가 없다", `supervisor.run` 1회차 USER_STOPPED·Python 실행 0. 해제 절차는 `root/supervisor`만 읽는다. (실제 claude A묶음 실행이 아니라 그 쓰기 결과를 흉내 낸 것이다.)

## 연결(C) 증거

합성 root(`scratchpad/b6rel/c-root.*`, 로그 `scratchpad/b6rel/c-evidence.log`), 실제 진입점만 사용:
`control stop` → `python -m harness.supervisor --max-cycles 1` `{"python_runs": 0, "state": "USER_STOPPED"}` → 훅 모의 입력 `재개 USER_STOPPED`(exit=2, 코드는 stderr) → supervisor 1회차 다시 `python_runs 0, USER_STOPPED`(문구만으론 안 풀림) → 틀린 코드(exit 0, "코드 불일치") → 맞는 코드("해제 확인: USER_STOPPED. 현재 상태 RUNNING.") → supervisor 1회차 `{"python_runs": 2, "state": "RUNNING"}`, 작업 VERIFIED.
장부 줄: `1 opstate_transition set USER_STOPPED control_cli` · `2 release_challenge issued` · `3 release_challenge rejected 코드 불일치` · `4 opstate_transition clear USER_STOPPED actor=user reason="UserPromptSubmit 훅: 재개 [경로=hook, 확인 코드 일치. 확인 코드는 사용자 인증이 아니..."` · `5 claimed` · `6 completed` · `7 python_drain`, `ledger.verify` 문제 0.
실환경·활성화는 주장하지 않는다(훅 미설치, 가짜 executor).

## 한계 (정직하게)

- **확인 코드는 사용자 인증이 아니다.** 같은 macOS 사용자로 sandbox 밖에서 도는 프로세스(대화형 Claude·Codex·셸)는 1단계를 직접 실행해 stderr의 코드를 보거나, `opstate.clear_by_user`를 직접 부르거나, `opstate.json`을 고쳐 풀 수 있다. 시험 자체가 그 예다(시험 프로세스가 두 단계를 다 해서 푼다). 결정 2의 "에이전트의 모의 입력·직접 함수 호출·상태 파일 수정으로 해제할 수 없는지"는 **sandbox executor와 A묶음 쓰기 자리에 대해서만 "불가"로 확인**했고, sandbox 밖 같은 사용자 에이전트에 대해서는 **"가능"이 확인된 한계**다(OS 사용자 분리 D-7 보류와 같은 원인, 새 인증 서비스 금지라 코드로는 못 막음).
- 2단계 코드가 실제로 막는 것: 지난 문구·코드 재생, 대화 중 오입력, 다른 대상의 코드, 세션 모델이 프롬프트 경로로 해제하는 것(모델은 UserPromptSubmit을 만들 수 없고, 종료 코드 2라 요청·코드를 보지 못함 — 설치본 문자열 기준, 실행 미확인).
- 6자리 코드의 sha256+salt는 파일을 읽을 수 있는 같은 사용자에게는 금방 역산된다(위 한계 안의 일이라 강화하지 않음).
- 훅 종료 코드 2의 stderr가 폰 원격 화면에 보이는지 **미검증**. 안 보이면 폰에서는 못 풀고 중단이 유지된다(안전 방향). 그때는 Mac 터미널 2단계로 푼다.
- `holder:` 해제 성공 경로는 새 시험이 없다(`unlock.release_holder` 자체는 기존 시험 `test_release_holder_alive_without_lock`, 여기서는 같은 분기 코드).
- 손상된 opstate는 이 절차로 못 푼다(기존 규칙). 수동 복구 절차 문서는 없다.

## 미검증

실제 훅 설치·폰 화면 표시·데스크톱/원격 제어 경로, 실제 claude A묶음 실행에서의 쓰기 범위(--restricted·Edit(./out/**) 문서 기준), 사용량 한도 중 훅 실행 여부.

## 사용자 확인 필요

1. 위 한계(sandbox 밖 같은 사용자 에이전트는 해제 가능)를 받아들일지, 아니면 실제 훅 설치 승인 전에 대화형 에이전트의 하네스 root 쓰기를 막는 실행 환경(예: root를 에이전트 쓰기 허용 경로 밖에 두기)을 정할지.
2. 훅 1단계를 종료 코드 2(프롬프트 지움)로 둔 것: 기존 훅의 "항상 0" 원칙의 예외다. 재개 요청 원문이 대화 기록에서 사라지는 대신 장부(`release_challenge issued`)에 남는다.
3. 메인 기본값으로 정한 결정 1·3~7(위 표)을 그대로 둘지.

## 보류 (운영 뒤 개선)

- 상태 파일 직접 수정(장부에 해제 기록이 없는 USER_STOPPED 소실)을 Supervisor가 감지해 INTEGRITY_HALT로 보는 대조: 장부 해시 체인은 서명이 아니라 같은 사용자가 다시 만들 수 있어 효과가 제한적이고 opstate·supervisor 공통 파일을 고쳐야 해 보류.
- status 요약에 발급 중인 확인 코드(대상·만료) 표시.
- `holder:` 해제의 진입점 단위 시험.

## 전체 시험

대상 `b65fae6`, 저장소 루트에서 `PYTHONDONTWRITEBYTECODE=1 <python> -m unittest discover -s tests -p "test_harness_*.py"`, 잠금 `scratchpad/full-suite.lock` 획득 뒤 실행·해제.

- 3.12(`.venv/bin/python`): Ran 539 tests in 309.4s, OK (기준 1b52418의 530 + 새 9).
- 3.9(`/usr/bin/python3`): Ran 539 tests in 352.2s, OK.
- 간헐 실패로 알려진 `test_kill9_while_waiting_then_restart_resumes`는 이번 1회에서 실패하지 않았다(고치지 않음).

## 롤백

`git revert <이 문서 커밋> b65fae6` (새 파일 삭제, 훅 진입점·허용 목록·안내 문구 원복). 운영 상태에 남는 것은 합성 root뿐이고, 실 root에는 실행하지 않았다. 해제 뒤 남는 `supervisor/release_challenge.json`·`release.lock`은 지워도 된다(코드 무효화).

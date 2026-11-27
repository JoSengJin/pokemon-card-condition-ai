# 하네스 8단계 — Gold 수집·중단 훅 (2026-11-27)

```text
task_id: harness-stage8-gold-hook-20261127
owner: Claude (메인 세션이 배정, 구현은 하위 에이전트)
status: ready_for_review
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

### 결과

배정 명세의 코드와 사전 검증을 마쳤다. **8단계 완료가 아니다.** 훅 설치, 휴대폰 시험 제출, 설치 상태의 동작은 하지 않았다.
시험은 모두 합성 입력이며 모델 성능 근거가 아니다. 실제 라벨 파일은 읽거나 쓰지 않았다.
**실제 운영 전에 막아야 할 결함이 있다(아래 리스크 1: 중단이 사라질 수 있음).** 이 작업의 수정 범위 밖이라 고치지 않았다.

### 커밋

| 종류 | 전체 SHA | 내용 |
|---|---|---|
| docs | `f3cc2fd4812b5268909b9e879ce1f3070f79f12b` | 작업 계약 |
| feat | `3ec6e9e460433486f2bf9d625460599d02fa34c8` | harness/{gold_issue,gold_parse,gold_store,gold_hook}.py, harness/hooks/{user_prompt_submit.py,settings-snippet.json.template} |
| **test(최종 시험 대상)** | `63e8958e893b417b342ed9b25aaf5a45b8c7a3f7` | tests/test_harness_gold_{support,flow,rejects,guard,stop,crash}.py (24개) |
| docs | 이 문서 커밋(그 위, 문서만) | 인계 |

계약 밖의 추가 harness 파일은 없다.

### 훅 규약: 확인한 것과 확인하지 못한 것

근거는 설치본 Claude Code 2.1.310 실행 파일에서 `strings`·`grep`으로 읽은 내장 문자열이다. `claude`는 `--help`만 실행했고
`--help`에는 훅 입출력 규약이 없었다. **정적 확인이며 실행 검증이 아니다.** 데스크톱 앱이 같은 판을 쓰는지도 확인하지 않았다.

| 항목 | 읽은 내용(요지) |
|---|---|
| 입력 | 훅 입력 생성 코드에 `hook_event_name:"UserPromptSubmit",prompt:…`, 공통 칸에 `session_id`·`transcript_path`·`cwd` |
| 종료 코드 | 0 = 표준출력이 Claude에게 전달됨. 2 = 처리를 막고 원래 프롬프트를 지우며 stderr는 사용자에게만. 그 밖 = stderr만 사용자에게 |
| JSON 출력 | `decision:"block"`·`reason`, `hookSpecificOutput.additionalContext`, `systemMessage` 설명이 있음(사용하지 않음) |
| 실패 처리 | `onFailure` 설명: 시작 실패·시간 초과·0/2 아닌 종료는 기본 `continue`(입력은 그대로 진행), `block`이면 종료 코드 2처럼 처리 |

구현은 항상 **종료 코드 0 + 짧은 표준출력**이다. 거절·중단에도 프롬프트를 막지 않는다. 2는 원래 프롬프트를 지우므로
DESIGN 5-2의 감지 수단(Claude 대화 기록 원본 대조)이 없어질 수 있기 때문이다(지운 입력이 기록에 남는지는 미확인).
템플릿에는 `onFailure`를 넣지 않았다. `block`이면 훅이 깨졌을 때 모든 입력이 막혀 사용자가 갇힐 수 있다. 설치할 때 정할 항목이다.

### 형식과 공개 API (이후 단계 호출자용)

```text
# 화면=<16자 hex>
# nonce=<32자 hex>
# 직접판정=확인
# 제출시각=2026-12-01T10:00:00+09:00
z1=정상|결함|불가|미확인
```

- `gold_issue.issue(root, zones, criteria_version, judge, now, planned_repeat=False)`: zones는 `image_sha256`·`region`·`crop_sha256`
  세 칸만. 반환값에만 nonce 원문이 있고 발급 장부에는 sha256만 둔다. `confirm.preset=False`(화면은 확인 칸을 꺼 둬야 한다).
- `gold_store.save(root, payload, now)`: 훅 진입점 프로세스에서만 성공. `gold_store.audit(root, issued_tail=None, store_tail=None)`:
  **Gold를 읽는 쪽(9단계)은 먼저 audit를 부르고 문제가 있으면 쓰지 않는다.** 현재 이 함수를 부르는 운영 코드는 없다.
- 장부: `root/gold/issued.jsonl`, `root/gold/store.jsonl`. root는 Supervisor root와 같아야 "중단"이 읽힌다.
- 설치 템플릿 자리표시: `__PYTHON__`, `__REPO__`, `__HARNESS_ROOT__`(절대경로). 설치하지 않았다.

### 위조에 대한 한계

진입점 표식(`__main__` 파일 대조)은 직접 import해 `save`·`handle`을 부르는 경로만 막는다. **같은 사용자 권한의 에이전트가
진입점에 모의 JSON을 파이프로 넣으면 저장되고, `audit()`은 구별하지 못한다**(시험
`test_piped_forgery_is_not_prevented_but_leaves_transcript_evidence`가 이 한계를 고정한다). `__main__.__file__` 변경(시험 드라이버의
`runpy`가 같은 효과), 장부 직접 편집·전체 재작성도 가능하다.

| 위조 | 결과 |
|---|---|
| `save`/`handle` 직접 호출(프로세스 안, `-c`, stdin 스크립트, 같은 이름의 다른 파일) | 거절 `no_hook_mark` |
| 장부에 직접 추가: 발급 없음, 답·원문 불일치, 재판정 표시 추가, 출처 변경, 칸 추가, 재사용, 형식 아닌 기록 | 저장은 막지 못함, `audit()`이 감지 |
| 줄 편집 | 해시 체인으로 감지, 이후 저장 거절 |
| 꼬리 삭제·전체 재작성 | 밖에 복제한 마지막 해시가 있어야 감지(복제는 구현하지 않음) |
| 진입점에 파이프로 넣은 규칙에 맞는 위조 | **감지 못 함.** 기록의 `session_id`·`transcript_path`·원문 해시로 대화 기록과 대조해야 함(대조 도구 미구현, 대화 기록 형식 미확인) |

`source=human`은 `# 직접판정=확인` 줄의 자기 신고다. AI가 만든 답을 사람이 붙여넣는 사고(2026-11-20~21 사례)를 이 코드가 판별하지는 못한다.

### 실행한 검사 (cwd=worktree, 대상 63e8958)

| 명령 | 종료 코드 |
|---|---|
| 시작 전 기준선 805d9c7, 계약의 시험 명령, 3.12 / 3.9 | rc=0 / rc=0, 각 250개 |
| 계약의 시험 명령, `.venv/bin/python`(3.12.14) | rc=0, 274개(250 + 24) |
| 계약의 시험 명령, `/usr/bin/python3`(3.9.6) | rc=0, 274개 |
| 신규 24개 `-W error::ResourceWarning` 5회 반복, 두 버전(10회) | 모두 rc=0, ResourceWarning 출력 0건 |
| 변이 35개(임시 복사본, 원본 무수정, 3.12) | 35/35 시험 실패로 감지, 종료 코드 0 |
| `git diff --check 805d9c7 HEAD` | 0 |
| `git diff --name-only 805d9c7 HEAD` | 허용 파일 13개(이 문서 포함) |

변이 시험은 커밋 직전 작업본에서 실행했다. 그 뒤의 코드 파일 변경은 `gold_hook.py` 설명 문자열의 `shortcut:` 문단 추가뿐이다.
변이 목록: nonce 재사용 허용, 발급 선기록 제거, 발급 기록 실패 무시, fail-closed 제거, 표식을 파일 이름만 대조, 완료 키 거절 제거,
미확인을 완료로 셈, 계획된 재판정 거절, 완료 키 검사 항상 생략, 원문 대신 정규화본 저장, 원문 평문 저장, nonce 해시 미대조,
구역 집합 대조 제거, 직접 판정 확인 제거, 확인 값 아무거나, 중복 zN·머리 줄 허용, 모르는 값 허용, 중단 부분 문자열, 확인 없이 중단 성공 주장,
예측 칸 허용, 발급 장부에 nonce 원문, 저장 잠금 제거, 체인 검증 제거, audit의 원문·nonce·완료 키·외부 꼬리 검사 제거, 이벤트 이름 미확인,
출처 변경, 대화 기록 칸 미기록·미거름, 머리 줄 없는 답 무시, 크기 제한 제거, secrets 미사용.
변이 스크립트는 세션 임시 폴더에 있었고 커밋하지 않았다.

### 필수 시험 대응

| 요구 | 시험 |
|---|---|
| 정상 저장·원문 해시 일치 | flow `test_save_keeps_original_bytes_and_hash`(CRLF·줄 끝 공백·U+2028·U+0085 바이트 그대로) |
| 발급 안 된·재사용 nonce 거절 | flow `test_unissued_and_reused_nonce_rejected`(재사용은 전부 미확인 화면으로 시험해 완료 키 거절과 분리) |
| 형식 오류·중복 키·확인 누락 거절 | rejects 2개(거절은 nonce를 소비하지 않음) |
| "중단" → `opstate`가 USER_STOPPED, 실제 `supervisor.run`이 시작 안 함 | stop `test_stop_sets_user_stopped_and_supervisor_starts_nothing`(중단 없는 대조 root는 실행함). **동시 갱신은 리스크 1** |
| 훅 표식 없는 직접 저장 거절 | guard `test_direct_write_without_hook_mark_refused` |
| 완료 키 재저장 거절 | flow `test_completed_key_rejected_planned_repeat_marked` |
| 저장 중 kill -9 | crash: 정한 6지점(잠금 전, 발급·저장 장부 읽기 전, 추가 직전, flush 뒤 fsync 전, 추가 뒤 응답 전), 임의 시각 24회(어느 지점이 맞았는지는 기록 안 함), 잘린 마지막 줄(합성) |
| 동시 호출 | crash: 같은 nonce 5개·같은 키 5화면은 1건만(판단과 추가 사이에 0.5초 지연 주입), 서로 다른 6화면 + 중단은 모두 반영 |
| 위조·손상 | guard 5개 + 위 한계 표 |

### 구조 (ast 재측정, harness 모듈 경계를 넘어 합산)

모두 신규 파일이라 변경 전 함수 수는 0이다. lambda 0개.

| 파일 | 함수 수 | 공개 함수 깊이(최대 경로) |
|---|---|---|
| gold_hook.py | 2 | handle 4 (handle → _stop → opstate.set_condition → opstate.load → jsonio.read_json; handle → gold_store.save → rows → ledger.verify → _check_line/_load) |
| gold_store.py | 5 | save 3, audit 3, rows 2, completed 0 |
| gold_parse.py | 2 | parse 0, classify 0 (`GoldError`는 메서드 없음) |
| gold_issue.py | 1 | issue 1 |
| hooks/user_prompt_submit.py | 0 | 모듈 수준 코드가 handle만 부른다. 함수가 아니라 시작점에서 제외(3단계 `__main__` 블록과 같은 기준). 이 층도 센다면 5가 되므로 검토 대상 |

동적 호출 대상은 없다. 시험 파일의 함수 수/테스트 수: support 6/0, flow 6/5, rejects 6/5, guard 6/5, stop 5/4, crash 6/5.

### 가정 (설계에 값이 없어 정한 것, 검토 대상)

1. `# nonce=`, `# 직접판정=확인` 줄 이름은 새로 정했다. `# 제출시각=`은 기존 형식대로 필수다.
2. 값은 `tools/self_agreement/answers.VALUES`와 같은 정상·결함·불가·미확인(시험이 대조). 옛 `미세/뚜렷`·`|확신` 화면 형식은 거절한다.
3. 배정 문구의 "구획 위치 기호"는 추적 파일과 프로젝트 메모에서 정의를 찾지 못했다. 위에 적은 줄 외에는 모두 거절한다. 별도 형식이 있다면 확인이 필요하다.
4. `미확인`은 완료가 아니고 `불가`는 완료다. 완료 키가 하나라도 있으면(새 값과 무관) 화면 전체를 저장하지 않는다(부분 저장 없음).
5. 계획된 재판정은 발급 때만 지정한다. 붙여넣기로는 바꿀 수 없다.
6. 중단은 앞뒤 공백을 뺀 전체가 `중단`일 때만이다. `중단.`·`중단해`는 아무 출력 없이 지나간다.
7. 붙여넣기 앞뒤에 설명 글이 있으면 거절한다. 크기 상한 64KiB.
8. `criteria_version`은 결함 종류별 기준을 구분하는 값(권장: 기준 문구 SHA)이어야 한다. judge 이름은 정규화하지 않는다.
9. 원문은 장부 줄 안에 base64로 둔다(리스크 2).

### 미검증

- 설치 보류(D-7)로 하지 않음: 실제 Claude Code에 훅을 설치한 상태의 동작, 데스크톱·원격 제어 경로, **사용량 한도 상태에서 훅이 실행되는지**, 휴대폰 시험 제출.
- 원격 제어·데스크톱이 사용자 원문에 앞뒤 글을 붙이는지(붙이면 Gold는 거절되고 "중단"은 인식하지 못한다).
- 표준출력이 사용자 화면에 보이는지, 모델이 거절 사유를 사용자에게 전달하는지.
- 사람이 아닌 입력(`claude -p` 프롬프트, 세션 간 메시지, 예약 작업·작업 알림)에도 `UserPromptSubmit`이 실행되는지, 입력으로 구분할 수 있는지.
- HTML 화면이 없어 "누른 것 = 가져온 것" 시험(`label-screen-round-trip`)은 **못 했다**. 화면 생성기를 만들 때 필수다.
- 전원 차단·OS 충돌 내구성(kill -9와 합성 잘린 줄만 시험). 새 파일의 폴더 fsync는 1단계 장부에 없다.
- 보호 사용자·권한 분리(9단계·설치). 독립 Opus 검증은 메인이 따로 한다.

### 리스크

1. **[높음, 3단계 `opstate`] 중단 유실.** `set_condition`·`_clear`는 잠금 없이 읽고 고쳐 쓴다. 재현(임시 root, 수정 없음):
   RATE_LIMITED_SHORT를 켠 뒤 `clear_auto`의 `write_json` 직전에 "중단" 훅 프로세스를 끼워 넣으면 훅은 "중단 접수: USER_STOPPED를 기록했다"고
   답하고 최종 유효 상태는 `RUNNING`이었다. 같은 이유로 동시에 기록한 다른 정지 상태도 잃을 수 있다. 실제 창은 짧지만 중단은 안전 경로다.
   권장: opstate의 읽기→쓰기를 flock 하나로 감싸고 이 재현을 회귀 시험으로 둔다.
2. **[중간, 1단계 `ledger`] 장부 영구 손상.** 데이터 문자열에 U+2028·U+2029·U+0085가 있으면 `read().splitlines()`가 줄을 나눠
   `verify`가 `unparseable`이 되고 다음 `append`가 거절된다(`ledger.append` 직접 호출로 3개 문자 모두 재현). Gold는 base64·입력 검사로 피했다.
   다른 모듈이 장부에 넣는 자유 문자열(예외 메시지·stderr 등)은 전수 확인하지 않았다. 권장: `split("\n")`으로 읽기.
3. **[결정 필요] Gold 원문이 모델과 대화 기록에도 남는다.** 설계의 "채팅에 붙여넣기" 경로의 성질이다. 봉인 Gold 답을 에이전트가 읽을 수 있게
   되며 DESIGN 7절의 추론 격리는 이 경로를 막지 않는다. 봉인 라벨을 받기 전에 확인해야 한다.
4. 훅이 실패하거나 시간 초과면 저장은 안 되지만(안전) **중단도 기록되지 않고** 입력은 모델에게 간다(`onFailure` 기본값, 정적 확인).
5. 발급 때는 완료 키를 거절하지 않는다(명세는 저장 때 거절). 사용자가 판정한 뒤에야 거절될 수 있으므로 화면 생성기는 발급 전에 `completed`로 확인해야 한다.
6. 이 저장소 이전의 기존 라벨 파일에 있는 완료 판정은 저장소가 모른다. 재요청 방지에는 별도 대조가 필요하다.
7. 장부가 손상되거나 마지막 줄이 잘리면 모든 저장이 거절된다. 복구 함수는 없다(사람이 확인). 체인은 맞지만 형식이 틀린 기록이 끼면 저장은 "결과를 확인하지 못함"으로 실패한다.
8. Gold 붙여넣기와 "중단"을 한 메시지에 보내면 형식 오류로 거절되고 중단은 기록되지 않는다.

### 적용 규칙·스킬·보고

- 품질 규칙: `label-provenance`(판정마다 `criteria_version`·`crop_sha256` 저장. 화면 해시는 화면 생성이 범위 밖이라 없음),
  `label-screen-round-trip`(**못 지킴**: 화면 없음. 기존 `answers.parse`와의 답 줄 대조만 함), `short-request-reading`.
- 스킬: Superpowers 해당 없음(TDD 순서·RED/GREEN 기록 안 함). 검증은 위 명령·종료 코드·대상 SHA로 대신한다.
- 성과·진척 HTML: 만들지 않았다. 허용 파일 밖이고 모델 성능 평가가 없다. 전체 진척률은 산정하지 않았다(정본 두 파일 미확인).

### 롤백

설치한 것, 실제 root에 쓴 상태, 설정 변경이 없다. `805d9c7..HEAD`의 커밋을 역순으로 `git revert`하면 된다. 기존 파일은 수정하지 않았다.

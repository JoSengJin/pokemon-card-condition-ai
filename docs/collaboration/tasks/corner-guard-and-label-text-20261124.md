# 병렬 개발 계약 2개: 우연 판별 도구 · 새 라벨 화면 안내문 (2026-11-24)

사용자 지시(채팅): 1번은 Opus 5.5, 2번은 Sonnet 5.5가 병렬 개발. **개발과 합성 검증까지만.** 통합·push·학습·추론·새 점수 생성·외부 호출·라벨 변경은 포함하지 않는다. 봉인 468장·독립 350장 자료는 열지 않는다. 판정 일관성 확인용 `artifacts/cohort2-retest-20261125/`(A2·B2 화면)은 열거나 바꾸지 않는다.

- 공통: base_sha는 이 문서를 처음 추가한 커밋(`git log --diff-filter=A --format=%H -- <이 문서>`). 작업마다 별도 branch·worktree(경로 미커밋). 허용 파일만 변경. 기본 checkout에는 쓰지 않는다(다른 세션의 미커밋 변경이 있다). 파일당 함수 ≤7, 저장소 함수 호출 깊이 ≤4. 편집은 worktree의 `./develop -- <수정 명령>` 안에서.
- worktree 실행 환경: `python3 -m venv .venv`(패키지 설치 없음)로 `./develop`을 쓰고, PIL·torch가 필요한 테스트는 기본 checkout의 `.venv/bin/python`을 실행에만 쓴다(설치·쓰기 금지). 테스트가 worktree 파일을 읽는지 출력으로 확인한다.
- 공통 checks: 새 테스트 `-W error` 종료 0, `git diff --check`, `git diff --name-only <base_sha> HEAD`가 허용 파일과 일치, 함수 수.
- handoff: 자기 branch 커밋 SHA 전체, 변경 파일, 검사 명령·종료 코드, 구조, 미검증, 위험, 롤백. **이 문서는 고치지 않는다**(채팅으로 보고하고 통합 담당이 기록).
- HTML 보고: 모델 결과가 없는 합성 검증이므로 만들지 않고 채팅 보고에 그 이유를 적는다.

## 작업 1 corner-chance-check-20261124 (owner: Claude Opus 5.5, status: assigned)
- branch: `claude/corner-chance-check-20261124`. 허용 파일: `tools/diagnostics/corner-chance-check-20261124/check.py`, `tests/test_corner_chance_check.py`.
- 목적: 같은 개발 자료에서 두 모델의 카드별 결과 차이가 우연 범위인지, 같은 평가 자료로 몇 번째 시도인지 보여준다. 표준 라이브러리만, 읽기 전용, 결과는 표준 출력 JSON.
- 입력: 대조 `result.json`과 후보 `result.json` 경로(명령 인자), 공통 실행 기록 폴더. `rows`·`scores`를 쓴다. 두 파일의 rows 또는 순서가 다르면 종료 코드 2.
- 카드 규칙(기존 정의와 같아야 함): 결함 카드 = 결함 구역이 하나라도 있는 group, 점수 = 결함 구역 최대, 0.20 미만이면 놓침. 정상 카드 = 결함 구역이 없는 group, 점수 = 전체 최대, 0.60 이상이면 잘못 표시. 동일 정의는 `tools/experiments/corner-mlp-head-20261121/worker.py`의 `card_miss`.
- 출력: (1) 대조·후보의 놓침/결함 카드, 잘못 표시/정상 카드와 Wilson95; (2) 짝지은 변화 장수(나빠짐 b, 좋아짐 c)와 양측 McNemar 정확 p `min(1, 2·P[Bin(b+c,0.5) ≤ min(b,c)])`(b+c=0이면 1); (3) 같은 사진 AUC 차이의 그룹 단위 짝지은 부트스트랩 95% 구간(2000회, 시드 20261124); (4) 시도 장부: `artifacts/experiments/*/{record.json,reference.json}`에서 후보 실행의 `cohort_sha256`과 같은 기록의 전체·상태별 수와 hypothesis_id 목록.
- 통과/실패를 판정하지 않는다. 기존 사전 기준·과거 판정을 대체하지 않고 "기술 통계, 채택 기준 아님"과 "`cohort_sha256`이 다른 옛 실행(946구역 등)은 세지 않아 실제 시도 수의 하한"을 출력에 넣는다. 반복 시도를 p에 보정했다고 쓰지 않는다.
- 테스트(합성): 카드 규칙(결함 카드의 정상 구역은 놓침·잘못 표시에 영향 없음), McNemar 손계산 값, Wilson 알려진 값, 같은 결과면 p=1, rows 순서 불일치 거절, 장부 집계(다른 cohort 제외, failed도 셈), 부트스트랩 시드 재현.
- 개발 중 실자료 실행 1회 허용(읽기 전용): 대조 `artifacts/experiments/20261121T050740-8588eeb0/result.json`, 후보 `20261124T010332-678d2e0d/result.json`. 점수 카드 수가 결과 문서 `docs/collaboration/reports/corner-phase-train-20261124.md`(5→7/175, 9→9/81)와 다르면 고치지 말고 보고한다.

## 작업 2 corner-label-text-20261124 (owner: Claude Sonnet 5.5, status: assigned)
- branch: `claude/corner-label-text-20261124`. 허용 파일: `tools/mobile_corner_label_pages.py`, `tests/test_mobile_corner_label_pages.py`(새 파일).
- 목적: 2026-11-24에 사용자가 승인한 모서리 결함 기준(`LABELING_PROTOCOL.md`의 "후면 모서리 결함 수준")을 앞으로 생성하는 화면 안내문에 넣는다.
- 바꿀 것은 `main()`의 안내 `<p>` 문자열뿐: "확대해서 보이면 크기와 관계없이 결함", "mm 크기 문턱은 두지 않음", "확대해도 반사인지 마모인지 구분 안 되면 추정하지 말고 이 화면에서는 미확인". 엣지·표면 제외와 기존 문장은 유지한다. 화면 동작·저장 형식·STYLE·SCRIPT·다른 함수·선택지(미확인·정상·결함)는 바꾸지 않는다.
- 시작 전 확인: 파일 SHA256 `6b1c143b71d867f68c7a8668adabf25b81d4537682472c6386c937323a78aafe`(추적 파일에 이 값을 고정한 곳 없음, 2026-11-24 확인). `artifacts/corner-rank-independent-v1-20261121/build-review.py`가 이 도구를 언급한다: 어떻게 쓰는지(가져오기·해시 검사 여부)만 읽기 전용으로 확인해 보고하고, 해시를 고정하고 있으면 멈추고 보고한다. 이 폴더의 다른 파일은 열지 않는다.
- 테스트(합성 이미지, 임시 폴더): 생성 HTML에 새 문구 3개와 기존 제외 문구가 있음; `SCRIPT`·`STYLE`·`AREAS` 해시가 변경 전 값과 같음(테스트에 고정); 결과 행 형식 문자열과 초기 상태(미확인)가 그대로; 이미 있는 HTML을 다시 쓰지 않음(새 경로만).
- 이미 만든 화면·기존 라벨·`LABELING_PROTOCOL.md`·`label_instructions.py`는 고치지 않는다. 프로토콜의 "문구가 아직 없다" 문장 갱신은 통합 담당이 한다.

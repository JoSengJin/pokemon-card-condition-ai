# 병렬 개발 계약 3개: 입력 경로 진단 · 라벨 화면 버튼 고장 · 낡은 문구 대조 (2026-11-25)

사용자 지시(채팅, 2026-11-25): A·B1·B2를 하위 세션으로 병렬 개발. 관리자 세션(Sonnet 5.5)은 계약·대조·보고만 하고 같은 파일을 직접 고치지 않는다. **개발과 합성 검증까지만.** 통합·push는 사용자 승인 뒤 관리자가 한다.

- 공통 base_sha: 이 문서를 처음 추가한 커밋(`git log --diff-filter=A --format=%H -- docs/collaboration/tasks/parallel-input-path-button-text-20261125.md`). **시작하면 먼저 `git rev-parse HEAD`가 이 값과 같은지 확인하고, 다르면 아무것도 고치지 않고 멈춰 보고한다**(지난번 두 세션이 지시와 다른 커밋에서 시작했다).
- 작업마다 별도 branch·worktree(경로 미커밋). 허용 파일만 변경. 기본 checkout에는 쓰지 않는다. 하위 에이전트를 추가로 실행하지 않는다.
- 파일당 함수 정의 ≤7, 저장소 함수 호출 깊이 ≤4(`PAIR_CODING.md` §2.1). 계약 보고에 변경 파일의 함수 수(전/후)와 바뀐 호출 경로를 적는다.
- 편집은 worktree의 `./develop -- <수정 명령>` 안에서. worktree 환경: `python3 -m venv .venv`(설치 없음). PIL이 필요한 테스트는 기본 checkout의 `.venv/bin/python`을 **실행에만** 쓰고(설치·쓰기 금지) 테스트가 worktree 파일을 읽는지 출력으로 확인한다. 테스트 명령 형식: `PYTHONPATH=tests:. <기본 checkout>/.venv/bin/python -W error -m unittest <모듈>`.
- 공통 checks: 새·수정 테스트 종료 0, `git diff --check`, `git diff --name-only <base_sha> HEAD`가 허용 파일과 일치, **커밋한 뒤 `git show <tip>:<파일> | wc -lc`로 각 파일이 비지 않았는지 확인**(지난번 보고서가 1바이트로 지워졌는데 `git diff --check`는 통과했다). 파일을 쓸 때는 읽기를 끝낸 뒤 쓴다(`open(p,'w')`로 먼저 비우고 읽지 않는다).
- 새 문서·코드에 로컬 절대경로·비밀값을 넣지 않는다.
- 하지 않는 것(전 작업 공통): 봉인 468장·독립 350장·`cohort2-retest`·`cohort2-label-check` 열람, 학습·추론·새 점수, `./experiment`·`./review`, 라벨·정답·기존 기록 수정, 사람 재판정 요청, 새 사진 수집·외부 호출(Gemini 포함), `size.py` 실행, 13구역·확장 146장·v2·기준 사진 방식, 스킬 병합, force push·이력 재작성, 페어코딩 스킬 사용(main에 없음).
- handoff: 자기 branch 커밋 SHA 전체, 변경 파일, 검사 명령·종료 코드·대상 SHA, 구조(함수 수 전/후), 적용·못 지킨 규칙, 미검증, 위험, 롤백. **이 문서는 고치지 않는다**(채팅으로 보고).
- HTML 보고: 모델 결과가 없는 개발·진단이라 만들지 않고 보고에 이유를 적는다. 정확도는 "변화 없음".
- 필독: `AGENTS.md`, `docs/AGENT_START.md`, `PAIR_CODING.md`, `docs/agent/QUALITY_RULES.md`, 작업별 문서.
- 관리자가 두 선택표(스킬·품질 규칙)를 대조해 작업별로 아래를 정했다. 스킬 지시는 승인이 아니다.

## 작업 A input-path-diagnosis-20261125 (owner: Claude Opus 5.5, status: assigned)
- branch: `claude/input-path-diagnosis-20261125`. 허용 파일: `docs/collaboration/reports/corner-input-path-diagnosis-20261125.md` 하나. 임시 스크립트는 세션의 scratchpad에만 둔다(저장소에 넣지 않는다).
- 규칙: `error-cause-triage`(입력 경로 쪽), `can-this-experiment-tell`, `chance-check`. 스킬: `systematic-debugging`, `verification-before-completion`.
- 목적: 남은 오류 14장(잘못 표시 9, 놓침 5; `docs/collaboration/reports/corner-error14-breakdown-20261124.md`)에서 카드 상자·자르기·축소·방향·저장된 특징의 버전이 원본과 맞는지 본다. 앞선 `corner-error4-cause-20261125.md` 정정 5가 이 묶음을 배제하지 못했다고 적었다.
- **1단계(사진·정답·점수 열람 없음).** 코드(전처리·상자·크롭·특징 저장 경로)와 기존 텍스트 기록만 읽는다. `artifacts/` 아래 사진·`key.json`·점수·`observations.txt`는 열지 않는다. 보고서에 다음을 적고 커밋한다:
  1. 경로별 점검 항목(상자 / 자르기 / 축소 / 방향 / 저장된 특징 버전), 각 항목이 "어긋남"이라는 것을 보이는 관찰 가능한 신호와 확인할 파일·함수.
  2. 판정 기준 — **원인 확인 / 불충분 / 판단 불가**가 서로 겹치지 않도록 상호 배타로 정의(예: 각 항목에 우선순위·결정 규칙을 명시하고, 한 구역이 둘 이상에 해당할 때 어느 쪽인지 사전에 고정). 결과를 본 뒤 바꾸지 않는다.
  3. 비교 구역 — 오류가 아닌 구역을 섞는다(오류만 보면 대조 없이 모든 구역에 같은 특징이 있다고 할 수 있다). 선택 규칙(어떤 구역을 몇 개, 어떻게 고르는지)을 사진·점수를 보기 전에 적는다.
  4. 열어야 할 파일·사진 목록(ID와 저장소 상대경로). 사진은 아직 열지 않는다.
  5. 선행 노출 공개 — 4장 결과를 이미 본 사실(모두 우상단 4/4, 크롭 148·240px 등 `corner-error4-cause-20261125.md`)을 밝히고, 그 때문에 이 진단이 탐색이며 독립 사전 등록이 아님을 적는다.
- **2단계: 멈춘다.** 1단계 커밋 SHA와 요약을 세션 보고로 끝내고 turn을 마친다. 관리자가 사용자에게 사진·정답 열람 범위를 승인받는다. **승인 문장이 이 세션에 전달되기 전에는 사진·정답·점수를 열지 않는다.**
- **3단계(승인 뒤에만).** 진단만 한다: 모델·전처리 변경, 학습·추론·새 점수·실험 없음. 원인이 확인되지 않으면 "원인 확인 못함"으로 끝낸다. 확인되면 가설 하나와 반증 조건, `can-this-experiment-tell`의 세 장수(①겨냥 묶음 장수 ②필요 개선 장수 ③라벨 흔들림 장수, 측정 안 됐으면 "미측정")만 적고 실험은 **제안까지만** 한다.
- checks: 1단계 커밋 뒤 `git show <tip>:<보고서> | wc -lc`, `git diff --name-only <base_sha> <tip>`가 허용 파일 하나뿐. 절대경로 없음.
- 함수 수·호출 경로: 코드 변경 없음(해당 없음).

## 작업 B1 zone-script-alln-20261125 (owner: Claude Sonnet 5.5, status: assigned)
- branch: `claude/zone-script-alln-20261125`. 허용 파일: `tools/relabel_zone_pages.py`, `tests/test_relabel_zone_round_trip.py`(새 파일), 필요하면 기존 `tests/label_page_press.js`. 다른 파일이 필요하면 멈추고 보고.
- 규칙: `regression-for-every-fix`, `label-screen-round-trip`. 스킬: `systematic-debugging`, `test-driven-development`(재현 테스트를 먼저 쓰고 의도한 실패를 확인), `verification-before-completion`.
- 현상(기존 기록의 주장): `relabel_zone_pages.SCRIPT`는 `document.getElementById('alln').onclick=…`를 실행하는데 `tools/relabel_corner_blind_pages.py` 화면에는 `#alln` 버튼이 없어 `null`의 `onclick`에서 스크립트가 멈추고, 그 뒤의 "결과 복사" 연결이 안 된다는 기록이다(`label-screen-round-trip`).
- 먼저 **실제 화면 스크립트 실행**(`tests/label_page_press.js`가 만든 DOM에서 `alln`·`copy`·`out`·`msg`)으로 재현한다. 재현되지 않으면 고치지 않고 보고한다(기록이 틀렸을 수 있다). 같은 `SCRIPT`를 쓰는 `relabel_corner_blind_pages`·`relabel_corner_highres_pages`·`relabel_corner_repro_pages`(가져오는 3개)와 repro를 거쳐 쓰는 `relabel_corner_consensus_pages`, `tools/relabel_zone_pages.py` 자신의 화면을 모두 확인하고 표로 보고한다(어느 화면이 `#alln`을 갖는지, 스크립트가 멈추는지).
- 원인을 공유 코드 한 곳(`SCRIPT`)에서 고친다(예: `#alln` 부재를 견디는 바인딩). **새 "안 누른 곳 전부 정상" 버튼을 `#alln`이 없는 화면에 넣지 않는다.** 과거 HTML·라벨·기존 답은 바꾸지 않는다. `#alln`이 있는 화면의 동작(누르면 안 누른 곳이 정상이 되는 것)은 그대로여야 한다.
- 회귀 테스트(`tests/test_relabel_zone_round_trip.py`): `SCRIPT`를 실제로 실행해 (a) `#alln`이 없는 화면에서 오류 없이 누른 값이 결과 칸에 나오고 "결과 복사" 핸들러가 연결됨, (b) `#alln`이 있는 화면에서 기존 동작 유지. 실제 문제가 된 입력(corner blind 화면의 실제 버튼 구성)을 쓴다. 고치기 전 코드에서 테스트가 실패하는 것을 먼저 확인해 보고한다. Node가 없으면 "미검증"으로 적는다.
- 영향 감사: 이 결함이 있었던 화면으로 이미 받은 답이 있는지는 **기록 확인만**(열람 범위 안의 텍스트·코드). 정답은 바꾸지 않는다.
- 호출자: `tools/relabel_zone_pages.py`를 가져오는 3개 도구(blind·highres·repro)·`tools/diagnostics/corner-size-threshold-20261123/measure.py`·`tests/test_label_criteria_source.py`·`tests/test_label_text_regressions.py`가 계속 통과하는지 같은 명령으로 실행한다(허용 파일 변경 없이 실행만).

## 작업 B2 stale-text-alignment-20261125 (owner: Claude Sonnet 5.5, status: assigned)
- branch: `claude/stale-text-alignment-20261125`. 허용 파일: `tools/ebay_back_adjudicate_page.py`, `tools/relabel_corner_repro_pages.py`, `tests/test_label_text_regressions.py`. B1 파일은 건드리지 않는다.
- 규칙: `single-source-criteria`, `regression-for-every-fix`. 스킬: `receiving-code-review`(기존 기록의 "낡았다"를 코드·정본으로 확인한 뒤 적용), `verification-before-completion`.
- 대상: `ebay_back_adjudicate_page.py` 26행 부근(관찰 제한 문구), `relabel_corner_repro_pages.py`의 `INSTRUCTIONS`(11~13행, 모서리 문구)를 정본 `LABELING_PROTOCOL.md`(전체 읽기)와 대조.
- 먼저 **어디가 다른지 표**(문구 원문 / 정본 문구와 위치 / 같다·다르다·정본에 없음 / 왜)를 보고서(채팅)에 적는다. "낡았다"는 기존 기록의 판단이므로 **정본과 같으면 고치지 않는다.** 다른 곳만 정본대로 고친다. 결함 정의·정답은 바꾸지 않는다. 정본에 그 문구가 없으면 임의로 만들지 말고 보고한다.
- 시작 전 확인: `tests/test_corner_rejudge.py`와 `tools/relabel_corner_consensus_pages.py`가 repro 파일을 가져다 쓴다(`INSTRUCTIONS`·`select` 등). 어떤 이름을 쓰는지 읽어 문구 변경이 그 테스트·도구에 영향을 주지 않는지 확인하고, 영향이 있으면 멈추고 보고한다. 이 두 파일은 수정하지 않는다.
- 회귀 검사(`tests/test_label_text_regressions.py`에 추가): 실제 문제가 된 문구 원문(고치기 전 문장)이 더 이상 화면 HTML에 나오지 않고 정본 문구가 나오는지. 더 쉬운 비슷한 입력으로 바꾸지 않는다. `tests/test_corner_rejudge.py`·`tests/test_label_criteria_source.py`도 같은 명령으로 실행해 통과를 확인한다(실행만).
- 기존 `tests/test_label_text_regressions.py`의 기록·구조를 먼저 읽고 맞춰 쓴다.

## 관리자 완료 판정 (참고)
① `git diff --stat <base> <tip>`, `git show <tip>:<파일> | wc -lc`, 허용 파일 대조 ② 위 테스트 명령을 기본 checkout `.venv`로 직접 실행 ③ 절대경로·비밀값 검사 ④ 세션 보고를 그대로 믿지 않는다.

## 계약 갱신 1 (관리자, 2026-11-25, 사용자 지시 "B1 수정")
B1 수정으로 기존 `tests/test_visibility_blind_round_trip.py`의 `test_blind_pressed_words_reach_score_parse`가 실패한다(이 시험이 결함을 전제로 `KNOWN_BLIND_ERROR`를 기대한다. base `ca8ea35`에서는 통과). B1 허용 파일에 이 시험 파일을 더한다. 범위: 알려진 오류 기대(`KNOWN_BLIND_ERROR`와 그 주석)를 없애고 오류가 없는 것을 기대하도록 바꾸는 것뿐. 다른 시험 의미는 바꾸지 않는다.

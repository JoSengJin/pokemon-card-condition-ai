# 휴대폰 표시·H 확대·사람 출처·봉인/접근 분리 구현 계획

> 향후 구현이 승인되면 Superpowers executing-plans로 아래 작업을 순서대로 실행한다. 이 문서는 계획 산출물이며 이번 세션의 코드 구현·시험 실행 지시가 아니다. 새 정책 선택이 필요해지면 해당 부분만 별도 결정하고 이미 정한 범위를 다시 묻지 않는다.

**Goal:** 실제 수집을 열지 않은 상태에서 휴대폰 표시·H 확대 이력·사람 출처 검증·봉인/역할 경계를 합성 자료로 먼저 구현·검증할 수 있는 작업과 실제 환경 의존을 분리한다.
**Architecture:** 기존 synthetic v1의 허용 출처·실행 불가·원문 보존을 회귀 기준으로 유지한다. 기존 v1 응답에 필드를 몰래 덧붙이지 않고 새 계약 버전의 표시/확대/출처/봉인 필드를 명시적으로 설계한다. 먼저 합성 전용 후보 경로를 검증하고, 실제 사람/사진 경로의 활성화는 미정 계약·접근 통제·실기기 검증 및 별도 실행 승인 뒤로 분리한다.
**Tech Stack:** 기존 Python/표준 라이브러리·Pillow 메모리 fixture, 기존 브라우저 JS/실제 브라우저 도구. 새 provider·수집 서버·인증 서비스·의존성 설치를 계획의 기본값으로 추가하지 않는다.
**Spec:** [갱신된 실제 수집 계약](../reports/new-observation-independent-evaluation-contract-20261117.md), 특히 §3·§4·§8.5–8.7. 이 문서는 계약을 변경하지 않는다.

## 이번 문서 작업 계약

task_id: collection-runtime-plan-20261117
owner: Codex
status: ready_for_review
base_sha: fe720874175133bdb1a375074139a2193e440378
branch: codex/collection-runtime-plan-20261117
allowed_files: docs/collaboration/tasks/collection-runtime-plan-20261117.md
forbidden_files: 그 외 모든 추적 파일, 실제 자료·라벨·모델·provider 설정·기존 근거
structure: 이번에는 문서만 추가, 함수 정의/호출 전이 변화 없음
checks: 상대 링크/필수 차단/미정 값/파일 소유·단계 의존·검사 명령·호출 경로 정적 대조, git diff --check
experiment: 없음

## Global Constraints

- 실제 자료 사용·수집·사람 판정 요청·모델 검증/학습/추론·외부 모델 호출·main 통합·push 금지. 이번에는 계획 파일만 작성한다.
- synthetic_fixture, not_executable_pending_collection_contract_approval, human_truth=false, eligible_for_collection=false를 합성 후보에서도 유지한다. real 사진을 synthetic으로 선언하거나 v1 human 거부를 제거하지 않는다.
- 휴대폰과 기존 eBay 연계 활용 방향, 놓침/오탐 동등 중요도는 유지한다. 기종·OS·브라우저·표시 수치·확대 범위·사람 배정·권한 수단은 미정이다.
- 표본 수·분할 비율·seed·반복 수·개선폭·허용률·오차를 만들어 넣지 않는다. 기존 평가 게이트/진척 배점·수치는 변경하지 않는다. 동등 중요도를 임의1:1 비용으로 변환하지 않는다.
- H 주 평가와 별도 A 평가,4상태·원문 메모·최초 답 보존, 초기 조정 없이 미해결 미확정 종료를 유지한다. AI가 사람 정답을 대신하지 않는다.
- 별도 인력·비용 확보는 필수가 아니다. 서브에이전트 역할 이름이나 같은 권한의 프로세스 분리는 접근 통제/독립성의 증명이 아니다.
- 향후 수정/합성 검사는 ./develop 잠금 안에서 직렬 실행. 코드 파일당 함수 정의 최대7, 프로젝트 호출 전이 최대4. 실패를 숨기는 wrapper·책임 몰아넣기 금지.
- 실행 전에 각 단계 task의 실제 소유 파일과 구조를 커밋한다. 아래 소스 파일 목록은 향후 제안이며 이번 문서 작업의 수정 허용 목록이 아니다.
- wildcard discovery·전체 suite·Torch/모델 의존성 설치 금지. synthetic v1 기록과 브라우저 검증 증거를 덮어쓰지 않는다.

## 현재 근거와 빈틈

|영역|현재 구현 근거|남은 차이|
|---|---|---|
|휴대폰 표시|[page:9](../../../card_condition/observation_page.py:9)는 고정 img 크기/viewport meta를 출력. [display:77](../../../card_condition/observation_display.js:77)는 명시 viewport/DPR/CSS와 바인딩을 확인.|휴대폰 프로파일 없음. 키보드/주소창/회전의 동작과 실제 터치/가독성·이미지 적합성 미확인. 단순 viewport override는 실제 휴대폰 증거가 아님.|
|H 확대|[display:11](../../../card_condition/observation_display.js:11)은 visualViewport.scale과 표시 크기를 기록하고 금지 확대를 일부 감지.|이미지별 명시 확대 조작·이동 좌표·기준 좌표계·초기/최종 상태를 기록하는 H 도구 없음. 페이지 확대와 이미지 확대는 다름.|
|수신/출처|[receipt:17](../../../card_condition/observation_receipt.py:17)은 human 출처 거부. [response:8](../../../card_condition/observation_response.py:8)의 v1 이벤트 키/종류는 고정.|브라우저 source_type이나 reviewer 문자열은 사람 신원/배정 증명이 아님. 실제 사람 수신 경로 없음. 임의 필드 추가 시 기존 validator는 거부해야 함.|
|봉인/접근|[receipt:108](../../../card_condition/observation_receipt.py:108)의 raw/manifest는 생성 전용 저장. 기존 [release.py](../../../card_condition/release.py:1)는 모델 checkpoint 릴리스 계약.|원문 해시는 내용 결합이며 권한 격리가 아님. collection의 배정/봉인/공개/격리 권한표와 실제 OS·도구 경계는 없음. 모델 release를 수집 release로 전용하지 않음.|

이전 [브라우저 합성 결과](../reports/synthetic-observation-browser-20261117.md:23)는 Chrome156.0.8078.80의 시험 조건과33개 합성 회귀 근거다. 이번에는 이를 재실행하지 않으며 휴대폰/사람/독립성 검증으로 확대하지 않는다.

## Review Focus

1. 모바일 키보드·주소창·회전으로 변한 viewport를 고정 승인값으로 다시 저장하거나 자동 복구하지 않는가(S1).
2. H 확대가 기존 CSS gate와 충돌하거나 A에 누출되고, 확대 복원으로 이전 invalidation이 지워지지 않는가(S2).
3. 브라우저의 human/reviewer/session 자기 선언만으로 출처 적격·사람 정답이 되지 않는가(S3).
4. seal의 SHA 재계산이나 역할 문자열 교체만으로 release를 통과시키거나 원문을 덮어쓰지 않는가(S4).
5. 같은 OS 계정/공유 에이전트의 거부 응답을 실제 파일 비접근 증명으로 착각하지 않는가(S4·R2).

## 단계와 합성 선행 가능 여부

|단계|구현 목표|합성만으로 먼저 확인 가능|실제 환경까지 필요한 항목|
|---|---|---|---|
|S0 계약 버전/경계|v1 보존·새 후보 계약/상태/필드 정의|schema·null·출처 분리·구버전 거부|실제 수집 계약의 구체 값 승인|
|S1 휴대폰 표시|관측값과 요구값 분리·표시 gate·모바일 레이아웃|가상 viewport/이벤트, 실패 latch, 원문 보존|선택 휴대폰/브라우저에서 합성 이미지 실기기 확인|
|S2 H 확대|명시 H 확대·이동 이력, A 차단|조작 로그/좌표/해시/수신 대조, 브라우저 화면|실제 터치·OS 확대 등 관측 한계 확인|
|S3 사람 출처 수신|신뢰 경계 밖 자기 선언과 보관자 배정 분리|가짜 인물/배정/미승인/불일치/원문 저장|사람 배정·출처 확인 수단·운영 신뢰 경계|
|S4 봉인/접근|불변 seal·역할별 공개/격리 전이|논리 권한표·파일 경로 거부·무결성·원답 유지|실행 주체별 실제 권한/도구/대화 분리|
|S5 끝단 회귀|표시→확대→내보내기→출처검사→봉인/모의release|실제 브라우저와 합성 파일만으로 연결|실제 자료 없이도 가능, 사람 독립성 증명 아님|
|R1/R2 활성화 준비|실기기·실권한의 합성 검증 후 실제 경로 준비|별도 승인된 기기/환경이면 합성 검증 가능|미정 결정·계약 고정·구현 승인·최종 수집 승인 필요|

실행 의존은 S0→S1→S2→S3→S4→S5. 파일/상태 계약을 공유하므로 직렬 구현을 권장한다. 실제 사람 배정이 미정이어도 S0–S5의 합성 설계·검증은 따로 승인해 진행할 수 있다. 한 영역의 실제 의존으로 독립적인 합성 작업을 막지 않는다.

## S0 새 후보 계약과 v1 보호

**향후 소유 파일:** 새 docs/collaboration/contracts/collection-runtime-v2-20261117.md, card_condition/observation_collection_contract.py, tests/test_observation_collection_contract.py. 기존 v1 소스는 이 단계에서 수정하지 않는다.

**Interfaces:** 새 후보 계약은 contract_id/버전·spec SHA, evidence_origin=synthetic_fixture, 실행 불가 상태, 요구 display profile과 별도 measured 환경, zoom 정책, source assignment 참조, seal/access 정책 참조를 갖는다. 출처 주장(claimed actor)과 실제 증거의 합성 기원은 별도 필드다. validate_collection_contract(contract)는 정확한 키·타입·참조를 검사하고 readiness(contract)는 누락 조건 ID를 반환한다. 둘은 승인값을 생성하지 않는다. v2 envelope의 실제 필드 집합·canonical digest·버전 거부 규칙과 sidecar→독립 validator 연결은 이 단계 문서로 코드보다 먼저 고정한다. S1/S2에서 추가 관측/확대 기록은 v1 response가 아닌 별도 candidate 채널에서 조립하며 S3의 validator가 이를 읽는다. 공유 인터페이스 고정 전에 구현자가 각자 필드를 정하지 않는다. 이 문서 작성 작업이 실제 기기/정책 수치 결정을 대신하지 않는다.

- [ ] RED: null profile을 승인 수치로 채우거나 미정 assignment에서 ready로 바꾸는 사례, human 주장과 synthetic 기원 혼동, v2를 v1로 보낸 사례를 검사한다. v1은 확장 키를 여전히 거부해야 한다.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_collection_contract.py -v`. 최초에는 새 계약/검사 미구현으로 실패, 구현 뒤 모든 사례 통과를 확인한다.
- [ ] 최소 구현: 순수 검사와 미정/차단 사유 반환만. 새 collection 후보는 항상 합성·수집 미승인·human_truth/eligible=false. 실제 human 입력을 받는 옵션/플래그는 만들지 않는다.
- [ ] GREEN과 git diff --check 확인 후 로컬 커밋. 스키마가 고정되지 않으면 다음 단계 구현을 시작하지 않는다.

## S1 휴대폰 표시 관측과 레이아웃

**향후 소유 파일:** 새 card_condition/observation_viewport.js, tests/observation_viewport.test.cjs, tests/test_observation_mobile.py. 수정 card_condition/observation_page.py, card_condition/observation_display.js. 새로운 이벤트 구조는 S0 문서의 candidate 채널에만 두며 기존 v1 응답 스키마에 섞지 않는다.

**Interfaces:** readViewport()는 layout/visual viewport·DPR·orientation·visibility 등 실제 제공된 관측값만 반환하고 없는 값은 null이다. matchesViewport(required,measured)는 선언된 조건만 비교한다. 명시 기기 profile과 이번 브라우저 관측을 별개로 보관한다. readViewport는 프로젝트 helper를 다시 호출하지 않는 leaf로 둔다. 페이지는 기존 render_page(packet,assets)의 합성 제약을 보존하며 시험용 프로파일로만 확인한다. 기종 식별/실기기 승인을 UA 문자열에서 추정하지 않는다.

- [ ] RED: 키보드/주소창/회전·visualViewport 미제공·DPR 변경·0크기·명시 조건 불일치에서 입력과 원응답이 안전하게 유지되는지 검사한다. 프로파일 null과 실측값을 섞어 채우면 실패해야 한다.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_mobile.py -v`. Node/DOM stub 결과와 이후 실제 브라우저 시험을 분리한다.
- [ ] 구현: 문맥/구역 이미지와4상태·메모·내보내기를 모바일 폭에서 접근 가능하게 배치한다. 승인된 크기/허용 오차가 없으면 임의 반응형 축소를 제품 기준으로 적용하지 않는다. 환경 변경의 원인을 기록하되 불일치/관측 불능을 임의 무시하거나 latch를 해제하지 않는다. 구체 조건은 candidate profile readiness에서 차단한다.
- [ ] GREEN: 합성 조건의 실제 브라우저 SHA/Blob/decode·잠금/활성화·원문 유지 확인. fixture 수치는 시험 조건으로만 기록한다. 고정한 실제 휴대폰 확인은 R1로 남긴다. 검토 후 로컬 커밋.

## S2 H 이미지 확대·이동의 명시 기록

**향후 소유 파일:** 새 card_condition/observation_zoom.js, card_condition/observation_zoom.py, tests/observation_zoom.test.cjs, tests/test_observation_zoom.py. 수정 observation_page.py, observation_display.js. 기존 v1 response.js/response.py 키는 바꾸지 않으며 확대 로그는 버전된 candidate envelope에 별도 보존한다.

**Interfaces:** attachZoomControls(mode,images,log)는 H에만 명시적 조작을 제공한다. snapshotZoom(image)는 asset ref/SHA·entry·배율·원이미지 좌표계의 이동·기준 viewport와 관측 순서를 기록한다. validate_zoom_log(contract,events)는 시작/조작/제출 상태와 asset 연결을 검사하는 leaf 성격의 검사다. 지원 배율/이동 범위는 선택 기기와 별도 확정할 사항이며 여기서 숫자를 정하지 않는다. 시험용 입력값은 synthetic profile에서만 공급한다.

- [ ] RED: H 확대/이동/복원, A 조작 차단, 다른 이미지 ref의 로그·누락/역행 이벤트·범위 미정 상태, CSS gate와 변환 크기의 불일치, 복원 뒤 이전 invalidation 유지.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_zoom.py -v`. 실제 브라우저 조작은 별도 화면/원문 증거를 남긴다.
- [ ] 구현: 앱이 제어하는 이미지 확대와 브라우저/OS 확대를 구분한다. base CSS 영역·transform 후 영역·원본 natural 크기를 별도 관측하고 확대를 이유로 기존 연결/SHA 검사를 끄지 않는다. 후보 경로의 의도된 H 변환만 별도 검사하며 v1 gate는 같은 입력에서 같은 결과여야 한다. 브라우저 scale만으로 이미지 이동이나 사람의 실제 관찰을 추정하지 않는다.
- [ ] GREEN: H 조작 이력이 후보 내보내기/독립 수신에 같은 순서·좌표·원문으로 남고 A는 확대를 정상화하지 않는다. 앱 밖 확대 관측 불능은 제한/미확정으로 기록한다. 검토 후 로컬 커밋.

## S3 사람 출처를 다룰 수신 계약의 합성 구현

**향후 소유 파일:** 새 card_condition/observation_source.py, card_condition/observation_collection_response.py, card_condition/observation_collection_receipt.py, tests/test_observation_source.py, tests/test_observation_collection_receipt.py. 기존 observation_receipt.py의 human 거부는 수정하지 않는다.

**Interfaces:** validate_source_context(context,assignment)는 브라우저 원문과 별도로 제공되는 보관자 문맥의 contract/session/rater/mode/허용 범위를 대조한다. candidate packet/response의 독립 validator와 capture_collection_receipt(contract,raw_bytes,custody_context,ledger)를 새 후보 경로로 둔다. 필드 이름은 S0에 고정한 스키마와 동일하게 구현한다. v1 capture_receipt를 감싸 v2를 통과시키거나 실제 자료를 v1 synthetic packet에 넣지 않는다. 새 후보의 모든 사람 ID·배정 증거는 시험용이며 실제 사람으로 분류하지 않는다.

- [ ] RED: human/reviewer 자기 선언만 있는 입력, 잘못된 session/배정/문맥/모드, 미승인 계약, AI/unknown, 중복 JSON키, UTF-8 메모, 별도 received_at, 같은 원문/다른 context, 부분 저장·재해시 파생 status 변조.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_source.py -v`와 `.venv/bin/python -m unittest discover -s tests -p test_observation_collection_receipt.py -v`를 각각 실행.
- [ ] 구현: 원문 bytes·SHA와 custody 문맥을 분리해 생성 전용 저장. 검증 실패도 원문 보존/거부 사유로 남기며 저장 자체가 사람 정답 채택은 아니다. 기존 persist_receipt의 생성 전용 IO를 재사용할 수 있으나 v1 read_records/분류기로 v2를 해석하지 않는다. 새 identity에는 계약/버전/원문/수신 문맥이 연결돼 별개 문맥이 병합되지 않아야 한다.
- [ ] GREEN: capture/load/멱등의 상태·사유 규칙이 같고 모든 합성 결과 human_truth/eligible=false. 실제 사람 source 활성화·신원 확인 방식은 R2까지 차단한다. 서명/인증 서비스는 선택 근거 없이 도입하지 않는다. 검토 후 로컬 커밋.

## S4 불변 봉인·역할별 공개·격리 전이

**향후 소유 파일:** 새 card_condition/observation_seal.py, card_condition/observation_access.py, tests/test_observation_seal.py, tests/test_observation_access.py. 일반 모델 release.py는 수정하지 않는다.

**Interfaces:** seal_receipts(contract,receipt_refs,ledger)는 승인된 receipt ID/raw SHA·정답 버전·배정/관측 조건·미확정/누락/격리 집합·모집 분모를 불변 manifest에 연결한다. authorize(role,action,state,policy)는 외부의 신뢰 경계에서 부여한 역할에 대해서만 허용/거부·사유를 반환한다. 파일 경로/역연결 ID를 개발자 집계 결과에 포함하지 않는다. seal/release 기록과 실제 파일 접근 권한은 서로 다른 검사다.

- [ ] RED: 봉인 이후 원문/manifest 변경·같은 seal 덮어쓰기·미확정 정상 보충·다른 역할/session·사전 동결 없는 release·평가 전 개별 답 열람·가짜 역할 문자열·사고 후 공개·부분 seal. 상대경로 이탈/심볼릭 링크를 통한 누출도 합성 임시 루트로 검사한다.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_seal.py -v`와 `.venv/bin/python -m unittest discover -s tests -p test_observation_access.py -v`를 각각 실행.
- [ ] 구현: 최초 원답은 불변, 후속 상태는 별도 사건 기록. 미해결은 미확정, 사고는 계약의 영향범위/session 격리 규칙. release는 후보/계획 동결 참조와 권한·시점을 요구하고 승인 없는 모의 release는 synthetic 시험에만 한정한다. 전체를 다시 쓰는 주체에 대한 SHA의 인증 한계도 표시한다.
- [ ] GREEN: fake 역할별 입력이 기대 필드만 받는지 확인. 같은 OS 계정이 임시 루트를 직접 읽을 수 있으면 논리 정책 통과와 별개로 실제 접근 분리 미확인/미충족을 보고한다. task 통과로 독립 평가 준비 완료를 선언하지 않는다. 검토 후 로컬 커밋.

## S5 합성 끝단 회귀·브라우저 증거·인계

**향후 소유 파일:** 새 tests/observation_collection_browser_fixture.py, tests/test_observation_collection_flow.py, docs/collaboration/reports/collection-runtime-synthetic-20261117.md. JS 추가 파일의 배포 누락을 막는 범위에서 pyproject.toml의 package-data 항목만 변경 대상으로 지정한다. 새 의존성은 추가하지 않는다.

- [ ] RED: 후보 내보내기의 로그 누락·잘못된 출처 주장·봉인/공개 필드 혼입·새 JS package-data 누락을 재현하는 검사부터 작성. 이미지 의미 판정은 하지 않는다.
- [ ] 실행: `.venv/bin/python -m unittest discover -s tests -p test_observation_collection_flow.py -v`. 기존6파일은 test_observation_packet.py, test_observation_assets.py, test_observation_page.py, test_observation_response.py, test_observation_receipt.py, test_observation_p2.py로 각각 지정한다. 축약 이름·wildcard를 명령 인자로 쓰지 않는다.
- [ ] 실제 브라우저: 시작 전 잠금→합성 SHA/Blob/decode→H 조작/A 차단→테스트가 정한4상태/메모→실제 내보내기 문자열 추출. DOM read-only 추출→UTF-8 파일→receipt raw.bin의 bytes/SHA를 브라우저 자체 증거와 대조. Python/Node에서 응답을 재생성해 대체하지 않는다.
- [ ] 합성 receipt→seal→역할별 모의 공개/거부/격리 연결. 모든 후보는 synthetic/실행 불가/false 유지. 실제 브라우저·Node stub·정적 검사 결과를 각각 기록한다.
- [ ] 이전 test_observation_browser_receipt.py는 이번 흐름을 대신하는 테스트가 아니다. 원래 버전의 실제 원문 증거가 있을 때만 정확 파일로 재실행하고 없으면 의존/미실행으로 기록한다. 과거 증거를 새 후보 입력으로 바꾸지 않는다.
- [ ] 독립 최종 코드 검토와 중요 지적 RED→GREEN, 정확 회귀 후 로컬 커밋. 실제 구현 턴에는 고정 진척 두 정본을 읽고 정적 성과 HTML을 생성·열기·렌더 구분, 합성 화면/원문/소스 SHA·rollback을 인계한다. 실제 사진·모델 성능 주장은 하지 않는다.

## R1/R2 실제 환경 의존 — 미정 유지, 이번 실행 금지

**R1 휴대폰:** 사용자 기종·OS·브라우저를 지정하고 실제 표시 수치/범위·H 확대 조작·필수 관측/누락 정책을 고정해야 한다. 승인 뒤에도 먼저 합성 이미지만으로 주소창/키보드/회전·터치·앱 확대와 OS/브라우저 확대·내보내기 원문을 확인한다. 브라우저 viewport override 통과를 실제 휴대폰 통과로 대체하지 않는다. 관측하지 못한 값은 null/한계로 보존하며 제품 수용 수치는 결과 뒤에 정하지 않는다.

**R2 사람/접근 경계:** 사람 H/A 배정·보관자/평가자·담당 자동화 ID·역할별 파일/도구/대화/메모리/회신 허용 범위·권한 집행 주체·보호 자료 비노출 제외 확인 수단이 필요하다. 별도 인력 확보 없이 기존 참여자/승인된 절차 자동화로 설계하되 신뢰 경계가 확보되지 않으면 보류한다. 한 사람이면 A봉인후H의 제한을 기록하고 여러 사람의 독립 답으로 세지 않는다. 실제 수집 receiver 활성화는 문서와 소스의 별도 변경 task로 배정하며 합성 human 모의 입력을 실제 사람 응답으로 승격하지 않는다.

실제 권한 검증은 준비된 별도 실행 신원/도구 환경에서 합성 sentinel 파일로 허용 접근과 금지 파일 직접 열기를 모두 확인해야 한다. 거부돼야 할 주체에게 파일시스템/상위 도구/주 대화로 우회 접근이 남으면 실패다. 지금 OS 계정/키/앱 권한을 새로 만들거나 변경하지 않으며 격리 수단은 미정이다. 수단이 정해지기 전 특정 ACL/암호화/외부 서비스 도입을 확정하지 않는다.

실제 eBay 모집/권한·중복 배제·표본/수용 수치 미정도 전체 수집 차단으로 남는다. 이 네 영역의 기술 완성만으로 계약 전체를 실행 가능으로 표시하지 않는다. 실제 자료/수집의 시작은 기술 검증 뒤에도 별도 사용자 실행 승인 대상이며 모델 실행과 main/push 승인을 포함하지 않는다.

## 구조·소유권 검토 계획

현재 함수 수는 observation_packet.py7/assets.py2/page.py1/response.py5/receipt.py7/status.py1, display.js7/response.js4다. 현재 packet/receipt에 함수를 추가하는 방식을 전제로 하지 않는다. 새 역할/이벤트 계약은 각각 응집된 새 파일에 두고 source validators가 서로를 불필요하게 감싸지 않게 한다.

|변경 후보|변경 전|계획 후 상한/확인|
|---|---:|---|
|observation_page.py / observation_display.js|1 / 7|각각7 이하. display에 새 함수를 추가하려면 viewport/zoom의 응집 책임을 새 파일로 배정하고 파일 간 호출을 함께 센다.|
|새 viewport.js / zoom.js / zoom.py|0|각각7 이하. 함수별 책임은 환경 관측/비교 또는 확대 조작/기록/검사로 한정.|
|새 contract/source/collection_response/collection_receipt/seal/access|0|각각7 이하. 실제 정의 수는 단계 task·AST/named callback 검사로 확정하고 초과하면 커밋 전 보완.|
|기존 packet/receipt/response와 fixture/tests|7/7/5 등|직접 확장하지 않는 것을 기본으로 한다. v1 schema/거부/원답 보존을 기존 정확 검사로 보호.|

기존 최장 render_page→verify_assets→validate_packet→validate_profile→exact_keys=4와 capture_receipt→validate_response→validate_observations→validate_event→exact_keys=4를 유지한다. v2 API를 위 API의 상위 wrapper로 붙이지 않는다. 후보의 주요 경로는 capture_collection_receipt→validate_collection_response→validate_zoom_log→exact_keys처럼 최대4 안에 직접 배치하고, 조립은 최상위에서 순서대로 수행해 검증 중첩을 늘리지 않는다. entry orchestrator의 프로젝트 호출도 함께 세며 동적 callback 경로는 검토 대상으로 표시한다. 실제 코드가 없으므로 이 표를 구조 통과 결과로 보고하지 않는다.

## 자기 검토·검증·완료 인계

- 계약 §8.5–8.7의 네 기술 영역·미정 항목·수집/모델 분리·기존 eBay 경계·사람/자동화 역할을 각 단계에 연결했다.
- S0의 버전 계약을 선행 조건으로 고정하고 표시/확대/출처/봉인 shared state는 직렬 소유로 배정한다. S5가 새 함수를 직접 구현하는 단계로 범위를 넓히지 않는다.
- 미정값은 정책/환경 의존으로 명시했으며 실행 가능한 합성 케이스와 실제 활성화 준비를 분리했다. 계획이 새 데이터 수집·사람 판정·수치 승인을 대신하지 않는다.
- 이번 실제 검증은 문서 링크·필수 상태·소유 파일·순서/경계·공백 대조만. 소스 수정·테스트/실브라우저/모델 실행·실자료 접근 없음. 과거33개 통과를 새 성과로 세지 않는다.
- 문서 준비 범위이므로 HTML_REPORTING.md에 따라 이번 새 성과 HTML은 생성/열기/렌더하지 않는다. 개발 진척은 정본78/100 유지이며 이 계획으로 점수를 올리지 않는다.

**리스크:** 확대와 strict CSS 조건의 충돌, 누락 로그의 정상 승격, human 문자열의 과신, 논리 권한과 실제 격리 혼동, 접근 가능한 이전 대화/도구를 통한 누출, 문서 계획을 실제 수집 준비 완료로 오인하는 위험이 있다. 단계별 반례와 실제 의존 차단으로 검증한다.
**롤백:** 이번 계획 커밋만 revert하면 된다. 향후 구현은 단계별 커밋을 역순 revert하고 합성 근거/원응답/이전 v1을 보존한다. 실제 수집 자료는 생성하지 않았으며 삭제·복원할 대상이 없다.
**Handoff:** 계획 파일만 로컬 커밋하고 SHA·clean 상태·문서 검사 결과를 최종 응답에 남긴다. 구현은 이번 요청 범위에 포함하지 않으며 자동 실행을 약속하지 않는다.

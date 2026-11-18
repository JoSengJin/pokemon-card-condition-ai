# 수집 런타임 S0–S5 합성 구현·검증 결과

2026-11-18 KST. 개발 진척 **78/100 유지** (`usable-card-analysis-v1.13`, production_ready=false). 이번 성과는 **합성 후보 표시·H 확대·출처 수신·보관 봉인/모의권한 연결**이며, 정확히 지정한14개 파일의 **57개 회귀 통과(skip0)**다. 실제 사람 출처 수신/휴대폰 적합성/독립 평가/모델 품질 개선을 완료했다는 뜻은 아니다.

## 기준·권한·커밋
- 시작 e21768e086c9c2bfefecb191fab63af243b926c6, 브랜치 codex/collection-runtime-synthetic-20261118. 기존 격리 worktree에서 새 전용 브랜치를 사용했고 기존 계획/계약 브랜치는 보존했다.
- 최종 검증 소스 **8d24d2c91b4fce6c570fde723e32c697769d95c5**. 후속 결과 문서 커밋과 구분한다. 최종 문서 SHA/clean 상태는 handoff.json 및 세션 완료 응답에 기록한다.
- 사용자 승인 범위의 S0–S5 합성 구현·검사·읽기 전용 교차 검토만 수행했다. 실제 자료·기존 사진/라벨·보호 자료를 읽거나 수집하지 않았다. 모델/worker/선택기/운영 fallback/실제 provider/main 통합/push 미실행. 추가 모델 의존성 설치 없음.
- 모델 성능 실험이 아니므로 ./experiment·record.json을 생성하지 않았다. 누락률/오탐률/분모/일반화 개선은 미측정이고 개발 진척 증가로 세지 않는다.

## 단계별 결과·독립 검토
|단계|구현/회귀·교차 검토|로컬 구현 커밋|
|---|---|---|
|S0 계약|새 v2 exact schema/digest/null/readiness. RED3→GREEN3, 기존31통과. reviewer 중요잔여 없음. actual collection readiness/false flags 고정.|829064b|
|S1 표시|선택 인자의 후보 HTML/viewport sidecar. 새3 및 기존 관련19 통과. 실제 Chrome export/메모 확인. reviewer 중요잔여 없음.|69f8600|
|S2 확대|같은 Blob의 별도 H 렌즈와 독립 로그/A 빈 로그. 새4+계약3+mobile3/기존 관련19 통과. 검토 CSS latch·초기1/구간 모순2건 RED→GREEN 및 재검토.|babc948|
|S3 출처·수신|합성 배정/custody와 브라우저 주장을 분리. source2/receipt4, 누적47통과. 금지 human 출처 재해시가 읽기 경로로 들어오는 반례1건 RED→GREEN/재검토.|e01e46f|
|S4 봉인·모의권한|create-only unresolved 봉인, 역할 집계/동결참조/release/격리 사건 재생. access2/seal4+관련16통과. cohort 읽기→게시 경쟁 조건1건 RED→양잠금 유지 GREEN/재검토.|046fbc9|
|S5 끝단|실제 Chrome 문자열→raw.bin/SHA→의미 재검사→봉인→모의 공개/집계/격리. JS package-data 누락3사례 RED→보완. 최종 비정수 확대 반례 보완 후 전체57통과. 새 전체 diff reviewer 및 재검토 중요잔여 없음.|8d24d2c|

단계 task/버전 문서 선행 커밋은 Git 이력에 별도 보존했다. reviewer는 소스/테스트/계약만 읽었고 실제 자료/artifacts·검사 실행·수정·외부 provider를 사용하지 않았다. reviewer 합의는 브라우저 관측·독립성 증명이 아니다. 회귀 숫자는 단계 사이 중복 실행을 포함하므로 합산하지 않으며 최종 고유 검사57개와 구분한다.

## 핵심 diff·보존 조건
- v1 packet/assets/display/response/receipt/status 소스와 고정 진척 두 정본은 base와 동일. default render_page H/A 결과는 base 코드를 같은 메모리 fixture에 적용한 반환 bytes와 동일함을 확인했다.
- page에 optional collection_contract 경로만 추가. 새 contract/viewport/zoom/response 채널은 v1 키에 섞지 않으며 v1은 확장 키를 계속 거부한다. 자동 이미지 축소로 제품 크기를 정하지 않고 고정 영역 스크롤/컨트롤 폭을 제한했다.
- H는 원래 표시 img의 CSS/게이트를 변경하지 않고 같은 검증 Blob의 렌즈를 별도로 확대한다. ref/SHA/URL/decode/natural/base CSS/변환/이동·실제 좌표를 기록한다. 외부 src/style/크기 변조는 즉시 복원해도 latch되며 정상 자체 transform 기록만 동기 소비한다.
- 새 receiver는 actual source_type=human을 신규/재읽기 모두 거부한다. 브라우저 human 선택은 합성 시험용 주장이다. synthetic 배정 대조 성공도 human_truth/eligible_for_collection=false, collection_ready=false 유지. 원문 bytes·브라우저 session·별도 received_at·status/reasons를 저장하고 load/멱등에서 재산정한다.
- 봉인은 현재 contract의 전체 receipt/raw 해시를 연결하는 **보관 봉인**이다. truth_status=unresolved_synthetic이며 사람 정답을 고르거나 미확정을 정상으로 바꾸지 않는다. S5 최상위에서 S3 의미 검사를 먼저 실행하고 S4는 IO/hash 연결을 확인한다. receipt→seal 순서 잠금을 cohort 읽기부터 게시까지 유지한다.
- 모의 권한은 외부 synthetic policy의 principal/role/contract를 대조하고 과거 전이도 재생 검증한다. 개발자 출력은 receipt_count/status_counts/quarantined만, 개별 ID·사진·메모는 없다. actual_access_verified=false이며 파일/OS/에이전트 접근을 강제하는 구현은 아니다. 기존 모델 release.py는 수정하지 않았다.
- 기존 synthetic_fixture/not_executable_pending_collection_contract_approval/false flags,4상태·메모·완료 답 보존·AI 사람정답 대체 금지·추가 인력/비용 비필수·기존 평가 게이트 유지.

## 비정수 확대 반례와 기술 정밀도
최종 reviewer가 엄격한 DOMRect 동등 비교를 지적했고 실제 Chrome에서64 CSS×1.1이70.4000015258789/70.39999389648438로 기록되어 입력이 잠기는 반례를 확인했다(fractional-red.raw). geometry_edges를 추가해 끝점차와 측정 크기를 정확히 연결하고, binary32 좌표/scale의 IEEE-754 ULP에서 유도한 반올림 범위만 JS/Python 공통으로 적용했다. 임의 px 허용 오차·제품 수용 수치는 추가하지 않았다. 1px CSS 변조는 계속 거부한다. style canonical 문자열과 observer latch/base gate도 보존한다. 최종 Chrome에서1.1·1.123456789·1.9999999999999998 정상 동작을 확인했다. 다른 렌더러/실제 휴대폰 적합성을 주장하지 않는다.

## 실제 브라우저 시험·원문 증거
- Chrome **156.0.8078.80/macOS**: 브라우저 userAgentData.fullVersionList 자체 관측. **390×844 CSS px/DPR1 viewport override**, 실제 휴대폰/터치 시험이 아니다. 이 수치는 승인 기기/프로파일에 넣지 않았다. contract viewport/DPR null 유지, CSS64·배율1~2·이동8 등은 fixture 전용 숫자다.
- pages는 기존 memory fixture/render_page로 생성했다. start 버튼으로 실제 initialize를 지연해 검증 전 잠금을 확인했고 crypto/Blob/decode/displayReady를 대체하지 않았다. 실패용 자산 변경은 생성 후 합성 전송 결과에서만 수행했다.
- 127.0.0.1:43188의 합성 pages 폴더만 정적 제공했다. 저장소 루트/artifacts 전체/.claude/실자료는 서비스하지 않았다. viewport 원복 완료, 서버 종료/HTML 열기·렌더는 최종 인계 확인란에 기록한다.

|실제 시나리오|결과|
|---|---|
|H/A 시작 전·후|입력 disabled→실제 SHA/Blob/decode 후 활성화. H 렌즈 연결 확인, A에는 H 조작이 없음.|
|4상태/메모|normal→defect→unassessable→unreviewed 명시 전이와 한글·앞뒤 공백·줄바꿈 원문 보존. 자동 시험이며 사람/AI에게 이미지 의미 판단을 요청하지 않음.|
|미정 H 범위|합성 기본 응답 시험은 가능하나 H 적용 버튼 잠김. 후보 수신은 미확정 zoom을 표시 검증 성공으로 인정하지 않음. 실제 수집 readiness는 항상 false.|
|명시 viewport391×844 불일치|실제390×844에서 입력 차단. 프로파일 자동 보충/복원 없음.|
|bytes 변조/누락/해시 일치 decode 실패|각각 gate 차단, invalidated 유지.|
|H 확대/이동/소수 배율|2배/원본X1과1.1 등 실제 로그, base gate 유지.|
|렌즈 CSS 오류 후 즉시 복원|입력 잠금 유지, defect/메모 원답 보존. 실제 수신 status=pending_observation.|

실제 textarea#collection-out.value를 documented read-only DOM API로 읽고 UTF-8 파일로 보존했다. JSON 재직렬화·strip·정규화로 원문을 재생성하지 않았다. 브라우저 TextEncoder/crypto.subtle로 같은 문자열의 byte 수/SHA를 측정해 파일→receipt raw.bin과 대조했다. parsing은 context/session 검증을 위해서만 했으며 저장 bytes를 대체하지 않았다. 이 증거는 HTTP wire가 아닌 **브라우저 출력 문자열의 UTF-8 bytes**에 해당한다.

|최종 실제 원문|bytes|SHA256|수신 상태|
|---|---:|---|---|
|h|21219|366849c5dd0b210348a3c8a25d3563724bd19f3e6cace2759310686d027e137b|synthetic_only|
|a|16597|e6845d199fdefa2c3142f9192807a29f0b8cab4299fce199f89fcc0f91db8299|synthetic_only|
|fractional|8957|e6c0fe3ff7e9d9feaeb27e01d6695082b8e53e9e05b82a0b81d58c0ae889df25|synthetic_only|
|css-restored|18478|909248f4c248cd335d5578ee7dfac709ad61eddbc8474e890bb7e7c9cddf6ff9|pending_observation|

네 원문 모두 browser proof/추출 파일/raw.bin의 bytes·SHA 일치. 실제 session_id를 가짜 rater 배정에 연결하고 별도 received_at 보존·정확 재접수만 멱등·다른 received_at context는 분리했다. load 재검사→unresolved seal 확인 후 정상 합성 원문은 모의 freeze/release·평가자 정책 허용(actual_access_verified=false)·개발자 집계·격리 후 거부까지 시험했다. CSS 실패 원문은 pending_observation 상태로 봉인·격리했다. 가짜 인물/배정/동결 참조이며 실제 사람/모델 평가가 아니다.

이전 코드의 원문은 before-geometry-fix/로 보존하고 최종 코드는 새 원문으로 다시 확인했다. 근거: browser-checks.json, h/a/fractional/css-restored.raw와proof.json, 해당jpg, flow-evidence.json, flow-receipts/·flow-seals/. 첫 source label locator의 exact label 매칭이 도구에서 안 돼 실제 DOM에서 확인한id로 조작했다. 기능 통과로 없는 도구 성공을 가정하지 않았다.

## 정확한 실행·검사·구조
모든 편집/합성 검사는 ./develop 잠금 안에서 직렬 실행. 기존 전용 venv/Pillow와 Node를 사용했고 새 라이브러리·Torch·모델 설치 없음.

```sh
./develop -- env PYTHONPATH=.:tests .venv/bin/python tests/observation_collection_browser_fixture.py artifacts/collection-runtime-synthetic-20261118
.venv/bin/python -m http.server 43188 --bind 127.0.0.1 --directory artifacts/collection-runtime-synthetic-20261118/pages
```

아래 파일을 각각 `.venv/bin/python -m unittest discover -s tests -p <정확파일명> -v`로 잠금 내부 subprocess에서 실행했다. 실제 끝단에는 COLLECTION_BROWSER_EVIDENCE=artifacts/collection-runtime-synthetic-20261118을 전달했다. 전체 stdout/stderr/정확 COMMAND는 final-*.log. wildcard discovery/전체 suite는 실행하지 않았다.

|파일|검사 수|결과|
|---|---:|---|
|test_observation_packet.py|6|통과|
|test_observation_assets.py|6|통과|
|test_observation_page.py|3|통과|
|test_observation_response.py|5|통과|
|test_observation_receipt.py|6|통과|
|test_observation_p2.py|5|통과|
|test_observation_collection_contract.py|3|통과|
|test_observation_mobile.py|3|통과|
|test_observation_zoom.py|5|통과|
|test_observation_source.py|2|통과|
|test_observation_collection_receipt.py|4|통과|
|test_observation_access.py|2|통과|
|test_observation_seal.py|4|통과|
|test_observation_collection_flow.py|3|통과|

Node DOM/decode stub은 구조/회귀 검사이며 실제 Chrome 시험과 분리했다. 이전 test_observation_browser_receipt.py는 과거 별도 원문 기반이므로 이번 끝단 통과 수에 포함하지 않았다. package-data 등록/소스 리소스 확인은 했으나 wheel build/설치·배포 검증은 미실행이다.

정의 수는 Python AST(메서드/중첩/lambda 포함), JS named/arrow/메서드 대조와 node --check로 확인. 최대7. 최종 viewport4/zoom JS7/후보export1, contract3/zoom Python2/source1/candidate response2/receipt5/access2/seal5/page1. tests 최대7. 새 arrow 콜백까지 세어 초과했던 zoom을 for 순회로 정리했다. source-manifest.json에 소스별 SHA/정의 수를 보존했다.

최장 주요 프로젝트 전이4: capture/load→validate_response→validate_observations→validate_event→exact_keys; capture/load→validate_collection_response→validate_collection_contract→validate_profile→exact_keys; exportCollection→finishZoom→recordZoom→snapshotZoom→zoomGeometryMatches. 새 geometry helper는 leaf다. 기존 renderer→verify_assets→validate_packet→validate_profile→exact_keys도4. seal 전 S3검사와 seal은 최상위에서 순차 호출해 wrapper 깊이를 늘리지 않는다. 이벤트 callback도 독립 reviewer와 경로를 대조했다.

## 변경 파일 전체
- card_condition/observation_access.py
- card_condition/observation_collection_contract.py
- card_condition/observation_collection_receipt.py
- card_condition/observation_collection_response.js
- card_condition/observation_collection_response.py
- card_condition/observation_page.py
- card_condition/observation_seal.py
- card_condition/observation_source.py
- card_condition/observation_viewport.js
- card_condition/observation_zoom.js
- card_condition/observation_zoom.py
- docs/collaboration/contracts/collection-runtime-v2-20261117.md
- docs/collaboration/reports/collection-runtime-synthetic-20261117.md
- docs/collaboration/tasks/collection-runtime-execution-20261118.md
- pyproject.toml
- tests/collection_runtime_fixture.py
- tests/observation_collection_browser_fixture.py
- tests/observation_viewport.test.cjs
- tests/observation_zoom.test.cjs
- tests/test_observation_access.py
- tests/test_observation_collection_contract.py
- tests/test_observation_collection_flow.py
- tests/test_observation_collection_receipt.py
- tests/test_observation_mobile.py
- tests/test_observation_seal.py
- tests/test_observation_source.py
- tests/test_observation_zoom.py

## 미정·리스크·롤백
- **R1/R2 미완료:** 휴대폰 기종/OS/브라우저·실제 표시/확대/터치·사람 H/A 배정·실제 출처 확인·보관/평가 주체·파일/도구/대화/메모리 접근 통제·보호 자료 비노출 중복 확인 수단은 미정/미검증. eBay 모집·권한·표본·배분·수용 수치도 그대로다. 이 작업을 이유로 수집을 시작하지 않는다.
- 합성 actor 주장과 policy는 신원 인증/권한 격리/사람 독립 판정이 아니다. 같은 OS 계정의 직접 파일 열기를 막았다고 주장하지 않는다. 실제 sentinel/분리 신원 시험도 실행하지 않았다.
- SHA는 보관 내용/연결 검사이며 쓰기 권한자의 악의적 전체 재작성에 대한 서명이 아니다. 본 seal은 unresolved 보관 봉인으로 사람 정답 확정·운영 채택을 하지 않는다.
- 엄격한 새 후보 schema는 과거 후보 원문과 호환되지 않을 수 있다. 기존 원문/manifest를 마이그레이션·정상 승격·삭제하지 않는다. 실제 자료를 synthetic으로 위장하지 않는다.
- 최초 답·4상태·미확정/판단 불가와 원문을 보존한다. 사람 답 재요청·AI 다수결·정상 보충 없음. 합성 실패/저장 오류는 모델 성능 수치가 아니다.
- 롤백은 최종 결과 문서 커밋부터 S5 8d24d2c→S4 046fbc9→S3 e01e46f→S2 babc948→S1 69f8600→S0 829064b의 역순 revert. 단계 사이의 계약 보완 커밋도 해당 단계 철회 시 역순 포함한다. 실제 rollback은 하지 않았다. e21768e 이하 계획/실제 수집 초안/이전 브라우저 근거·다른 worktree는 보존한다.

## 에튜 포인트
1. **멱등성과 원문 보존:** 원문SHA와별도수신문맥을identity에함께넣으면 같은 접수는재사용하면서 같은본문의다른session/수신시각은합치지 않는다. 이번 raw.bin은내보낸bytes그대로이고수신시각만다르면다른receipt다.
2. **잠금 범위:** 결과파일만잠그면입력집합이중간에변할수있다. 이번 seal은receipt잠금→seal잠금순으로입력읽기부터게시까지보호해새접수와subset봉인경쟁을막는다.

HTML: artifacts/collection-runtime-synthetic-20261118/report.html. 열기/실제렌더·server종료·viewport원복과최종SHA/clean은최종확인후task/handoff에기록한다. 이번승인S0–S5를마친뒤종료하며최종응답이후자동실행을약속하지않는다.

최종 인계 확인(2026-11-18 KST): 정적 report.html 열기 요청 성공 및 실제 Chrome AX/화면 렌더 확인(report.jpg). viewport override 원복 완료. 재개 시 이전 시험 서버 listener 없음 확인 후 동일 pages/127.0.0.1만 잠시 재시작해 보고서를 확인했고, 해당 PID11747 종료(exit143) 및43188 listener 해제를 확인했다. 현재 보고서 렌더 탭은 열어 두었고 서버는 종료했다. 사용자 재개 후 소스는8d24d2c와 동일하며 테스트 재실행을 새 성과로 추가하지 않았다. 최종 문서 커밋 SHA/clean 상태는 handoff.json과 세션 완료 응답에 제공한다. S0–S5 승인 범위 완료, R1/R2·실제 모집/표본/수치/권한 준비는 미정·미완료로 유지한다.

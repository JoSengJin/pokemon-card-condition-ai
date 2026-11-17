# 수집 런타임 합성 구현 실행 계약·ledger
owner: Codex
status: implementing
base_sha: e21768e086c9c2bfefecb191fab63af243b926c6
branch: codex/collection-runtime-synthetic-20261118
spec: collection-runtime-plan-20261117.md 및 new-observation-independent-evaluation-contract-20261117.md

사용자 승인: S0부터 합성으로 가능한 구현/검증을 순차 진행, 단계별 회귀·독립 읽기 전용 교차 검토 후 로컬 커밋. 실제 자료/수집/모델/외부 provider/main/push 금지. 실제 기기·역할·표본·수용 수치 미정 유지. 기존 v1 guard와 false flags 보존. 모든 편집/검사는 ./develop 안에서 직렬 실행. 함수7/호출전이4 제한. 시험 fixture 숫자는 제품 승인값이 아니다.

## S0 소유 파일·계약
- docs/collaboration/contracts/collection-runtime-v2-20261117.md
- card_condition/observation_collection_contract.py
- tests/test_observation_collection_contract.py
- 이 ledger
새 계약 exact schema/digest/null/readiness와 v1 확장 거부를 먼저 RED→GREEN. contract는 synthetic만 허용하고 실제 수집 readiness=false 고정. 새 leaf validator/일관된 digest만 추가, 기존 v1소스 수정 없음. 새 Python 최대4정의 목표, readiness→validate_collection_contract→validate_profile→exact_keys 최대3전이.

## 실행 ledger
- [x] S0 계약
- [x] S1 휴대폰 관측
- [x] S2 H 확대
- [x] S3 출처/수신
- [ ] S4 봉인/접근
- [ ] S5 실제 브라우저 합성 연결·최종 회귀
후속 단계 소유 파일/경로는 시작 전에 여기에 추가하고 커밋한다. ignored 산출물 artifacts/collection-runtime-synthetic-20261118/의 stage별 RED/GREEN/review/브라우저 원문·화면/report.html. 기존 artifacts 탐색/덮어쓰기 금지. HTML은 이번 실제 개발 결과로 갱신·열기와 렌더를 구분한다. 진척 두 정본은 유지하며 최종 보고 전 읽는다.

롤백은 단계 구현을 역순 revert. v1/원문/기존 근거/다른 worktree 보존. R1실기기/R2실권한은 미정·미확인이고 합성 통과로 실제 수집을 열지 않는다.

S0 완료: RED3실패→GREEN3통과, 기존31회귀통과. 독립 reviewer 중요 지적 없음(정적만), 함수3/테스트6·최대3전이. helper fixture는 다른 단계에서도 직접 import할 수 있게 자기 모듈 import를 포함한다. source/기준 gate unchanged.

## S1 소유 파일·선행 계약
새 card_condition/observation_viewport.js, card_condition/observation_collection_response.js, tests/observation_viewport.test.cjs, tests/test_observation_mobile.py. 수정 card_condition/observation_page.py, 위 wire 문서, 이ledger. display.js는v1그대로 보존. render_page(packet,assets,collection_contract=None)의 선택 경로만 후보 UI/스크립트 추가. viewport관측은 별도 candidate log, v1키 불변. exporter는 S1에 viewport후보를 조립하고 S2/S3에서 zoom/출처 연결. 새 JS최대5정의, page1정의 유지. render_page→verify_assets→validate_packet→validate_profile→exact_keys=4 유지.
Ruling: 모바일 대응은 승인수치 없는 자동 이미지축소가 아니라 고정 이미지 영역 스크롤/컨트롤 폭 제한으로 한다. v1 출력은 선택인자없을때 bytes동일. 후보 export는 기존export를 호출하고 base_response를 그대로 묶으며 추가로그는sidecar다.

S1 완료: 미구현 RED→mobile3 GREEN, 기존page/response/receipt/p2 19회귀통과. 실제Chrome에서후보export/메모/viewport sidecar와false flags 확인(s1.raw/s1.jpg). reviewer 중요잔여없음, viewport4/exporter1/page1정의. 최장 exportCollection→exportResponse→buildResponse→invalidate→observe=4. 실제휴대폰미검증.

## S2 소유 파일·계약
새 card_condition/observation_zoom.js, observation_zoom.py, tests/observation_zoom.test.cjs, tests/test_observation_zoom.py. 수정 observation_page.py, observation_collection_response.js, wire문서/ledger. v1display/response불변. H확대는원본baseimg를변환하지않는별도lens에서동일Blob을표시하여base CSS gate를완화하지않는다. lens ref/SHA/URL/decode/natural/transform을독립대조하고누적실패 latch. null범위는H컨트롤잠금, A컨트롤없음. 함수JS최대7/Python최대2. candidate exporter→finishZoom→recordZoom→snapshotZoom=3전이(더깊어지지않음).

S2 검토 보완: CSS/transform 일시 변조·복원과 scale_min2/max3·초기1 모순을 확인. CSS JS회귀1실패·범위 계약1실패로 재현. S2 소유에 observation_collection_contract.py/test_observation_collection_contract.py 추가. Ruling: 기준뷰의 항등 배율1을 명시 합성 구간에 포함하는 schema 정합 조건으로 제한하며 제품 확대 수치를 승인하지 않는다. style/width/height 감시와 자체 transform 기록의 동기 소비를 구현한다.

S2 완료: zoom4+contract3+mobile3/기존관련19통과. 검토P2두건회귀RED→GREEN, 재검토중요잔여없음. 실제Chrome H배율2/원이미지X1 로그·A컨트롤없음·자체transform정상·CSS오류복원후잠금확인. JS6/Python1정의, 주요최장exportCollection→finishZoom→invalidateZoom→invalidate→observe=4. src/style mutation과크기누적판정, 범위는1포함정합조건만추가.

## S3 소유 파일·수신 계약
새 card_condition/observation_source.py, observation_collection_response.py, observation_collection_receipt.py, tests/collection_runtime_fixture.py, tests/test_observation_source.py, tests/test_observation_collection_receipt.py. 수정 observation_page.py/observation_collection_response.js(합성출처주장dropdown),wire문서/ledger. 기존v1receipt/validator는수정하지않음.
Ruling: packet메타데이터를독립수신검사하려면 API에packet이필요하므로 capture_collection_receipt(packet,contract,raw_bytes,custody_context,assignment,ledger), load_collection_receipts(packet,contract,assignment,ledger)로정확서명고정. v1 validate_response와v2 sidecar검사는 capture/load에서나란히직접호출하여v1최장4전이를늘리지않는다. read helper는IO/hash검사만하고semantic검사는capture/load에서각각수행. 새파일함수최대7.

S3 완료: source2/receipt4 RED→GREEN, 누적47회귀통과. reviewer는저장된human source재해시재분류1건지적, 반례RED1→공통read의syntheticguard보완→GREEN/재검토잔여없음. 신규source1/response2/receipt5정의. v1base검사는load/capture직접호출최장4. 실제human소스거부/합성human주장비인증/별도context/bytes/partial/status재검사유지.

## S4 소유 파일·봉인 계약
새 card_condition/observation_seal.py, observation_access.py, tests/test_observation_seal.py, tests/test_observation_access.py. 수정 tests/collection_runtime_fixture.py(가짜권한fixture),wire문서/ledger. read helpers는S3의synthetic/hash검사재사용, v1모델release불변.
Ruling: S4 seal은검증한인수증/원문참조의불변보관봉인이고사람truthseal이아니다. S5의최상위에서S3 load_semantics를먼저검사한후seal을호출한다. sealAPI는ledger의해시·합성guard를직접재대조하고임의subset/partial을거부하며truth_status=unresolved_synthetic/false로고정. semantic→seal을래핑해호출깊이를늘리지않는다. 실제신원/파일접근인증은R2미구현이다.
seal_receipts(contract,receipt_refs,ledger,output), load_seal(contract,ledger,output,seal_id), seal_state(seal,output), transition_seal(seal,output,action,actor,policy,freeze_ref=None). access authorize(actor,action,state,policy), aggregate_projection(actor,state,policy,receipts). 새파일각최대4/2정의. 주요경로transition→seal_state→digest 또는transition→authorize→exact_keys 최대3, seal→read_collection_records→strict_json_loads 최대4이내.

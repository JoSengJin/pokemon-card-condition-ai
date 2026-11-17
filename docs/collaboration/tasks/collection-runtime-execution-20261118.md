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
- [ ] S1 휴대폰 관측
- [ ] S2 H 확대
- [ ] S3 출처/수신
- [ ] S4 봉인/접근
- [ ] S5 실제 브라우저 합성 연결·최종 회귀
후속 단계 소유 파일/경로는 시작 전에 여기에 추가하고 커밋한다. ignored 산출물 artifacts/collection-runtime-synthetic-20261118/의 stage별 RED/GREEN/review/브라우저 원문·화면/report.html. 기존 artifacts 탐색/덮어쓰기 금지. HTML은 이번 실제 개발 결과로 갱신·열기와 렌더를 구분한다. 진척 두 정본은 유지하며 최종 보고 전 읽는다.

롤백은 단계 구현을 역순 revert. v1/원문/기존 근거/다른 worktree 보존. R1실기기/R2실권한은 미정·미확인이고 합성 통과로 실제 수집을 열지 않는다.

S0 완료: RED3실패→GREEN3통과, 기존31회귀통과. 독립 reviewer 중요 지적 없음(정적만), 함수3/테스트6·최대3전이. helper fixture는 다른 단계에서도 직접 import할 수 있게 자기 모듈 import를 포함한다. source/기준 gate unchanged.

## S1 소유 파일·선행 계약
새 card_condition/observation_viewport.js, card_condition/observation_collection_response.js, tests/observation_viewport.test.cjs, tests/test_observation_mobile.py. 수정 card_condition/observation_page.py, 위 wire 문서, 이ledger. display.js는v1그대로 보존. render_page(packet,assets,collection_contract=None)의 선택 경로만 후보 UI/스크립트 추가. viewport관측은 별도 candidate log, v1키 불변. exporter는 S1에 viewport후보를 조립하고 S2/S3에서 zoom/출처 연결. 새 JS최대5정의, page1정의 유지. render_page→verify_assets→validate_packet→validate_profile→exact_keys=4 유지.
Ruling: 모바일 대응은 승인수치 없는 자동 이미지축소가 아니라 고정 이미지 영역 스크롤/컨트롤 폭 제한으로 한다. v1 출력은 선택인자없을때 bytes동일. 후보 export는 기존export를 호출하고 base_response를 그대로 묶으며 추가로그는sidecar다.

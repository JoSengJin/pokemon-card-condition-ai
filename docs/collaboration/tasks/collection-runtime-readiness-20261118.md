# R1/R2 준비용 합성 증거·접근 계약 보완 task
task_id: collection-runtime-readiness-20261118
owner: Claude
status: implementing
base_sha: 773bdf39bfc1da3ccea99ac4f6e6862390910b17
branch: codex/collection-runtime-synthetic-20261118
goal: R1 실기기 증거와 R2 실제 접근 검증이 없으면 완료로 표시되지 않음을 합성 기록·검사로 고정한다. 실제 환경·수집·모델은 건드리지 않는다.

## 기존 지원 대조 (S0~S5 재사용, 중복 구현 금지)
|항목|판정|근거|
|---|---|---|
|A 원문 bytes/SHA 보존·한글/공백/줄바꿈|기존 구현 있음|S3 receipt raw.bin/SHA, S5 브라우저 원문 대조. 새 검사는 순수 bytes↔SHA 비교 leaf만 추가|
|A H 확대 앱 로그|기존 구현 있음|S2 zoom 로그. 브라우저/OS 확대 관측은 없음|
|A 시나리오별 증거 유형 분리·R1 완료 차단|최소 보완 필요|증거 유형(합성/데스크톱/실기기) 기록·집계 없음|
|A 실제 휴대폰 관측|실제 환경 의존|기종·OS·브라우저 미정|
|B 논리 역할 정책·집계 비역연결|기존 구현 있음|observation_access.py, actual_access_verified=false|
|B 채널(파일/도구/대화/메모리/회신)·자동화·겸직·개발측 수신 제한 계약|최소 보완 필요|채널·자동화 역할 표현 없음|
|B 실제 OS/파일/도구 통제|실제 환경 의존|집행 수단 미정|
|C sentinel 시나리오·결과 기록|최소 보완 필요|없음|
|C 실제 실행 신원 sentinel 시험|실제 환경 의존|환경 미정|
|D 증거 로그 헤더|최소 보완 필요|R1/sentinel 기록에 공통 헤더만 추가|

## 소유 파일 (모두 신규)
card_condition/observation_evidence.py, card_condition/observation_roles.py, tests/test_observation_evidence.py, tests/test_observation_roles.py, 이 task 문서.
금지: 기존 소스·테스트·pyproject·진척 정본·artifacts 기존 경로·실자료.

## 계약
- 새 코드는 어떤 입력으로도 r1_complete/actual_access_verified/collection_ready/human_truth/eligible_for_collection를 True로 반환하지 않는다. 최고 상태는 `evidence_ready_for_review`로 사람/메인 검토 대기이며 완료 선언이 아니다.
- 미정 값(기종·OS·브라우저·확대 범위·담당 ID·집행 수단·표본·수치)은 null로 둔다. 새 수치·허용 오차·필수 개수를 만들지 않는다.
- 모든 기록 data_origin=synthetic_fixture. 다른 값·human 출처 주장은 거부.
- 모의(mock) 결과는 실제 권한 검증으로 승격하지 않는다. 같은 OS 사용자 권한의 프로그램 거부도 승격하지 않는다.
- sentinel 표식은 `SYNTH-SENTINEL-` 접두 합성 문자열만 허용.
- 외부 에이전트·OS 권한·provider·실제 자료 미사용.

## 구조 (변경 전→후 함수 수, 한도 7 / 호출 전이 한도 4)
observation_evidence.py 0→5, observation_roles.py 0→5. 기존 파일 변경 없음.
경로: r1_status→readiness→validate_collection_contract→validate_profile→exact_keys=4. sentinel_status→sentinel_verdict→validate_sentinel_record→check_header→exact_keys=4.

## checks
`.venv/bin/python -m unittest discover -s tests -p test_observation_evidence.py -v`, `test_observation_roles.py` 각각. 관련 회귀: test_observation_access.py, test_observation_collection_contract.py (영향 확인용, 새 성과로 세지 않음). 모델 실험 아님 → ./experiment 없음.
HTML: artifacts/collection-runtime-readiness-20261118/report.html (ignored, 합성 결과·미완료 표시).

롤백: 이 task의 커밋 revert (신규 파일만이라 기존 동작 영향 없음).

## 결과 (2026-11-18)
status: ready_for_review
구현: card_condition/observation_evidence.py(5정의), observation_roles.py(5정의), tests/readiness_fixture.py(5), test_observation_evidence.py(7)/test_observation_roles.py(3)/test_observation_sentinel.py(5) — 모두 신규, 기존 소스·pyproject·진척 정본 미변경. 테스트는 구현과 함께 작성해 RED 단계 없이 GREEN으로 처음 실행했고, 첫 실행 1건(원문 공백 fixture 결함)은 테스트 데이터만 수정했다. 정의 수 한도 초과(테스트 9/17)는 fixture 분리·파일 분할로 해소했다.
호출 경로 최장 4(r1_status→readiness→validate_collection_contract→validate_profile→exact_keys, sentinel_status→sentinel_verdict→validate_sentinel_record→check_header→exact_keys).
고유 검사 14개 통과(evidence6/roles3/sentinel5). 영향 확인 기존 회귀 access2·collection_contract3 통과(새 성과 아님). 전체 suite·실제 Chrome·휴대폰·모델 미실행.
반례 검증: 실기기 증거 없음→blocked, 모의 권한만→blocked, 필수 관측 null 보충 없음, 앱 확대 로그→외부 확대 승격 거부, 금지 접근 성공/표식 회신→failed, 증거 없음→unverified(통과와 구분), 원문 strip/재직렬화/1바이트 변경→불일치, real/human 입력 synthetic 재분류 거부, 같은 OS 사용자 거부→unverified, 겸직→independent=False.
최상위 상태는 evidence_ready_for_review이며 r1_complete/actual_access_verified/collection_ready는 코드상 항상 False.
HTML: artifacts/collection-runtime-readiness-20261118/report.html(ignored). macOS open 요청 성공, 화면 렌더는 도구 제약으로 미확인.
미정·실제 의존: 기종/OS/브라우저, H 확대 정책, 사람 배정, 담당 ID·집행 수단, eBay 모집, 표본/수치 — 전부 미정 유지.

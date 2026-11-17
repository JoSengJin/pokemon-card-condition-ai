# 비노출 packet 최소 구현 — 합성 자료 전용

task_id: blind-observation-packet-20261117
owner: Codex
status: implementing
base_sha: c9dbf5556c8e557eb91e573e10c338cc096e56a0
branch: codex/stable-low-reference-cause-design-20261116

## 목표·권한
사용자의 2026-11-17 승인에 따라 packet만 구현하고 합성 단위 검사까지만 한다. 기존 최소 구현 계약은 전체 경로의 설계 기록으로 보존하며 page/receipt/수집 구현은 승인 범위에 포함하지 않는다. 실제 사진·라벨 접근/사용·수집·모델 검증·학습·추론·main 통합·push 금지. 기존 기록·.claude/·D-LOC·다른 worktree 보존.

## 소유 파일
- card_condition/observation_packet.py
- tests/test_observation_packet.py
- docs/collaboration/tasks/blind-observation-packet-20261117.md
- docs/collaboration/reports/blind-observation-packet-20261117.md

나머지 tracked 파일은 변경 금지. Git 제외 .venv는 외부 패키지 없이 자체 생성한다. Git 제외 artifacts/observation-packet-implementation-20261117/{red.log,green.log,report.html}에 합성 검사/보고 근거를 남긴다.

## 계약·계획
1. 합성 dict/UTF-8 JSON bytes만 처리하는 순수 packet API. 파일 읽기·화면·수집·기존 진단 import·모델 연결 없음.
2. 허용 키 정확 일치. 점수·기존 라벨·모델 후보 등 임의 metadata를 거부한다. completed=true는 거부하고 false만 공개 projection에서 제외한다. entry/photo/asset ID는 익명 형식, 경로는 assets/익명ID.확장자만 허용한다.
3. profile의 미정 표시값은 null로 유지한다. synthetic_fixture 선언만 허용하며 출력 collection_status는 not_executable_pending_collection_contract_approval로 고정한다. 이 선언은 실제 출처/독립성 증명이 아니다.
4. 구역 전체 scope, H/A와 profile 일치, 원사진/표시 자산 SHA 형식, 크기·정규화/픽셀 좌표·중복 정체성·지시문 SHA·공개 packet SHA를 검사한다. 실제 표시 자산 바이트 검사는 renderer 후속 범위다.
5. 중첩/배열 내부를 포함한 JSON 중복 키는 동일 값도 거부한다. 원문 bytes는 변경하지 않는다. 거부 원문·해시·이유의 영속 저장은 receipt 후속 범위이며 이번에 완료했다고 보고하지 않는다.
6. 지시문/버전 문자열의 의미·이미지 내용·선정 독립성까지 schema로 증명하지 않는다. 원본 데이터와 연결된 후보/라벨 판정은 읽지 않는다.

## 구조
observation_packet.py 0→최대7함수, tests/test_observation_packet.py 0→최대7메서드/함수. build_packet→validate_packet→validate_profile/packet_digest 최대2 프로젝트 전이, strict_json_loads→unique_object_pairs는 json callback을 통한1프로젝트 전이(라이브러리 내부 제외). 순환 호출 없음.

## 검사
TDD: 합성 테스트 작성→기능 부재 실패 확인→최소 구현→같은 단위 검사 통과. python -m unittest discover -s tests -p test_observation_packet.py -v만 실행한다. 전체 suite는 실제 자료/모델 경로가 포함될 수 있어 이번 승인에서 제외한다. ./develop 잠금 안에서 코드/테스트 수정 및 합성 검사. diff 공백·함수 수·호출 경로 정적 확인. HTML은 합성 결과/미실행/리스크/롤백/진척78/100 유지로 생성하고 로컬 열기 요청과 렌더 확인 여부를 분리한다.

experiment: 없음. 모델 성능·독립 평가·일반화 개선 근거 없음. 표본 수·기기·출처·판정 조건 등의 미정 값은 확정하지 않는다.

## handoff
구현 후 실제 결과·미검증·리스크·롤백을 보고서에 기록한다. 로컬 커밋만 수행하고 main/push는 하지 않는다. 구현 철회는 구현 커밋만 git revert하며 원본 기록·환경·다른 worktree를 복원/삭제하지 않는다.

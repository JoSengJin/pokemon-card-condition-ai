# 비노출 판정 packet — 합성 단위 검사 구현 결과

개발 진척: **78/100 유지** (`usable-card-analysis-v1.13`). 이번 성과는 합성 metadata packet의 생성/거부 경계 구현이며 모델 품질·독립 평가·일반화 개선은 확인하지 않았다.

- 상태: `synthetic_packet_implemented_collection_not_executable`.
- 실제 수집: `not_executable_pending_collection_contract_approval` 유지.
- 작업 기준: `c9dbf5556c8e557eb91e573e10c338cc096e56a0`.
- 검사 당시 HEAD: 계약 커밋 `0e834e71d2b024b458c73edc18ec7e17f97a053e`, 아래 코드/테스트는 미커밋 신규 파일. 최종 로컬 커밋은 이 보고서의 Git 이력과 세션 인계로 확인한다.

## 변경 파일·핵심 diff

|파일|변경|
|---|---|
|[observation_packet.py](../../../card_condition/observation_packet.py)|순수 Python packet 생성·schema/표시 profile/정체성/좌표/SHA 검사와 strict JSON 파서. 기존 호출자·모델·worker·CLI·화면 연결 없음.|
|[test_observation_packet.py](../../../tests/test_observation_packet.py)|합성 상수만 사용한 unittest 6개(준비 메서드 포함7정의).|
|[작업 계약](../tasks/blind-observation-packet-20261117.md)|허용 파일·TDD·합성 한정·구조·실행 불가 상태·인계.|
|이 보고서|실행 근거·범위·리스크·롤백 기록.|

## 구현한 경계

- root/entry/profile/asset의 키 집합을 정확 대조한다. score/target/region_target/previous_label/rank/candidate_token/candidate_box/heatmap/임의 metadata를 제거해 통과시키지 않고 거부한다. 허용 필드 내부의 형식도 검사하며 임의 JSON 컨테이너를 통과시키지 않는다.
- 구역 전체 scope, H/A 일치, A 확대 금지, 익명 ID·자산 상대 경로, source/asset 크기, 유한 정규화 좌표와 floor/ceil 픽셀 좌표 일치, 중복 entry ID·photo/asset 정체성 충돌을 거부한다. 완료 상태는 정확히 false만 받고 공개 packet에서 제외한다.
- 공개 내용만 canonical JSON SHA로 결합한다. 표시 지시문은 원문 그대로 보존하고 별도 UTF-8 SHA로 결합한다. 입력은 변경하지 않으며 출력의 중첩 자료를 복사한다.
- raw UTF-8 bytes를 strict_json_loads로 읽으면 object_pairs_hook이 중첩/배열 안 객체·동일 값 반복·Unicode escape로 같은 키가 된 경우도 거부한다. 비유한 JSON 숫자도 거부한다. 일반 json.loads로 이미 dict가 된 입력의 중복 키를 사후 복원할 수 없으므로 JSON 경계에서는 반드시 strict parser가 선행해야 한다.
- data_origin/approval_status는 synthetic_fixture 선언만 허용하며 collection_status는 실행 불가 상수다. profile의 미정 표시값 null은 그대로 남고 승인으로 승격되지 않는다. 이 표시는 실제 합성 출처를 판별하는 기능이나 수집 승인 절차의 대체물이 아니다.

## 실제 검사와 미실행

명령: `./develop -- env PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p test_observation_packet.py -v` (동일 unittest 명령을 잠금 내부 subprocess에서 실행하고 stdout/stderr를 저장).

- RED: 코드 작성 전6개 모두 기능 부재 assertion 실패, exit1. `artifacts/observation-packet-implementation-20261117/red.log`.
- GREEN: 구현 후6개 통과, exit0. `artifacts/observation-packet-implementation-20261117/green.log`.
- 소스7정의, 테스트7정의. AST 집계와 읽기 전용 교차 검토에서 확인. 최대 프로젝트 전이 `build_packet → validate_packet → validate_profile → exact_keys`는3회. strict_json_loads의 json callback은 unique_object_pairs 한 경로이며 순환 프로젝트 호출 없음. 표준 라이브러리 내부 호출은 별도 제외.
- Superpowers TDD 및 requesting-code-review 적용. 검토자는 읽기만 수행했으며 중요한 구현 결함은 발견하지 않았다. task의 호출 전이2→3 표기 정정 반영.
- 패키지 설치 없이 독립 .venv(Python3.9.6, 표준 라이브러리) 사용. 실제 사진/라벨·보호 자료를 읽지 않았다.
- 전체 suite/모델 검증/학습/추론/사람 판정 요청/실제 수집/외부 provider 호출/main 통합/push는 미실행. 기존 suite에는 실제 자료/모델 경로가 있어 이번 승인 범위에서 실행하지 않았다.

## 미구현·리스크·남은 의존

- packet만 구현했다. page·renderer·표시 바이트/packet SHA 대조·관찰조건 receipt·4상태 응답·원문/해시/거부 이유 영속 저장은 후속 범위다. strict parser는 전달받은 원문 bytes를 변경하지 않고 ValueError를 발생시키지만 거부 원문을 자체 저장하지 않는다. 기존 전체 최소 구현 계약 완료를 뜻하지 않는다.
- 지시문/버전/변환 문자열은 보관자가 제공하는 합성 metadata다. 키 검사로 자유문장의 의미·이미지 속 모델 표시·점수 기반 선정·사람의 실제 비노출/관찰·독립성을 증명하지 않는다. SHA는 선언된 내용의 결합이며 실제 이미지 파일이나 표시 바이트를 확인하지 않았다.
- 같은 사진·구역·자산을 다른 entry_id로 반복하는 경우의 의미적 중복 배제는 현재 구현하지 않았다. 익명 명부의 실제 선정/중복 배제는 후속 보관자 경계에서 별도 확정·검사해야 한다. entry ID 중복 및 같은 ID의 정체성 충돌 거부와 혼동하지 않는다.
- 실제 수집의 기기·사진 출처·사람 판정 출처/비노출 절차·접근 통제·표본 수·수용 수치 등 미정은 그대로다. 별도 인력/비용 확보를 필수로 추가하지 않고 AI를 사람 정답으로 대체하지 않는다. packet 합성 검사 통과만으로 수집 실행 불가 사유는 해소되지 않는다.
- 기존 파일/호출 경로 변경이 없어 기존 동작을 연결해 바꾸지 않았다. 전체 suite·실제 자료 호환성·배포 연결은 미확인이다.

## 검증 소스 SHA-256

- `card_condition/observation_packet.py`: `48846cf61c3fa3692e3b12fcc9664c97e3740c87192a748c4f73dc86ffc6dcc8`
- `tests/test_observation_packet.py`: `9be72f403017df86bb6f68b50cebb6ff3b748a3be5073cc328338c49d8509893`

## HTML·인계·롤백

HTML: `artifacts/observation-packet-implementation-20261117/report.html`. 합성 결과만 포함하며 CDN/API/사진/외부 script 없음. 진척 근거는 PROGRESS_CRITERIA.md와 development-progress.json이며 기준/점수 파일은 변경하지 않았다.

롤백: 이번 구현 결과 커밋만 git revert한다. 계약 커밋까지 철회하려면 결과 커밋 다음 계약 커밋0e834e7 순으로 별도 승인하에 revert한다. 원본 기록·.claude/·D-LOC·다른 worktree·과거 계약은 삭제/복원하지 않는다. 이번에는 롤백·main 통합·push를 실행하지 않는다.

HTML 확인: 로컬 open 열기 요청 성공(exit0), 실제 렌더는 미확인.

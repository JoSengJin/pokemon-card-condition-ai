# 합성 표시 자산 바이트 대조기 구현 계약

task_id: synthetic-observation-assets-20261117
owner: Codex
status: implementing
base_sha: 3eb813a3f24284f13ee4eb55b0fed798787007d5
branch: codex/synthetic-observation-assets-20261117

## 목표·승인 범위
사용자가 승인한 다음 최소 작업 하나: 기존 packet 검사 재사용 후, 합성 표시 이미지 bytes의 SHA·크기·해독·자산 집합을 검사하고 검증한 동일 bytes를 반환한다. 독립 worktree에서 코드/합성 단위 검사와 로컬 커밋까지만 수행한다. 실제 자료 사용·수집·모델 검증·학습·추론·main 통합·push 금지. 기존 원본 기록·.claude/·D-LOC·다른 worktree 보존.

## 소유 파일
- card_condition/observation_assets.py
- tests/test_observation_assets.py
- docs/collaboration/tasks/synthetic-observation-assets-20261117.md
- docs/collaboration/reports/synthetic-observation-assets-20261117.md

기존 packet 소스/테스트·기준·라벨·원본·다른 문서는 수정하지 않는다. ignored 산출물: artifacts/synthetic-observation-assets-20261117/{baseline.log,red.log,green.log,report.html,execution.json}. 자체 .venv에 requirements-tested.txt의 Pillow12.3.0만 설치하며 다른 환경의 site-packages나 artifacts를 공유하지 않는다.

## API·재사용·구현 선택
새 API `verify_assets(packet, assets) -> dict[str, bytes]`. 입력 packet은 기존 dict 형식이고 assets는 공개 ref→정확한 불변 bytes의 dict다. JSON bytes는 호출자가 기존 strict_json_loads로 읽고 넘겨야 하며 이 API에서 임의 JSON/파일을 읽지 않는다.

1. 기존 validate_packet을 먼저 호출한다. 금지 metadata·packet SHA·synthetic_fixture·실행 불가 상수·H/A·정체성 검사를 그대로 재사용한다.
2. packet에서 기대 ref와 자산 metadata를 모으고 입력 dict의 ref 집합과 정확 대조한다. 공유 context ref는 하나로 취급한다. 누락·추가 자산은 거부하며 경로/URL 접근을 수행하지 않는다.
3. 값은 type(value) is bytes만 허용한다. SHA-256을 자산 sha256과 대조한다. 원사진 photo_sha256과 표시 자산 sha256은 다른 역할이며 혼용하지 않는다.
4. BytesIO와 기존 Pillow로 PNG/JPEG를 검사한다. verify로 구조를 검사한 뒤 같은 bytes에서 다시 열어 load로 실제 해독하고 size를 대조한다. 실제 파일을 다시 읽거나 bytes를 재인코딩/교체하지 않는다. ref의 png/jpg/jpeg와 실제 형식도 일치해야 한다. 이미지 해독 실패는 ValueError로 거부하고 Pillow의 전역 허용/제한 설정을 완화하지 않는다.
5. 모든 자산 통과 후 새 dict에 검증한 동일 bytes 객체만 담아 반환한다. 부분 성공 반환·입력 변경·수집 상태 변경 없음. 합성 출처 선언은 provenance의 증명이 아니며 실제 사람에게 표시됐다는 의미가 아니다.
6. page/브라우저 표시·이미지 생성/보정·4상태 응답·receipt/원문 영속 저장·데이터 선정·실제 수집은 구현하지 않는다. 표본 수·기기·출처·관찰조건의 미정 수치는 유지한다.

## 구조
새 소스 최대2함수, 테스트 전체 최대7정의. 예상 최장 프로젝트 경로 verify_assets→validate_packet→validate_profile→exact_keys 3전이(라이브러리 내부 제외). 새 decoder helper를 쓰면 verify_assets→helper 1전이. 기존 packet 파일은7정의 그대로 보존한다.

## Superpowers 실행 계획·합성 판정 기준
이번 요청의 구현 방식은 직접 TDD 한 작업과 마지막 독립 읽기 전용 리뷰다. 작업 계획·ledger는 이 task에 통합한다(저장소 계약 우선).
- [ ] 기존 packet 합성6개 baseline 통과를 저장한다.
- [ ] 새 합성 unittest를 먼저 작성하고 미구현 실패(RED)를 확인한다.
- [ ] 최소 verifier 구현 후 새 검사와 기존 packet 검사를 함께 통과시킨다(GREEN).
- [ ] 중요한 입력: 올바른 PNG/JPEG의 동일 bytes 반환/불변성, SHA 불일치·1바이트 변조·mutable/비bytes, SHA 일치 손상/잘린 이미지, 크기 불일치, 누락·추가 자산, 잘못된 packet·금지 metadata·실행 상태 변경 거부, 공유 자산과 형식/확장자 불일치.
- [ ] 구조·diff 공백·허용4파일·검토·SHA를 확인하고 보고서/HTML 생성·로컬 열기 후 로컬 커밋한다.

검사는 ./develop 잠금 안에서 `python -m unittest discover -s tests -p 'test_observation_[pa]*.py' -v`만 실행한다(기존 packet과 새 assets 파일). 전체 suite는 실제 자료/모델 경로를 실행할 수 있으므로 실행하지 않는다. 모델 성능 실험이 아니며 experiment 실행은 없다. 진척은 고정 기준78/100 유지.

## ledger·handoff
- 초기 판단: 사용자 승인 명세가 구체적이므로 추가 선택 질문 없이 위 범위를 실행한다. 기존 표시 자산 확장자 PNG/JPEG를 따르며 새 형식을 추가하지 않는다.
- 검사 결과·검증 소스 SHA·리스크·미검증·로컬 커밋은 결과 보고서 및 Git 이력에 기록한다. HTML 열기 요청 성공과 렌더 확인은 구분한다.
- 롤백: 결과 구현 커밋만 git revert. 계약까지 철회하면 역순 revert. 원본·다른 worktree 삭제/복원 금지. 이번에는 롤백·main 통합·push를 수행하지 않는다.

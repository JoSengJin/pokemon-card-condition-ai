# 合성 관찰 루프 P2 세 경계 보완 계약

task_id: synthetic-observation-p2-20261117
owner: Codex
status: implementing
base_sha: cf53d5ea314a34a6d702a449ac0d20effd9ed1d9
branch: codex/synthetic-observation-p2-20261117

## 목표·권한
사용자가 승인한 P2 세 건만 TDD 합성 회귀로 보완한다. 현재 격리 worktree에서 후속 전용 브랜치를 분리하며 이전 브랜치/커밋을 보존한다. 실제 자료 사용·사람 판정 수집/재요청·모델 검증·학습·추론·main 통합·push 금지. 기존 원본·.claude/·D-LOC·다른 worktree 보존. 결과는 로컬 커밋까지만 한다.

## 소유 파일
- card_condition/observation_display.js
- card_condition/observation_response.py
- card_condition/observation_receipt.py
- card_condition/observation_receipt_status.py
- tests/test_observation_p2.py
- tests/observation_profile.test.cjs
- docs/collaboration/tasks/synthetic-observation-p2-20261117.md
- docs/collaboration/reports/synthetic-observation-p2-20261117.md

나머지 tracked 파일 변경 금지. ignored 산출물은 artifacts/synthetic-observation-p2-20261117/ 아래 red.log/green.log/review-red.log/final-green.log/execution.json/report.html. 기존 합성 fixture와 Node DOM stub을 재사용하고 새 의존성을 설치하지 않는다.

## 수정 계약·계획
- [ ] P2-1: viewport_css/device_pixel_ratio/image_css 중 null이 아닌 profile만 관측값과 정확히 대조한다. null은 미정으로 유지한다. JS 초기/응답/내보내기 gate 및 환경 변경, Python 자기 보고 검사에서 불일치를 보류한다. 허용 오차·기기/표본 수·정책 수치를 새로 정하지 않는다.
- [ ] P2-2: change 시점에 해당 구역의 문맥/구역 자산 연결·natural size·CSS 양수/명시 크기를 확인하고 잘못된 관측은 나중 export가 정상이어도 회복시키지 않는다. raw 응답/메모와 미확인/판단 불가를 변경하지 않는다.
- [ ] P2-3: receipt 생성과 재읽기/멱등 경로가 출처·관측 요약·conflicts로 결정하는 status/reasons 규칙을 공유한다. AI/unknown 출처를 synthetic_only로 재분류하거나 사유를 누락한 manifest는 checksum을 다시 계산해도 거부한다. 기존 raw/SHA/원문 보존·실행 불가/사람 정답 대체 금지·충돌 원답 보존은 유지한다.
- [ ] 세 허점을 재현하는 합성 RED 확인→최소 구현→기존26+새 회귀 검사→독립 읽기 전용 교차 검토·중요 보완→최종 로컬 커밋. task/보고서와 로컬 정적 HTML에 실제 결과/미확인/리스크/롤백 기록.

## 구조·검사
기존 receipt 파일은7정의 한도이므로 순수 status/reasons 분류 규칙만 새 observation_receipt_status.py로 분리한다. 기존 public API는 유지한다. 파일당 최대7정의와 프로젝트 최대4전이를 유지한다. capture/load→validate_response→validate_observations→validate_event→exact_keys=4. 새 event 비교 helper는 구조 검사를 중첩 호출하지 않는 leaf다. 새 status 분류도 leaf이며 read_records/capture에서 직접 호출한다.

검사 파일은 test_observation_packet.py, test_observation_assets.py, test_observation_page.py, test_observation_response.py, test_observation_receipt.py, test_observation_p2.py를 각각 정확한 이름으로 지정한다. wildcard/전체 suite/모델 의존성 설치 금지. 모든 수정/합성 검사는 ./develop 잠금 안에서 수행한다. Node는 실제 crypto/Blob과 기존 DOM/decode stub이며 실제 브라우저/기기 검증을 뜻하지 않는다.

## 유지·한계·롤백
not_executable_pending_collection_contract_approval, synthetic_fixture, human_truth=false, eligible_for_collection=false를 유지한다. 기기·사진 출처·인력/비용·표본 수·관찰 절차/독립성·수용 수치 미정은 그대로다. 진척78/100 유지, 모델 누락/오탐 개선은 미평가다.

새 status 규칙은 기존 context/요약/선언된 conflicts의 내부 정합성 검사이며 사람 인증·악의적 전체 재작성 방지나 새 이력/정답 선택 정책이 아니다. 합성 검사 통과를 실제 수집 승인으로 해석하지 않는다. 실제 수집 실행 불가 사유는 해소되지 않는다.

롤백은 이번 결과 구현 커밋만 git revert하며 계약까지 철회하면 역순 revert한다. 기존 cf53d5e 이전 루프·bytes 대조기·다른 worktree를 삭제/복원하지 않는다. 실제 롤백은 이번 요청에 포함되지 않는다.

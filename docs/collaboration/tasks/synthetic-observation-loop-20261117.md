# 합성 표시→4상태→관찰조건/원답 저장 루프

task_id: synthetic-observation-loop-20261117
owner: Codex
status: ready_for_review
base_sha: be453f7c4f056d902458531e62b7210fe1b33a17
branch: codex/synthetic-observation-loop-20261117

## 목표·권한·설계
사용자의 명시 승인에 따라 현재 격리 worktree에서 새 전용 브랜치를 사용한다. 표시 연결·4상태 응답·관찰조건/원답 저장을 단계별 TDD→합성 검사→독립 읽기 전용 검토→보완→로컬 커밋으로 이어간다. 실제 자료/사람 판정 수집·모델 검증·학습·추론·main 통합·push 금지. 기존 원본·.claude/·D-LOC·다른 worktree 보존.

기존 observation_packet/assets API는 그대로 재사용한다. 렌더러는 검증된 bytes를 HTML에 내장하고 브라우저가 그 bytes의 SHA를 대조해 Blob URL에 연결·decode 완료한 뒤 입력을 연다. ref 변경/제거 시 무효화하며 매 응답 변경/내보내기 때 연결을 재확인한다. 네트워크·원본 경로·모델/기존 답 payload를 넣지 않는다. H/A는 별도 profile에 결합하며 A에는 확대 조작을 넣지 않는다. 미정 profile은 승인으로 바꾸지 않는다.

4상태는 unreviewed/normal/defect/unassessable. 일괄 정상·미확인 정상 보충·원문 메모 trim 없음. 내보내기는 명시적 동작이며 관측 이벤트/표시 자산 기대·실측 SHA/버전/시각·viewport/DPR/표시 크기/visibility/visualViewport 관측을 결합한다. 실제 기기/주의/외부 정보 비열람을 브라우저 관측으로 입증하지 않는다.

수신은 strict_json_loads로 중첩 중복 키를 거부한다. 구역/사진/packet/profile 연결과 4상태·관측 구조를 독립 검사한다. 누락 항목과 unreviewed를 구분하며 어느 쪽도 정상으로 만들지 않는다. receipt는 raw.bin 원문과 raw SHA·수신 문맥·거부/충돌 이유를 생성 전용 저장한다. raw를 재직렬화해 대체하지 않는다. 동일 수신만 멱등, 별개 session/출처는 분리하고 상충 답의 정답을 고르지 않는다. 부분 저장은 완료로 로드하지 않는다. AI/미확인 출처는 사람 정답이 아니며 실제 human 출처 입력은 이번 합성 전용 API에서 허용하지 않는다.

모든 packet/response/receipt는 synthetic_fixture 및 not_executable_pending_collection_contract_approval를 유지하고 receipt의 human_truth/eligible_for_collection은 항상 false다. 서버 시각과 브라우저 자기 보고 시각을 분리한다. 미정 기기·출처·표본 수·수치·실제 관찰/접근 통제는 그대로 유지한다.

## 소유 파일(정확 목록)
- card_condition/observation_page.py
- card_condition/observation_display.js
- card_condition/observation_response.js
- card_condition/observation_response.py
- card_condition/observation_receipt.py
- pyproject.toml (새 JS 자산 package-data만)
- tests/observation_loop_fixture.py
- tests/observation_browser_fixture.cjs
- tests/observation_display.test.cjs
- tests/observation_response.test.cjs
- tests/test_observation_page.py
- tests/test_observation_response.py
- tests/test_observation_receipt.py
- docs/collaboration/tasks/synthetic-observation-loop-20261117.md
- docs/collaboration/reports/synthetic-observation-loop-20261117.md

ignored 산출물: artifacts/synthetic-observation-loop-20261117/ 아래 단계별 red/green/검토/실행 기록·합성 fixture·최종 report.html. Python tempfile의 합성 receipt만 추가 사용한다. 다른 tracked 파일/실제 자료/기준 파일 변경 금지.

## 구조·검사 계약
각 소스/테스트/fixture 파일은 메서드·중첩/익명 함수까지7정의 이하. 라이브러리 내부를 제외한 프로젝트 호출 최대4전이. page→verify_assets→validate_packet→validate_profile→exact_keys=4. capture_receipt→validate_response→validate_packet→validate_profile→exact_keys=4. 새 wrapper로 이를 초과하지 않는다. 동적 JS 이벤트→핸들러 경로는 별도 검토한다.

기존 packet/assets 두 합성 검사 파일과 새 파일을 각각 정확한 이름으로 실행한다. wildcard discovery·전체 suite·모델 의존성 설치 금지. Node는 기본 vm/assert/crypto/Blob 및 DOM stub을 사용하며 실제 브라우저·기기 검증으로 보고하지 않는다. 실제 사진/완료 라벨/기존104·303은 fixture로 쓰지 않는다.

## 실행 계획·ledger
- [x] 1 표시: Python renderer/검증한 동일 bytes 내장·JS SHA/Blob/decode gate·관측/무효화. Python/Node 합성 RED→GREEN, 검토·보완 후 커밋.
- [x] 2 응답: 명시적4상태/원문 메모/관측+내보내기·독립 Python validator. 합성 전이·변조·미확인/누락·비노출 검사, 검토·보완 후 커밋.
- [x] 3 저장: raw/SHA/수신 문맥/거부·충돌/멱등/부분 저장·무결성. JS 내보내기→Python receipt 연결 합성 검사, 검토·보완 후 커밋.
- [x] 최종: 기존12검사와 새 정확 파일 검사, 정의/호출/소유 범위·diff·소스 SHA 대조. 진척78/100 유지 보고서/로컬 HTML 생성·열기(렌더 확인 구분). 로컬 커밋 후 종료.

Ruling: 사용자가 방금 위 설계 범위의 루프 실행을 명시 승인했으므로 재승인 질문 없이 직접 구현하고 단계별 reviewer를 호출한다. 계획/설계/실행 ledger는 저장소 task 계약에 통합한다. 메모리 합성 bytes만 사용하며 페이지 작성은 문자열 반환 API다. 실제 수집 연결·HTTP 서버·제품/학습 export는 추가하지 않는다.

## 리스크·롤백
브라우저 로그는 자기 보고이고 DOM stub은 실제 표시/기기·사람 비노출 증명이 아니다. 원문 저장은 라벨 채택이 아니다. 실제 수집 실행 불가 사유는 해소되지 않는다. 결과 커밋을 역순 revert하고 기존 bytes 대조기까지 되돌리지 않는다. 다른 worktree/원본 자료는 삭제·복원하지 않는다. 실제 롤백은 이번 요청에 포함되지 않는다.

- 1段 검토: 초기 비동기 제거/재삽입·data-ref 변경2건을 회귀 RED2실패로 재현했다. 초기부터 observer를 설치하고 정상 내부 src 기록만 구별해 소비하며 무효화 latch를 유지한다. binding의 ref와 proof 상태/기대 집합을 검사한다. reviewer 지적과 Node 회귀를 근거로 보완한다.

- 2단계 검토: invalidate 이력·최종 상태/마지막 change 모순을3case RED로 재현했고 display_verified=false로 보류하여 원답을 유지한다. 타입 회귀에서는 profile의 True/1 동치와 nonhashable entry_id도 거부했다.stage1 commit51e2a60。

- 3단계 검토: lone surrogate 원답의 manifest UTF-8 재인코딩 실패, 세션 거부 뒤 stale summary, 멱등 재수신 summary 미검사3건을 RED3실패로 재현했다. 파생 JSON/digest는 ASCII escape를 쓰되 raw bytes는 그대로 저장한다. 거부 summary 초기화/로드 검사, 두 진입점의 기존 derived summary 검사를 적용한다. 함수/전이 제한 때문에 동일4줄 검사를 얇은 wrapper로 감싸지 않고 각 진입점에서 직접 실행한다. stage2 commitc56e80a.

- 최종 전체 검토: 초기 A 모드 non-1 visualViewport.scale과 정상→거부 manifest 재분류 후 멱등 반환2건을 발견했다. JS 초기 gate/Python 관측검사와 capture의 rejected 원문 재검증을 보완했다. final-review-red.log에3파일 회귀 실패를 보존하고 전체26개 합성 검사를 재실행한다. stage3 commitbe29a34.

## 최종 인계
정확한5개 파일의 합성26개 통과(기존12+새14). 중요한 단계별/전체 검토9건 회귀 보완 완료. 소스 SHA/구조·변경15파일·미확인·리스크·롤백은 [결과 보고서](../reports/synthetic-observation-loop-20261117.md)와 ignored execution.json/final-green.log에 기록했다. 최대7정의/4전이 준수, 기존 packet/assets/진척 기준 파일 보존. HTML: 열기 요청 성공(exit0), 실제 렌더 미확인. 실제 수집 실행 불가·human_truth/eligible=false 유지, main/push 미실행.

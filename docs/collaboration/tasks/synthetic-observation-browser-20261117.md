# 실제 브라우저 합성 관찰 검증 실행 계약

task_id: synthetic-observation-browser-20261117
owner: Codex
status: ready_for_review
base_sha: 37af253dba992746f3a664dcb32230f9ac50db62
branch: codex/synthetic-observation-browser-20261117

## 목표와 경계
실제 Chrome에서 기존 fixture/render_page를 사용하여 표시→입력→textarea 내보내기→capture_receipt/load_receipts를 검증한다. 이번 사용자 첨부 요청이 spec이며 재승인 없이 이 세션에서 직접 실행한다. 제품 정책 설계는 하지 않는다. synthetic_fixture / not_executable_pending_collection_contract_approval / human_truth=false / eligible_for_collection=false 유지. null 기기·출처·표본수·실제 관찰 절차·수용 수치는 미정이다. 별도 인력/비용 비필수와 AI 사람정답 대체 금지 유지. 모델/worker/실자료/라벨/선택기/게이트/운영 fallback/외부 provider/main 통합/push 금지.

## 정확한 소유 파일
- docs/collaboration/tasks/synthetic-observation-browser-20261117.md
- docs/collaboration/reports/synthetic-observation-browser-20261117.md
- tests/observation_real_browser_fixture.py (기존 fixture/renderer로 시험 출력 생성, 제품 API 없음)
- tests/observation_real_browser_controls.js (합성 출력 전용 실패 조작/원문 증거 버튼)
- tests/test_observation_browser_receipt.py (실제 추출 원문→기존 receipt 연결 검사)
발견한 제품 결함은 이 계약에 정확한 파일·실패 근거를 먼저 추가한 뒤 최소 수정한다. 그 밖의 tracked 파일은 변경 금지. ignored 산출물: artifacts/synthetic-observation-browser-20261117/ 아래 생성 HTML/packet/실제 추출 raw/receipt ledger/log/evidence/report.html/screenshot. 합성 출력만 file URL로 연다. 불가할 때만 전용 임시 폴더를 127.0.0.1 정적 제공하며 종료 시 정리한다.

## 읽기 전용 검토 결과
37af253 최종 코드/tests/계약 검토와 독립 reviewer 결과 세 P2 중요 잔여 결함 없음. 근거 display.js:80–86, response.py:70–87,127–141, receipt_status.py:17–28, receipt.py:69–75,87–101,146–192. 검토 단계 검사·수정·실자료 접근 없음. 원본/new checkout 지정 task/report 네 파일 bytes 동일. reviewer는 정적 검토만 했다.

## 실행 계획과 수용 기준
- [x] 1 읽기 전용 diff 검토와 독립 검토. native worktree를 정확한 base에서 준비. 계약 커밋.
- [x] 2 기존 정확한 6개 검사 파일을 각각 실행하여 현재 통과/실패를 기록. Python3.12/Pillow12.3.0만 전용 venv에 설치, Torch 없음.
- [x] 3 H/A null profile 실제 이미지·SHA/Blob/decode, 시작 전 disabled→정상 활성화. 정상 네 상태의 명시 전이, 한글 앞뒤 공백/줄바꿈 메모 보존. test-only 시작 버튼으로 initialize 호출을 지연하며 crypto/decode/displayReady 교체 금지.
- [x] 4 명시 profile 시험: 시험 viewport 800×600, 실제 DPR 읽고 matching/DPR/viewport/CSS 불일치. 숫자는 제품 기준이 아니다. ref/src/제거·복원과 change 당시 CSS0 후 복원해도 무효 latch와 원답 유지. 생성 후 합성 자산 변조/누락/해시 일치 decode 실패에서 disabled 확인.
- [x] 5 실제 textarea 문자열을 DOM read-only API로 추출, UTF-8 원문 파일로 저장. 브라우저 자체 TextEncoder/SHA/byte count와 파일/raw.bin bytes·SHA 비교. 원문 재직렬화/strip 금지. 실제 session_id를 합성 수신 context에 연결. 네 상태·로그·메모·별도 received_at·멱등/별개 context를 검사. 기존 거부/충돌/부분 저장 회귀 재사용.
- [x] 6 결함 발견 시 systematic-debugging→최소 RED→GREEN. 제품 변경 없으면 기존 행동 검증으로 기록하며 가짜 RED를 만들지 않는다. 소스 변경 시 독립 최종 diff 검토, 중요 지적 보완. verification-before-completion 후 로컬 커밋, clean 상태·남은 의존 보고 및 종료.

## 정확한 검사
각각 `.venv/bin/python -m unittest discover -s tests -p <name> -v`: test_observation_packet.py, test_observation_assets.py, test_observation_page.py, test_observation_response.py, test_observation_receipt.py, test_observation_p2.py, 새 test_observation_browser_receipt.py. wildcard/전체 suite 금지. 기존 Node VM/DOM stub와 실제 Chrome 결과를 분리한다. 브라우저는 cua_repl의 documented locator/evaluate(read-only)만 사용한다. 필요한 DOM 변조는 합성 생성 출력의 명시 시험 버튼으로 수행한다.

## 구조와 인계
새 Python 파일 각 최대3정의, JS 최대3정의 목표/상한7. 제품 경로 변경 없음. render_page→verify_assets→validate_packet→validate_profile→exact_keys 및 capture_receipt→validate_response→validate_observations→validate_event→exact_keys=4. receipt 시험은 새 제품 wrapper 없이 직접 호출한다. 새 helper는 데이터/파일 전달만 담당한다. 실제 결과로 함수 수/주요 호출을 재확인한다.

HTML ignored 경로 artifacts/synthetic-observation-browser-20261117/report.html 생성·내용 대조·브라우저 열기와 실제 렌더 확인을 각각 기록. 진척 두 정본은78/100 v1.13이며 이번 합성 도구 검증으로 증가시키지 않는다. 모델 누락/오탐/독립성·일반화 개선 미평가.

리스크: 브라우저 관측은 자기 보고이며 사람 판정/독립성 증명이 아니다. 원문 bytes 연결은 사람정답 채택이 아니다. 롤백은 이번 로컬 결과 커밋만 revert, 계약 철회 시 계약도 역순 revert. 이전 커밋/원본/다른 worktree 보존. 실행 로그·코드 SHA·브라우저 조건·화면·원문 SHA·미검증·최종 SHA를 보고서/handoff에 기록한다.

## 실행 인계
기존31+실제 추출 원문 연결2=33통과(skip0), 실제 Chrome156.0.8078.80 합성14종 확인. 제품 코드 결함 발견 없음/수정 없음. 계약deb2883, 검증 소스710d860c6be4b67cfb12ef70dc96c00d10e92c2a. 새 파일 함수 수0/2/3, 제품 최장4전이 유지. 생성 wrapper 제거 전후20출력 bytes 동일. 독립 선행/최종 reviewer 중요 잔여 결함 없음. 미정 값과 사람정답/적격false·실행불가 유지. [보고서](../reports/synthetic-observation-browser-20261117.md) 및 ignored source-manifest.json/final-*.log/원문·화면 근거 참조. HTML 열기/렌더와 서버 종료는 최종 확인 후 기록한다.

최종 확인: 정적 HTML 열기 요청 성공 및 실제 Chrome AX/화면 렌더 확인 완료(report.jpg). viewport override 원복 완료. 이번 시험 서버 PID68356 종료(exit143), 127.0.0.1:43187 listener 없음 확인. HTML 탭의 현재 렌더는 열어 두었으며 서버는 재실행하지 않는다. 최종 문서 커밋 SHA·clean 상태는 ignored handoff.json/최종 세션 보고에서 제공한다. 미완료 승인 작업 없음. 남은 의존은 이번 범위 밖 실제 수집 계약 승인과 실제 자료/독립성/모델 검증이다.

# 실제 브라우저 합성 관찰 검증 결과

개발 진척 **78/100 유지** (`usable-card-analysis-v1.13`, 운영 준비 미완료). 이번 성과는 **실제 Chrome 합성 표시→입력→원문 내보내기→receipt 저장 검증**이며, 지정 Python 합성 검사 **33개 통과**(기존31 + 실제 추출 원문 연결2). 모델 성능·사람 판정 독립성·일반화 개선은 미평가다.

## 기준·로컬 커밋
- 시작: `37af253dba992746f3a664dcb32230f9ac50db62`, 검토 부모 `858de45c85a455085c34e9bddc0823d161e57651`.
- 브랜치: `codex/synthetic-observation-browser-20261117`. native create_worktree로 새 격리 checkout 생성. 기존 checkout/브랜치/미커밋 변경 보존.
- 구현 전 계약 커밋: `deb2883`.
- 최종 검증 소스 커밋: **`710d860c6be4b67cfb12ef70dc96c00d10e92c2a`**. 제품 소스는37af253과 동일. 후속 문서 커밋은 검증 소스와 구분하며 전체 최종 인계 SHA는 ignored handoff.json과 세션 완료 보고에 기록한다.
- main 통합·push·실제 자료 접근·사람 판정 수집/재요청·모델 검증/학습/추론·외부 provider 호출 없음.

## 선행 읽기 전용 검토
첫 단계에서 git show37af253과 연결 코드·기존 테스트·계약을 읽었으며 검사 실행/수정 없이 독립 reviewer에게 같은 diff를 검토시켰다. 세 P2 범위의 중요한 잔여 결함은 발견하지 못했다.

|P2|파일·줄 근거|판단|
|---|---|---|
|null 유지·명시 조건만 대조|observation_display.js:80–86, observation_response.py:70–87|viewport/DPR/CSS가 non-null일 때만 비교. null 승인/숫자 보충 없음.|
|change 당시 표시 오류 누적|observation_response.py:79–87,127–141, observation_response.js:4–10|해당 entry 자산 누락/연결/natural/CSS 실패는 검증 false로 누적. 나중 export로 회복하지 않음.|
|receipt 상태/사유 공유|observation_receipt_status.py:17–28, observation_receipt.py:69–75,87–101,146–192|생성·로드·멱등에서 공유 분류/원문 요약 재검사. AI/unknown/보류를 synthetic_only로 바꾼 재해시 manifest 거부.|

원본 worktree의 tasks/reports synthetic-observation-{p2,loop}-20261117 네 문서를 읽고 새 checkout 동일 문서와 bytes를 대조했다. 모두 동일. 정적 검토는 실제 동작 확인과 구분한다.

## 실제 실행 환경과 방식
- 실제 실행 **Google Chrome156.0.8078.80 / macOS**, navigator.userAgentData.fullVersionList로 확인. 축약 UA는156.0.0.0. 설치된 앱 plist157.0.8103.79와 실행 버전은 달라 설치값을 실행값으로 사용하지 않았다. 근거 runtime-version.json.
- H/A null profile: 실제 시험 viewport **1728×941 CSS px, DPR2, visualViewport.scale1**.
- 명시 profile 및 실패 조작: viewport override **800×600, 실제 DPR1**, 명시 image_css64×64. 제품 승인 기기·수용 기준이 아니다.
- override 직후 DPR2로 만든 첫 explicit fixture는 실제 DPR1과 달라 잠겼다. systematic-debugging으로 environment 관측값과 profile을 대조해 원인을 확인했다. 제품 함수를 완화하지 않고 시험 입력 DPR만1로 다시 생성한 뒤 matching 활성화·각 필드 불일치 차단을 확인했다. 처음 결과도 browser-evidence.json에 남겼다.
- cua_repl의 documented Chrome locator/selectOption/fill/click 및 read-only DOM evaluate 사용. 브라우저 내부 함수를 대체하거나 read-only evaluate로 DOM을 수정하지 않았다. 실패 조작은 생성된 합성 페이지의 명시 시험 버튼만 사용했다.
- 기존 메모리 fixture와 render_page가 검증한 bytes를 사용. 시작 버튼으로 initialize만 지연해 검증 전 disabled를 관측했다. crypto.subtle/Blob/image.decode/displayReady는 제품 원본 그대로다.
- file URL은 도구 URL 정책으로 거부돼 사용하지 않았다. 사용자 승인된 대안으로 `python -m http.server 43187 --bind 127.0.0.1 --directory artifacts/synthetic-observation-browser-20261117/pages`에 해당하는 인자 배열 실행. 실제 명령은 아래 재현 항목 참조. 합성 출력 전용 폴더만 제공했으며 저장소 루트/artifacts 전체/실자료/.claude는 서비스하지 않았다. 초회 timeout 뒤 호스트의 LISTEN/HTTP200 확인 후 reload 성공. 서버 종료 여부는 handoff에 기록한다.

## 실제 시나리오 결과
|시나리오|실제 결과|
|---|---|
|H/A 표시 전→후|두 모드 입력 disabled→실제 SHA/Blob/decode 후 활성화. 빨강8×8·파랑4×4 합성 이미지 표시, natural/CSS 크기/expected와 measured SHA 일치.|
|H/A 네 상태·메모|normal→defect→unassessable→unreviewed 명시 전이와 관찰 로그 보존. `  한글 합성 메모\n두 번째 줄\n `의 앞뒤 공백·한글·줄바꿈 보존. null profile 세 값 유지.|
|명시 조건 일치|800×600/DPR1/image_css64×64에서 활성화, 실제 export 수신 display_verified=true.|
|viewport/DPR/CSS 불일치|각각 viewport801×600, 요구 DPR2, 실제 CSS63×64 사례에서 disabled 유지. 각 필드 단독 불일치로 검사.|
|합성 자산 변조|내장 bytes SHA 불일치, verified/decoded=false, 입력 차단.|
|합성 자산 누락|자산 집합 불일치, proof 집합 빈 상태, 입력 차단.|
|해시 일치 decode 실패|생성 후 합성 bytes를 비이미지로 바꾸고 합성 packet SHA도 일치시킴. SHA는 일치하나 실제 decode 실패, 입력 차단. Python 제품 검증은 우회하지 않고 실패용 전송 결과만 조작.|
|decoded natural 크기 불일치|생성 후 기대 크기만9×8로 바꾼 출력에서 gate 차단.|
|change 당시 CSS0|초기 normal/메모 입력 후 CSS0에서 defect 전이 시 무효 latch. CSS 복원 후에도 disabled, defect·메모 보존, receipt pending_observation.|
|ref/src 변경·제거/재연결|오류 순간 잠김, ref/src/요소 복원 후에도 disabled. normal·메모와 원문 유지. ref 변경 이력은 독립 수신에서 rejected, src·제거 이력은 pending_observation. 검증 성공으로 복귀하지 않음.|

근거: browser-evidence.json, h/a/explicit 및 실패 시나리오 .raw/.proof.json, 각 .jpg. 이미지 의미를 사람/AI에게 판정시키지 않았으며 상태는 시험이 정한 자동 조작이다.

## 실제 문자열→UTF-8 원문→receipt
내보내기는 다운로드가 아니라 제품 exportResponse가 설정하는 `textarea#out.value`다. 이 DOM 문자열을 read-only locator.evaluate로 추출한 뒤 Node fs.writeFile의 UTF-8 인코딩으로 원문 파일을 만들었다. JSON parse/stringify/strip/정규화로 파일을 재구성하지 않았다. 브라우저 시험 버튼이 같은 textarea.value를 실제 TextEncoder로 인코딩·crypto.subtle SHA 계산한 결과와 파일 byte 수·SHA를 대조했다. 파일을 새 checkout으로 복사한 뒤 capture_receipt가 저장한 raw.bin과 bytes를 다시 대조했다. 이 문자열 추출은 HTTP 응답 bytes를 보존했다는 주장이 아니라 **브라우저 textarea 출력 문자열의 UTF-8 bytes**를 보존한 것이다.

|실제 출력|bytes|SHA-256|receipt|
|---|---:|---|---|
|H|13747|360d17315fc2268eeeeb26064e5f4a6bb1aea398733833341a673dac3e6c5957|synthetic_only|
|A|13748|41abcd5ded00188b1499dcd5747b8984ab97c525969ebea2530b129331ba5f22|synthetic_only|
|명시 profile|5079|3ac58fc0c47c4ea89b46805260fc6e11f4725215ac3fa039e0eac401051f9aff|synthetic_only|

세 원문 모두 파일/raw.bin bytes·SHA 일치. 실제 browser session_id를 synthetic 수신 context에 그대로 연결했다. 별도 수신 received_at, 전체 observations/events, 메모·상태를 보존하고 정확한 재접수만 같은 receipt를 반환했다. reviewer_id가 다른 context는 별개 receipt이며 재로드 성공. 모든 기록 human_truth=false/eligible_for_collection=false. 오류 뒤 복원한 네 원문도 byte/SHA 일치하고 보류/거부로 재로드·멱등 검사를 통과했다. ref 이력의 잘못된 binding은 rejected 원문으로 보존되며 응답 필드는None이다. 원답 raw.bin은 없어지지 않는다. 거부·충돌·부분 저장·AI/unknown provenance와 재해시 위조 회귀는 기존 정확 검사 파일을 재사용했다.

근거 receipt-evidence.json, invalidated-receipt-evidence.json, receipts/ 아래 raw.bin/receipt.json. 반복 harness 실행은 수신 시각이 다른 별개 context를 추가하며 기존 기록을 덮어쓰지 않는다.

## 변경 파일·핵심 diff·구조
- tests/observation_real_browser_fixture.py: 기존 fixture/renderer로 정상·실패 HTML 생성. 불필요한 generate wrapper 없이 top-level orchestration(0정의), 제품 최장 경로4전이 유지.
- tests/observation_real_browser_controls.js: 출력 전용 시작/DOM 실패 버튼과 원문 UTF-8 SHA 증거(2정의). rawProof는 WebCrypto를 직접 호출하며 제품 검증 함수 대체 없음.
- tests/test_observation_browser_receipt.py: 실제 추출 원문만 읽는2개 검사와 setup(3정의). 외부 증거 환경변수가 없으면 SkipTest로 한계를 명시하며 이번 실행은 skip0이다.
- 새 task와 이 보고서: 승인 경계·소유권·계획·실제 결과·롤백 기록.

제품 소스/기존 fixture/tests/진척 두 정본은 base와 bytes 동일. Ponytail 최소 변경 원칙으로 결함 없는 제품 코드는 수정하지 않았다. 새 제품 API·수집 서버·범용 프레임워크 없음. 생성기 wrapper 제거 전후 합성 출력20파일 bytes 동일 확인. Python AST/JS 함수 수는0/2/3, node --check 통과. 주요 제품 경로는 render_page→verify_assets→validate_packet→validate_profile→exact_keys=4, capture_receipt→validate_response→validate_observations→validate_event→exact_keys=4이며 시험 entry orchestration에서 직접 API를 호출한다. 시험 JS testMutation은 제품 검증 함수를 호출하지 않고 DOM 입력만 만든다. rawProof는 플랫폼 API만 사용한다.

## 실제 명령·검사·검토
전용 venv Python3.12.15/Pillow12.3.0, 기존 Node 사용. Pillow만 기존 pinned 버전 설치, Torch/모델 의존성 설치 없음. 코드/시험 출력 수정 및 검사 모두 ./develop 잠금 안에서 직렬 실행했다.

```sh
./develop -- env PYTHONPATH=.:tests .venv/bin/python tests/observation_real_browser_fixture.py artifacts/synthetic-observation-browser-20261117/pages 1
.venv/bin/python -m http.server 43187 --bind 127.0.0.1 --directory artifacts/synthetic-observation-browser-20261117/pages
```

각각 `./develop -- .venv/bin/python -m unittest discover -s tests -p <정확한 파일명> -v`로 실행한 결과:

|파일|검사 수|결과|
|---|---:|---|
|test_observation_packet.py|6|통과|
|test_observation_assets.py|6|통과|
|test_observation_page.py|3|통과|
|test_observation_response.py|5|통과|
|test_observation_receipt.py|6|통과|
|test_observation_p2.py|5|통과|
|test_observation_browser_receipt.py|2|통과(skip0)|

마지막 파일은 `SYNTHETIC_BROWSER_EVIDENCE=artifacts/synthetic-observation-browser-20261117` 환경변수로 실제 추출 증거를 지정했다. 정확한 subprocess 인자와 결과는 final-*.log의 COMMAND 및 로그에 있다. wildcard discovery·전체 suite는 실행하지 않았다. 기존31개 일부가 호출하는 Node VM/DOM/decode stub은 실제 브라우저 검사가 아니다. 이번 Chrome 도구 실행14종 시나리오와 실제 추출 원문 연결2검사를 따로 구분한다.

제품 결함이 발견되지 않아 제품 RED→GREEN 수정은 없었다. 실패 fixture가 잠기는 것은 기대 결과이며 이를 제품 결함 수정 성과로 세지 않았다. 시험 환경 DPR 불일치 역시 제품 수정이 아니다. 최종 독립 reviewer는 새3소스·계약·연결 코드만 읽고 중요한 잔여 결함 없음으로 보고했다. reviewer는 검사 실행·실자료/artifacts 접근·수정을 하지 않았고 브라우저 실행 증거를 독립 인증한 것은 아니다.

## 미확인·리스크·롤백
실제 수집 실행 불가·synthetic_fixture·human_truth=false·eligible_for_collection=false 유지. 기기·사진 출처·표본수·실제 판정/관찰 절차·수용 수치 미정. 별도 인력/비용 확보 비필수, AI 정답 대체 금지, 기존 고정 진척/평가 게이트 그대로다.

브라우저 자기 보고·합성 자동 조작은 사람의 관찰/독립성/주의·실기기 적합성을 입증하지 않는다. Chrome 한 환경의 합성 bytes 시험이며 다른 브라우저/실사진/EXIF·실운영/모델 성능·배포 검증은 미실행이다. SHA는 내용 연결이며 악의적 전체 재작성 방지 서명은 아니다. 새 receipt 검사는 먼저 실제 브라우저 증거를 생성해야 재실행 가능하다. 일반 실행 시 skip을 통과 성과로 세지 않는다. 합성 PNG가 작으며 의미 판정용 UI 개선을 이번 범위에 추가하지 않았다.

롤백은 이번 소스 커밋710d860을 git revert. 결과 문서/계약도 철회할 때 후속 문서 커밋→710d860→deb2883 역순 revert한다.37af253 이하 이력/원본/다른 worktree/실자료를 삭제·변경하지 않는다. 실제 롤백 미실행. ignored 근거는 보존한다.

정적 HTML: artifacts/synthetic-observation-browser-20261117/report.html. 열기 요청 성공/실제 렌더 확인·서버 종료 결과는 task/handoff에 기록한다. 로컬 커밋 후 승인 범위를 마치고 종료하며 이후 자동 실행을 약속하지 않는다.

최종 확인: 정적 HTML 열기 요청 성공 및 실제 Chrome AX/화면 렌더 확인 완료(report.jpg). viewport override 원복 완료. 이번 시험 서버 PID68356 종료(exit143), 127.0.0.1:43187 listener 없음 확인. HTML 탭의 현재 렌더는 열어 두었으며 서버는 재실행하지 않는다. 최종 문서 커밋 SHA·clean 상태는 ignored handoff.json/최종 세션 보고에서 제공한다. 미완료 승인 작업 없음. 남은 의존은 이번 범위 밖 실제 수집 계약 승인과 실제 자료/독립성/모델 검증이다.

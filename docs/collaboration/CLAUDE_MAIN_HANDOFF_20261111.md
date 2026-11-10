# Codex → Claude 메인 인계 — 2026-11-11

개발 진척 **78/100(usable-card-analysis-v1.13), 운영 준비 미완료** 유지. 사용자 요청으로 메인 역할 인계를 준비했다. **Claude 인수 확인 전이며 이양 완료가 아니다.** Claude를 실행하거나 외부 AI를 호출하지 않았다. Codex는 이 문서의 검증·일반 push 뒤 상태 변경을 멈춘다. 인수 후 Claude만 메인 변경을 수행한다.

## 1. 인수 순서와 현재 Git 상태

- 사용자의 명시 요청: “메인 롤 클로드에게 넘길거니까 지금까지한거 이어서 할 수 있도록 준비해서 프롬프트 줘”. `PAIR_CODING.md` §7에 따른 준비다. 과거 인계 문서의 역할/수치를 현재 상태로 사용하지 않는다.
- 코드 기준 main/origin/main: `ca6ed99a74c942ef8ff809227cbc4bdb46b799d8`. 이 뒤 이번 인계 문서 커밋만 추가된다. 최종 원격 동기화 SHA는 로컬 `artifacts/claude-main-handoff-20261111/remote-sync.json`에서 확인한다. 자기 문서의 커밋 SHA를 본문에 순환 기록하지 않는다.
- 작업 트리의 기존 비소유 untracked는 `.claude/`뿐이었다. 내용은 미검토이며 삭제/스테이징/덮어쓰기하지 않는다. 다른 worktree는 전부 보존했다. 목록/branch/SHA는 checkpoint.json에 기록한다.
- 협력 잠금은 비차단 flock 획득으로 FREE 확인. 잠금 파일의 pid는 오래된 기록일 수 있어 프로세스 생존 증거로 쓰지 않는다. 별도 읽기 전용 ps 검사에서 인식 가능한 프로젝트 Python/worker 프로세스는 0개였다. 검사 패턴에 잡히지 않는 모든 프로세스의 부재를 증명한 것은 아니다. 인수 직전에 다시 확인한다.
- `tools/pair-control/.state`는 없었다. 관제 세대/승인 장부를 생성하거나 바꾸지 않았다. 체크포인트와 실제 Git/잠금을 대조하고 수신 세션 ID·역할·승계 범위를 작업 기록에 남긴 뒤 첫 승인 행동(아래 저장 근거 감사)을 수행해야 인수 완료로 표현한다. Codex 세션 토큰이나 관제 인증을 만들어내지 않는다.
- 같은 Mac의 기본 checkout에서 인수한다. `artifacts/`와 사람 응답은 Git 제외이므로 git pull만으로 다른 컴퓨터에 전달되지 않는다. 없으면 이 로컬 증거 묶음을 확인하고, 원문/사진/모델을 추정 재구성하지 않는다.

## 2. 이번에 완료한 일과 사람 정답의 정확한 의미

현재 313개 검토 항목은 모두 응답 처리됐다. 다만 두 범위를 구분한다.

|범위|항목|결과|
|---|---:|---|
|점선 후보 사각형 안의 결함 유무|303|defect182 / normal52 / unknown69|
|확대 사진 안 어딘가의 결함 유무|10|별도 관찰. 후보 위치 정답으로 바꾸지 않음|

- 후보 응답: kind=`surface_candidate_review_manual_draft`, scope=`visible_defect_in_model_candidate_box`. `defect`는 점선 안 실제 손상, `normal`은 충분히 보이지만 점선 안 손상 없음, `unknown`은 판단 불가. 모델이 정상이라는 뜻으로 반전하지 않는다. 정상 후보 52곳이 카드/구역 전체 정상이라는 뜻도 아니다.
- 초기에 안내를 혼동해 받은 사진 전체 10건은 kind=`surface_point_review_manual_draft`, scope=`visible_defect_in_displayed_crop` 또는 이 범위를 명시한 legacy 입력이다. 10건 모두 defect 관찰이나 후보 위치를 확인한 답이 아니다. 기존 정상 라벨과 다른 7건은 충돌로 보존했고 덮어쓰지 않았다.
- **정밀한 사람 결함 좌표는 새로 받은 것이 0개다.** `candidate_box`는 모델이 선택한 최고 반응 패치 지지 영역이며 손상의 정확한 점이 아니다. `point:null`/빈 설명을 점·정상·결함으로 추정하지 않는다. unknown69개를 이진 정답에 포함하지 않는다. null은 미선택으로 남기며, 이후 사용자가 답하면 새 명시 응답으로 처리했다.
- 기존 region_target은 당시 고정된 구역 라벨을 바인딩하는 참고 정보다. 이번 답변으로 원래 학습/평가 라벨·배점·분모를 수정하지 않았다. 원래 결함 구역에 후보가 없다는 답은 구역 라벨 오류의 증거가 아니다. 다른 위치에 손상이 있을 수 있다.
- 최고 패치 하나만 보여준 탐색/진단 표본이다. 182/234 등을 전체 정확도나 재현율로 보고하지 않는다. 새 일반화 개선·AUC 개선·학습 완료를 주장하지 않는다. 평가 입력과 학습 입력/물리 카드 그룹을 계속 분리한다.
- 완료한 판정은 다시 묻지 않는다. 새 후보 범위 미확인으로 남은 초기 사진 전체 10개를 자동 확인 처리하거나 새 설문으로 재요청하지 않는다. 범위 차이는 summary.json의 명시 ID 목록에 보존돼 있다.

### 데이터 정본(전부 기본 checkout의 로컬 ignored 파일)

1. `artifacts/mobile-candidate-review-complete-20261111/summary.json`
2. `artifacts/mobile-candidate-review-complete-20261111/candidate-answers.json` — 303개 합본, 기존 후보 validator 통과.
3. `artifacts/mobile-candidate-human-ledger-20261110/*.json` — 후보 원문/범위/SHA/후보 토큰·사각형/완료 ID. 일부 저장본은 공백만 정규화했다는 플래그가 있다. 모든 제공 값은 유지됐고 source_text 해시/answers 대조를 다시 통과했다.
4. `artifacts/mobile-human-review-ledger-20261110/*.json` — 별도 사진 전체 10건.
5. `artifacts/mobile-candidate-human-response-*/` 및 `artifacts/mobile-human-response-20261110-batch01/`, `...batch02/` — 수신 응답과 요약.
6. `artifacts/mobile-point-review-20261110/packet.json` — packet_id `8cca9f9bd206ac1ad04fe0ad395a71cfca47c43db3695ebbddf202979a1fad96`.
7. `artifacts/surface-grounding-20261110/packet.json` — 원래 저장 점수/구역 대응, source_packet_id `397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc`.
8. `artifacts/mobile-candidate-review-workflow-20261110.json` — status=current_review_queue_complete, remaining0, active_reviews=[]; 새 학습이나 다음 검토 파일을 자동 생성하지 않는다.

## 3. 보존한 모바일 방식과 검증 한계

사용자는 서버·터널·localStorage 없이 파일 하나, 일반 img/dataURI, 원본crop 먼저/전체 사진 접기, 미확인 점선 토글, 10건 한 파일, JSON 한 번 복사를 요구했다. 최초 SVG/외부 경로 화면은 흐려 판정 불가였고 정답으로 쓰지 않았다. 스크립트 실행 준비 상태가 시작되지 않아 JS 의존을 제거했다.

현행 `tools/diagnostics/mobile-point-review-20261110/ten.py`는 native checkbox+CSS 토글, 기본 라디오, 40개 선택 조각으로 마지막 contenteditable JSON 칸을 구성한다. 동일 원사진은 SHA별 한 번 내장한다. 작은 파일이 필요할 때 구역 PNG만 무손실 WebP로 재포장했고 RGB 바이트 동일성을 검산했으며 원사진·JSON은 그대로다. 새 검토가 필요하다고 이미 완료한 라벨을 다시 묻지는 않는다.

`manual.py`는 사진 전체 관찰만 검증/저장한다. 후보 응답을 넣으면 거부한다. `candidate.py::validate_candidates`는 후보 응답의 packet/id/사진SHA/기존구역/token/box/판정을 검증한다. 현재 후보 수신·다음 파일 선택 일부는 이 채팅에서 develop 안의 일회성 명령으로 실행했으며, 일반 CLI 하나로 완전히 자동화된 것으로 주장하지 않는다. 증거는 저장된 ledger/manifest/postflight다.

폰에서 복사한 JSON들을 수신·검증한 기록은 있지만 이 세션에서 네이티브 폰 화면/클립보드를 직접 관찰하지 않았다. macOS open exit0은 열기 요청 수락일 뿐 렌더 확인이 아니다. 이전 file: 보안 차단을 브라우저·서버·터널로 우회하지 않는다.

## 4. 고정 대조군과 실패한 표현(채택되지 않음)

같은 반복 개발CV: 1776구역/204사진, 결함370/정상1406,5fold. 직접 alpha0 대조 `20261108T215307-941b3aaa`: AUC0.931924954826804,FN57/370(15.4054%),FP167/1406(11.8777%). 원래 품질 reference `20261106T210640-0eb1bdc0`: AUC0.9166506478028527,FN67/370,FP201/1406. 직접 대조와 원래 reference를 섞지 않는다. 아래 결과는 과거 저장 근거이며 이번 인계에서 성능을 다시 평가한 것이 아니다.

|실패 가설 ID|고정 표현|AUC|FN/370|FP/1406|완료 기록|
|---|---|---:|---:|---:|---|
|surface-frozen-global-lme-local-contrast-20261109|[x,abs(x-local_mean3x3)]768D|0.925992849|61|171|20261109T105308-99e918d6|
|surface-frozen-global-lme-normal-distance-20261109|[x,normal_distance]385D|0.931325209|56|174|20261109T115137-dab89dcc|
|surface-frozen-global-lme-position-interaction-20261110|[x,u*x,v*x]1152D|0.909963093|88|169|20261109T210729-0a9c06cc|
|surface-patch-cls-interaction-20261110|[x,x*CLS]768D|0.898043136|96|177|20261109T221044-f3b30c8f|

근거는 각 `docs/collaboration/reports/surface-...md`와 동일 가설의 `artifacts/.../plan.json`, `artifacts/experiments/<ID>/record.json`/observations/result다. 정상거리와 국소대비 수치를 혼동하지 않는다. 국소대비 선행 실행 `20261109T103853-3fa5c0b6`은 interrupted/-15이며 별도 실행이다. OOM/optimizer 실패/성능실패로 추정하지 않는다.

손실·대조·성공기준 고정: alpha0, 정상/결함bag1, L2=1, normal upperLSE tau0.1, 결함/출력max, sigmoid, threshold0.5, seed20261031,1000iterations/1250evaluations, 최종gradient1e-5/내부1e-7. 정상통계/center는 각 학습fold만. 표현gate는 직접alpha0 대비 AUC차>0 및 사진group paired95%CI하한>0. 채택AND는 FN≤67/370,FP≤112/1406,원래reference AUC차≥0.03 및 paired하한>0,5fold수렴/근거/분리/기존사람점보호다. 실패한4표현을 새 반증 없이 반복하거나 계수/alpha/threshold/scale/규제/기준 변경으로 구제하지 않는다.

직근 공통record `20261109T234706-4aeb730c`는 completed/return_code0, `surface-alpha0-grounding-diagnostic-20261110`다. 저장alpha0 재현 진단이며 새 모델 개선이 아니다. 이후 사람 응답 수신에서 학습·추론0,독립평가0이다.

## 5. 승계 권한과 금지

- 기존 개발·검증·통합·일반push 권한은 사용자 메인 교대 지시와 PAIR_CODING §7에 따라 승계한다. 새 메인이 검증한 변경은 일반push로 origin/main까지 동기화하고 원격SHA를 확인한다. force/history rewrite/다른worktree 삭제는 승인하지 않는다.
- 교대는 새 실험·재학습·Gemini/CodexCLI 외부호출·백본 재추출의 무제한 승인이 아니다. 새 학습 전 근거/한변수/직접대조/고정 성공실패 기준을 사용자에게 보여준다. 다음 새 가설은 아직 확정·승인되지 않았다.
- 실제 학습/비교는 기본checkout의 현재메인만 `./experiment --plan <plan.json> -- <command>`로 실행한다. code_changes/수정전snapshot,사진·물리group분리,기존점보호,결과후기준변경금지를 지킨다. 반환 후 record/observations/최신development_handoff/next_steps/token_report와 자동채택·복원을 확인한다.
- 모델/worker 포함 소스수정은 `./develop -- <수정명령>` 안에서만 수행한다. check뒤별도편집은 잠금이 아니다. 함수≤7/file,프로젝트 호출전이≤4,task에 소유파일 고정. 잠금삭제/동시실험/실패·불명 요청 자동재시도 금지.
- `development-review.json` enabled=true의 session_id는 `01a103d6-3296-7653-b501-da983df849eb`로 현재chat/Claude ID가 아니다. `artifacts/development-cycle/latest.json`도 그 옛 세션의 ai_calls_forbidden이다. 세션묶인 자동실행을 승계했다고 가정하거나 설정을 임의 수정하지 않는다. 이번 인계의 실제외부AI호출0.
- 사람응답/사진/라벨/모델/비밀은 Git에 넣지 않는다. PokeCollector운영/fallback/진척배점/독립시험을 임의변경하지 않는다. 78/100은 정확도가 아니다.

## 6. Claude가 첫 번째로 진행할 작업

1. AGENTS.md/PAIR_CODING.md/COMMON_EXPERIMENT_RECORDS.md/PROGRESS_CRITERIA.md/development-progress.json/docs/collaboration/HTML_REPORTING.md와 체크포인트를 읽는다. 기본checkout에서 fetch,HEAD/변경/진행중Git작업/실행/잠금/해시를 대조해 일치할 때 인수 기록을 남긴다. 다르면 덮어쓰지 말고 차이를 보고한다.
2. **새 학습 없이**303후보 ledger를 원packet·저장점수·구역오류에 join한다. 기존정상구역+후보내결함,기존결함구역+후보내없음,unknown69,모델패치지지영역/표시crop/경계 관계를 구분해 감사한다. 기존결함구역의 후보가 비어도 다른위치에 손상이 있을 수 있어 원라벨 오류로 확정하지 않는다. 판정대상·손상종류·경계/좌표/분모 불일치를 근거로 점검하고 원인을 단정하지 않는다. 최초10crop응답은 별도 표로 두고 후보303의 분모/음성으로 혼합하지 않는다. 완료판정 재질문 금지.
3. 출처검증·범위별 건수를 우선 보고한다. 다른범위/분모로 AUC개선을 만들지 않고 독립시험/평가정답을 학습에 넣지 않는다. 실제 새 성능비교를 한다면 공통실행기 사전계획과 평가계약이 필요하다.
4. 이 근거로 **다음 단일 표현 가설**을 고르고 근거·변경변수 하나·고정대조군·성공/실패 수치를 재학습 전에 보여준다. 실패4표현과 같은 변경을 새 반증 없이 반복하지 않는다. 기존 승인 범위의 독립 구현/합성검사는 이어가되 사람만 결정할 모호한 정답만 질문한다.
5. HTML_REPORTING 계약대로 성과/고정진척 HTML을 생성·열고 합성/정적/실제추론/학습/독립검증을 구분한다. 변경파일·핵심diff·checks·risk·rollback,실험시record상태와 동일분모FN/FP/%p를 보고한다.

## 7. 이번 검증·위험·롤백

이번 `manual_checks.py`,`candidate_checks.py`,`ten_checks.py`를 develop 안에서 재실행해 모두 exit0이다. 원문/hash/legacy범위/ID/사진/후보/중복/변조 보호,후보1024조합,10건76벡터/checkbox/단일JSON/동일사진의 합성·정적 검사다. 실ledger 전체의 source_text해시/answers/ID를 다시 검증했고303합본과 일치,303+별도10=313의 중복없음/잔여0/새정밀점0/unknown69 보존을 확인했다. 이번 새 모델성능 평가는 없다.

사람값/공란/미확인/원패킷은 변경하지 않았다. 모델 개선·운영 채택을 이번 진척으로 보고하지 않는다. 로컬 필수증거 SHA/경로는 `artifacts/claude-main-handoff-20261111/data-sha256.json`에 있다. `handoff-evidence.zip`은 사진/모델/비밀을 포함하지 않는 로컬 Git제외 백업이다. 원문JSON/저장점수 자료는 포함되므로 외부공개하지 않는다.

역할인수 미확인,실제네이티브렌더 미확인,일반화개선 미확인이다. 저장·문서 준비만으로 이양완료라 하지 않는다. 이번 task와 이 MD 두파일만 추가했고 코드/라벨/승인설정은 미변경이다. 되돌릴 때 문서커밋을 일반git revert하며 데이터/증거를 보존한다. Claude가 인수했다면 역할을 단독으로 역전하지 말고 조정한다.

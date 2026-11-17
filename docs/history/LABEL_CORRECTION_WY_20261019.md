# W/Y 라벨 정정과 연구 후보 철회 — 2026-10-19

## 직접 답변 반영
사용자 확인: ‘w는 판단 어렵고 Y는 모서리 결함’. W=edge_defect null/학습·평가 제외, X=corner_defect1 유지, Y=corner_defect1 저장. Y는 표시한 우측상단 국소존재만이며 실제점좌표/다른부위정답을 생성하지 않았다. 완료W/X/Y·U/V는 재질문하지 않는다.

## 모델·성능 상태
W를 normal0으로 학습한 후보는 현재 채택에서 제외했다(current-model-clearance.json). 그 후보의 3→2/22 결과는 이전 답변을 조건으로 실행한 역사적 결과로 보존하며 현재 품질개선 근거로 사용하지 않는다. 원본 result/human-observations/계획/체크포인트는 삭제·수정하지 않았다.

W없는 기존 연구기준 artifacts/edge-normal-objective-20261019/candidate-{0,1,2}.pt를 current research-selection.json에 명시했다. 현재 동일26개발구간은 FN0/4, FP3/22(13.64%), 실제점 누락0/4. 기존U/V는TP1/FP1. 현재선택재실행은 캐시26출력/4실제점을 확인했고 차이0이다. 새학습/원본feature추출0. 이는 새 성능 향상이나 운영모델 롤백 실행이 아니며 운영은 계속 미변경 상태다.

## 정답 자료 계약
기존 qualified 모서리 실제점14 + 상세존재5 = 양성19/정상0. detail_data에 최신 W unknown 제안을 넣어 shared builder가 명시적으로 skipped(reason=human truth unknown)함을 실제검증했다. current effective 5행에는 corner1만 있으며 W normal0이 없다. 양음성 클래스가 없어 모서리 head 학습은 시작하지 않았다. 기존사진70행 canonical SHA 불변.

## 변경 파일 / 핵심 diff
- artifacts/label-correction-wy-20261019/human-observation.json: 최신 직접답변.
- effective-proposals.json/readiness.json/effective-detail-rows.jsonl: W null 명시skip·Ycorner1 추가, 전체back anchor·사진/file/decoded SHA·group/split검증.
- research-selection.json/baseline-replay.json/verification.json: W없는 연구기준 경로·해시·현재성능 재실행·역사적 파일불변 근거.
- index.html: W정상승인→철회→현재유효기준을 구분하고 새개선으로 주장하지 않는 사진HTML.
- 이전 artifacts/eevee-normal-edge-training-20261019/label-clarification-pending.json, current-model-clearance.json, current-effective-detail-rows.jsonl, index.html, corner-review/index.html: 모호성해결·W후보사용금지·X/Y종류보존·완료Y재요청방지. 이전 raw답변·학습계획·result·checkpoint는불변.
- EEVEE_NORMAL_EDGE_TRAINING_20261019.md 상단 및 본 문서/소비 TODO: 이전 성과조건 철회.
- new-corner-review/: 이미수집한 다른라이츄back4의4개모서리 원본1:1/숫자1~4·context·정답null. 단일카드/로고/네변/모서리적합성만Codex선별. 정상이라고자동저장하지않음. 추론·학습0.
공용모델코드/기본값/Gemini/OpenCV/운영은 미변경.

## 검증
- 최신effective proposals를 실제공용detail_data로 준비: W unknown skip1, corner1 row5, exact point0, training_ready false.
- historical files 4개 SHA가 정정 전후 동일(verification.json).
- canonical70행 SHA 23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a 불변.
- 기존3checkpoint로26crop/4사람점재실행 차이0, FN0/FP3 확인(baseline-replay.json). 동일 입력 재학습은 하지 않았다.
- HTML local사진/문서참조 확인. 브라우저자동열기/렌더확인은 수행하지 않았다. 사진은로컬뷰어와최종메시지에표시.

## 리스크 / 롤백
최초답변과정정답변을 같은 사실로 취급하면 철회한normal0이 다시학습에 들어갈수있다. current effective proposal 및 clearance를 우선 사용해야 한다. 역사적result accepted 플래그는 당시조건기록이며 현재승인이 아니다. W가unknown이라는 사실을손상1로도바꾸지않는다.

라벨정정을 되돌리지 않는다. 새로운 사람정정이 있을때만 별도증거를 추가한다. 모델은계속W없는기존연구체크포인트를사용한다. 정상모서리가0이어서 다음단계는새라이츄모서리의확인가능한정답뿐이다. 기존완료·판독어려움구간을재요청하지않는다.

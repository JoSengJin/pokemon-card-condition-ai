# A3 실자료 검토·수집 준비 묶음

- task_id: a3-data-intake-batch-20261025
- owner: Claude
- status: assigned
- base_sha: 36469ce8504ce59784850dbb40ac75b2a096dc3e
- branch: claude/a3-data-intake-batch-20261025
- worktree: 로컬 전달 메시지 및 ignored LOCAL_INPUTS.json 참조
- goal: 새 채택본 기준으로 기존 검토 UI에 바로 넘길 신규 질문 패킷과, 현재 자료로 채울 수 없는 평가 셀의 구체 수집 명세를 완성한다.

## 입력과 고정 기준

### 현재 적용 기준 — Codex 통합 보완, 2026-10-25

현재 채택본은 `artifacts/development-manifest-20261025d/combined-reviewed.jsonl`, SHA256 `ad021468b3cd4483b6b335f3b170e452343b6001808725e9faedc4f6635aa935`다. 해당 `ADOPTION.json`·`DECISION.md`·`coverage.json`을 따른다. c는 아래 최초 계약의 이력이자 d의 롤백 기준으로 보존한다. 앞으로 실행할 때 아래 단계1의 "기존 c coverage"는 d 기준과 대조한다. 이전 c 기준의 패킷·수치를 새 d 결과로 간주하지 않는다.

라운드1의 정답·결함점3개·영역 확인을 d에 채택했다. 삭제 정답0, 저장 구역정답0이며 라운드1의12개 질문은 재요청하지 않는다. round2-live는 저장 전 사본과 바이트 동일함을 통합 검사에서 재확인했다. 다음 검토는 사용자가 요청할 때만 기본 checkout에서 연다. 영역 확인 후 저장→raw 재읽기·SHA/기존값 대조→별도 채택 순서다. box를 바꾸기만 해서는 정상 예제의 유효성이 입증되지 않으므로 기존 라벨과 새 좌표의 관계를 감사한다.

평가 정답 생성에서는 inventory의 `with_suffix('.drafts.json')` 경로에 파일·심볼릭 링크가 없는지 확인하고, AI 후보·모델 출력·다른 검수자의 답이 저장된 필드나 화면도 노출하지 않는다. 2인 판정 전 사진과 box를 고정한다. 독립 시험(D1)은 개발에 노출하지 않으며 별도 보관자의 비노출 집계 설계만 [통합 보고서](../reports/data-acquisition-integration-20261025.md)에 기록한다. 새 라벨 요청·수집·파일럿 실행은 이번 통합 범위 밖이다.

### 최초 계약의 입력 이력 — c 기준, 보존

채택본은 기본 checkout의 artifacts/development-manifest-20261025c/combined-reviewed.jsonl, SHA256 360f11cfdaaa61db103dd3f51e3c7e321ea3c0e5a69906cf872b10756dfaa932 이다. ADOPTION.json·DECISION.md·coverage.json을 함께 확인한다. 이전 b와 정답은 같고 f 앞뒤/h 뒤의 box_reviewed만 반영됐다. z는 기존 box와 표면 양성 9개를 그대로 보존했다. 새 z box를 채택하거나 구역 정답을 옮기지 않는다.

A3 원문: 센터링·모서리·엣지·표면·관찰제한의 앞뒤별 개발 평가에 양성/정상 각각20판정단위·각5실물이상 확보, 좌표평가 대상은 올바른 종류의 기존점·정상대조 출처 감사, 분모·지원범위·결측표를 버전동결한다. 전체 진척 30/100, A3는 pending/0점이며 전부 충족할 때만 +5점이다. 독립 시험 D1은 별도다.

coverage의 train/val 20셀 중 수량 충족은 train 엣지 뒤·표면 앞 2개다. train 표면 뒤 정상은13단위/6실물로7단위 부족하지만, 이 셀을 채우는 것만으로 평가 자료가 준비되지는 않는다. 기존 val의 센터링 face 후보 총합(known+unknown)은 앞14/뒤12이므로 양성20+정상20을 위해 최소 앞26/뒤28사진이 추가로 필요하다. 이 수치는 낙관적 하한이며 실제 정답 구성·중복·박스/면 검토에 따라 더 필요하다. 현재 val을 우선 작업 대상으로 두며 train과 합치거나 split을 바꾸지 않는다. train cross-fit를 이미 평가한 것으로 간주하지 않는다. train/val 둘 다 각각 완성해야 한다는 새 A3 기준도 만들지 않는다.

이전 질문 파일은 기본 checkout의 다음3개다. 29/28/25개의 답을 다시 요구하지 않는다. 마지막25개는 미저장이지만 재질문 금지다.
- artifacts/data-coverage-20261024/review/tasks.json
- artifacts/development-manifest-20261025/review/tasks.json
- artifacts/development-manifest-20261025b/review/tasks.json
이번 묶음에서는 이 질문들에 등장한 f/h/z 실물 전체를 신규 질문에서 제외한다. 이름만 바꾼 같은 사진/실물도 제외한다. 기존 known 정답·이미 검토된 단위도 제외한다. 근거 없는 group 동일성/면은 추정하지 않고 차단 목록으로 남긴다.

## allowed_files — 추적 변경 4개만

- docs/collaboration/tasks/a3-data-intake-batch-20261025.md
- docs/collaboration/prompts/a3-data-intake-batch-20261025.md
- docs/collaboration/reports/a3-data-intake-batch-20261025.md (신규)
- docs/collaboration/reports/a3-data-intake-batch-20261025.html (신규, 개인 경로·사진·원문 응답 없음)

ignored 산출물은 자신의 worktree artifacts/a3-data-intake-batch-20261025/ 아래만 작성한다. LOCAL_INPUTS.json은 Codex가 제공한 읽기 전용 로컬 포인터이며 변경하지 않는다. source/·card_condition/·tests/·도구·공용 HTML/UI·의존성·Mastra·진척 기준/점수·기존 manifest/ADOPTION/실험 기록 수정 금지. 기본 checkout의 입력은 모두 읽기 전용이며 사진을 복사하지 않는다. 사진 파일은 해시/크기 대조만 허용하고 모델 추론·AI 판정은 금지한다. 기본 checkout 밖 consumer 코드/설정/키 탐색 금지. manifest가 직접 참조한 사진 읽기만 허용한다.

## 한 번에 수행할 6단계

1. **실제 부족량 고정**: 기존 coverage_report와 현재 manifest로 coverage를 새로 계산한다. 원본의 전후 SHA를 확인하고 기존 c coverage와 의미 차이를 대조한다. train/val 각 셀 양성/정상 단위·실물·결측·박스 미확인·올바른 종류 점 개수/출처 상태를 deficits.json으로 기록한다. 단위와 실물을 섞지 않는다. 현재 평가 셀의 수량/출처/geometry 요건을 별도 표시한다.
2. **새 질문 전수 선별**: 제외 이력과 known 값을 적용한 eligible.json, excluded.json을 만든다. 각 후보에 card/group/split/side/label/area, decoded photo SHA와 raw SHA, 입력 manifest SHA, 기존 box/box_reviewed, 후보 근거·제외 근거를 담는다. face 정상은 지역 정상의 정답이 아니라 후보 선정 근거일 뿐이다. 가려짐/관찰제한은 정상으로 넣지 않는다. 후보의 순위는 평가 val의 실물 다양성·부족량을 먼저, train 보완은 다음으로 한다. 모델 점수는 사용하지 않는다.
3. **바로 사용할 검토 패킷**: first-round.json은 최대12개 질문, 최대6실물로 작게 만든다. 남은 새 후보는 후속 rounds.json으로 모두 분류한다. 패킷마다 채울 수 있는 셀과 사람 답변에 따라 달라지는 범위를 명시한다. 같은 실물의 질문을 묶되 정상 답변을 유도하지 않는다. box 미확인 사진은 geometry-first.json에 먼저 넣고 지역 질문은 blocked_on_geometry로 둔다. box가 바뀌면 이전 구역 좌표/라벨을 자동 이식하지 않고 해당 지역 질문은 새 box SHA가 고정된 후에만 다시 구성한다. 기존 정답을 삭제하는 입력을 만들지 않는다. 새 위치점은 사람만 표시하며 구역 유무를 점 위치로 변환하지 않는다. val 후보가 없으면 train으로 몰래 대체하지 말고 부족과 사유를 적는다.
4. **기존 UI 실행 인계**: READY_TO_REVIEW.md와 private review.html에 원본 전체 사진+강조 구역을 볼 수 있는 기존 UI의 정확한 URL 인자와 실행 명령을 담는다. 기존 `python -m card_condition review <inventory> --port <port>` 및 review.html의 geometry/card/side/area/label/image 파라미터 실제 구현을 확인한다. 기본 checkout에서 Codex가 현재 manifest를 보존한 새 검토용 inventory를 생성한 뒤 여는 방식이다. 자신의 worktree에서 라벨 서버를 띄우거나 root 파일을 쓰지 않는다. 정답/면/box는 자동 선택·저장하지 않는다. 기존 UI가 특정 질문을 지원하지 않으면 그 항목만 blocked로 표시하고 임의 새 UI를 만들지 않는다. READY_TO_REVIEW에는 답변 저장 후 raw JSONL 재읽기·SHA·건수 확인, 기존 정답 및 split/group/사진 보존 대조, 미저장 시 미확인 유지, 채택은 Codex가 담당한다는 절차를 포함한다. 실자료 inventory를 복사해 쓰는 실행은 Codex가 기본 checkout에서만 한다.
5. **추가 자료 확보 명세**: acquisition.json에 각 평가 셀의 최소 부족 양성/정상 단위·실물, 필요한 앞뒤 사진/촬영 조건·관찰제한 유형·출처 권리/동일 실물 확인 항목, 중복 제외 조건을 구체적으로 쓴다. 같은 새 사진이 여러 질문을 지원할 수 있으므로 셀 부족량을 무조건 합산하지 않는다. 신규 paired 실물의 필요 하한과 검토 후 늘어날 가능성을 구분한다. 기존 수집기 tools/collect_ebay_dataset.py를 읽어 collect-only와 AI screening의 차이를 확인하고 외부 호출 없는 명령 초안만 작성한다. API/다운로드/키 탐색/소비 프로젝트 접근은 실행하지 않는다. 새 자료는 평가 후보로 따로 보관하고 학습에 쓰지 않는 절차를 포함한다. PSA등급/판매글 문구를 결함 정답으로 쓰지 않는다. 수집 계획만으로 확보했다고 세지 않는다.
6. **실제 결과·인계**: 실제로 준비한 새 질문 수·실물 수·split/셀·제외 수·geometry 대기·추가 자료 필요량을 MD와 HTML에 적는다. 관찰 가능한 성과는 준비된 패킷이며 확보된 사람 정답 수는0이다. 완료 후 Codex가 할 단 하나의 다음 행동은 첫 geometry/라벨 검토 화면을 열어 실제 응답을 저장하는 것이다. 전체 진척30/100 유지, A3 미충족 사유를 적고 status ready_for_review로 인계한다.

## checks / structure / HTML

검사 수 늘리기·mutation·모델 단위 테스트 신규 추가는 목표가 아니다. 산출물에 대한 작은 재실행 가능한 assert 검사만 ignored에 둔다. 정의 수는 파일당7이하/호출 전이4이하, 새 스크립트가 없으면 해당 없음으로 기록한다. 필수 확인:
- 입력 manifest SHA와 전후 원본 해시 동일, 입력 경로 없는 경우 즉시 해당 항목 blocked(합성으로 대체 금지).
- manifest를 coverage_report로 직접 재계산한 실제 결과, private JSON 파싱, split/사진/실물/known/과거 질문 중복 거절, first-round 한도·geometry 선행 조건 검사.
- 사람답변이 없는데 target=0/1 또는 box_reviewed=true인 신규 출력이 생기지 않았는지 확인. 원본 라벨은 참조만 보존하고 새 truth를 생성하지 않는다.
- `git diff --check`, base 대비 allowed_files 정확 대조, 비밀·사진·개인경로 Git 제외, 원본 입력 전후 SHA/권한 확인.
- docs/collaboration/HTML_REPORTING.md 준수. 추적 HTML에는 공개 가능한 집계만, 개인 경로/사진은 ignored review.html에만. 두 HTML을 실제 브라우저로 열고 열기 요청과 렌더 확인을 구별해 기록한다. 새 성능 평가가 없으므로 FN/FP/정확도 개선 주장은 하지 않는다.

## 인계와 경계

커밋은 docs(data): 등 작업에 맞는 형식, git add는 정확4파일만. 전체 SHA/부모/커밋 순서·변경파일·준비 패킷 절대경로/해시·실제 실행결과·미검증·남은 사람 의존·위험·롤백을 인계한다. 브랜치/main merge·push·rebase/reset 금지. 새 학습·추론·외부 AI·자동 검토·수집 API 호출 없음. 독립 작업을 모두 마친 뒤 라벨 답변 없이 A3를 완료했다 하지 않는다. 롤백은 미통합이면 반영하지 않음, 통합 문서는 revert, ignored 패킷은 미사용 보관. 기존 manifest·모델 복구가 필요 없어야 한다.

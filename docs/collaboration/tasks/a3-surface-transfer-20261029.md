# A3 동결 표면 후보 비교

- task_id: a3-surface-transfer-20261029
- owner: Codex
- status: integrated
- base_sha: a956f6b6822b7fe8415a7e7719f4aa8045936d0b
- branch: codex/a3-surface-transfer-20261029
- goal: 동결 A3 val의 확인된 영역에서 기존 두 후보를 같은 ensemble·분모로 비교하고 미지원 geometry를 공개한다. 기존147구역/legacy51/typed51/11cohort를 저장계수로 재생한다. 새학습·정답수정·외부AI0.
- approval: 현재 사용자 승인된 다음 개발·검증 계속 요청과 기존 실험 재개 범위. 개발평가이며 독립시험/운영채택 아님.

## 파일 소유

- tools/experiments/a3-surface-transfer-20261029/data.py
- tools/experiments/a3-surface-transfer-20261029/readout.py
- tools/experiments/a3-surface-transfer-20261029/worker.py
- tools/experiments/a3-surface-transfer-20261029/report.py
- tools/experiments/a3-surface-transfer-20261029/plan.json
- tests/test_a3_surface_transfer.py
- docs/collaboration/tasks/a3-surface-transfer-20261029.md
- docs/collaboration/reports/a3-surface-transfer-20261029.md
- docs/collaboration/reports/a3-surface-transfer-20261029.html
- ignored artifacts/a3-surface-transfer-20261029/ 및 공통 실행기 새 실험 폴더

기존 모델/worker/라벨/자료/소비프로젝트/진척기준/DATA_INVENTORY 수정금지. 구현은 격리 checkout에서 합성검사만. 실제모델 비교는 main에서 ./experiment 안에서 한 번.

## 고정 계약

입력은 이전 NEXT_EVALUATION.json의 모델/백본/cache/자료 SHA. 동일한 head별 sigmoid token확률의 산술평균 후 물리token 최대를 새val에만 적용한다. 앞4head 동일/뒷21head 기존점대비전체점계수만 다르다. threshold .5. RGB224/patch14/기존 DINO revision·정규화·halo0 동일. fit/download/provider 호출 없음. 기존147은 원래 held-fold head로 재생해 최대오차2e-5·판정동일을 요구한다. 새추론 전 앞/뒤1crop 특징을 cache와 비교해 최대오차1e-4 이하를 요구하며 실패 시 즉시 기록하고 중단한다.

C 표면758구역/648점 원래분모를 유지한다. box_reviewed 아닌39구역/5점은 미지원으로 공개하고 추론하지 않는다. 확인된719구역/643점만 별도 비교분모로 표시한다. 관찰제한이 있는 양성도 정답이 있으면 raw평가에 남긴다. unknown은정상으로 만들지 않는다. 사람점은 원래3x3구역crop의 토큰에 매핑하고 같은종류·양성·physicalmask를 검사한다.

비교진전: 같은719구역·643점에서 새오답·새점누락0이고 총오류가 엄격히 감소해야 한다. 품질기준은 앞/뒤각FN<=5%,FP<=10%,점FN<=5%,양/음각20단위·5실물·점20개/5실물이고 미지원이 있으면 전체C3 미충족. 원래11cohort 수치조건과 guard를 유지하며 두기준을 따로 보고한다. 미달 후보를 운영에 채택하지 않는다.

## 구조/검증/인계

신규파일당 최대7함수. module guard→독립 단계 호출; data projection→region_box, point mapping→point_input_pixel, render→side_image→prepared_image 등 신규 프로젝트 함수전이 최대4. torch/PIL callback은 기존 라이브러리 연산이며 사용자정의 callback 추가없음. 합성검사: truth/geometry 분리, 경계점·EXIF·padding 좌표, head평균과max순서, 유한값/shape, 학습ID·group·raw/decoded분리, 실제계수 replay와 원래cohort보호.

code_changes는 실제 실행 byte동일 mirror를 모두 등록한다. HTML은 artifacts 새실험/index.html 사진/구역·점/분모/%p와 docs 동명보고서. 내용대조·열기·렌더 확인상태를 기록한다. file: 보안차단 우회없음. 롤백은 통합SHA git revert·관련검사·일반push, 원본자료/모델과 실패결과는 보존한다. 최신 완료 checkout1개 유지 규칙 적용.

## 구현 검증

새 data/readout/report/worker 함수4/4/2/3, 테스트6함수. source와합성/기존회귀71개OK(6.017초). 최초합성검사의float정확일치·macOS실제경로기대만교정했고모델/수치기준변경0. AST·diff공백검사통과. 주요깊이 features→side_tensor→side_image→prepared_image 3전이, replay_maps→mean_maps 1전이, point_tokens→point_input_pixel/physical_pixel_mask 1전이, render→side_image→prepared_image 2전이. coverage_report는moduleguard에서직접호출해기존4전이유지. 182입력SHA와실제실행mirror4개를공통plan에고정. 실제추론은통합후canonical에서만실행한다.

main dcd39d1 통합·71검사OK·공통실험20261028T203138-7d30f998 completed/acceptancefalse·일반push완료. 실제새val결과/HTML/한계/롤백은동명reports. 사용자7면geometry확인은다음새task로분리하고기존실험보존.

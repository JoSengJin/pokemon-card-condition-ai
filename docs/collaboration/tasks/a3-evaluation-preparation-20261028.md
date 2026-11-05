# A3 동결 자료를 개발 평가 입력으로 연결

- task_id: a3-evaluation-preparation-20261028
- owner: Codex
- status: integrated
- base_sha: 2a2ff1ebaf17ba52b2c72547a44599b1b7f11750
- branch: codex/a3-evaluation-preparation-20261028
- goal: 동결 A3 manifest/coverage SHA를 재대조해 val-only 평가 입력·정답 없는 ListingAnalyzer 요청·C 질문별 분모와 E2 관찰가능 분모를 출력하고, 현재 연구head와의 학습 중복/지원범위를 점검한다.
- approval: 사용자 현재 요청의 다음 승인 개발·검증 지속, 기존 TODO의 source 정합성/매물 지원범위·최종평가 준비. 실제 성능평가에 앞선 입력 검증이며 학습/추론/외부 AI는 실행하지 않는다.

## 파일 소유

allowed_files:
- tools/prepare_a3_evaluation.py
- tests/test_prepare_a3_evaluation.py
- docs/collaboration/tasks/a3-evaluation-preparation-20261028.md
- docs/collaboration/reports/a3-evaluation-preparation-20261028.md
- docs/collaboration/reports/a3-evaluation-preparation-20261028.html
- ignored artifacts/a3-evaluation-preparation-20261028/: 생성 입력/검증/모델 provenance audit/HTML

금지: 기존 소스·Claude 소유파일·사람 라벨·기존 동결 artifacts·모델/worker·소비프로젝트·진척점수/기준·미추적 DATA_INVENTORY 수정. 기본 checkout의 실제 사진 읽기는 직렬 실행하고 구현 checkout에서는 합성 fixture만 쓴다.

## 계약

1. 명시 SHA로 고정한 manifest/coverage를 읽고 기존 coverage_report와 전체 대조한다. 원본 train/val 그룹·사진 분리 검사를 통과해야 한다. test는 기존 투영의 splits 제한으로 읽지 않는다.
2. val 행만 별도 manifest에 보존한다. 제외행은 제외 상태로 보존하고 추론요청에서만 뺀다. 상대 사진 경로는 같은 원본 사진을 가리키도록 절대경로로 정규화하며 라벨/점/분할/그룹은 변경하지 않는다.
3. 요청에는 id·사진·사람확인 box·명시 관찰제한만 전달한다. 라벨·점·split/group은 요청에 전달하지 않으며 unknown 관찰/미확인 geometry를 정상/확인으로 바꾸지 않는다.
4. C의 원래 10셀/실제점·미확인 분모와 E2의 known observable 분모를 분리한다. 기존 truth_cells를 재사용한다. 점수/성능/비보류율은 미측정이고 quality/independent/production 완료 flag는 false다.
5. 입력 변경/새 출력 덮어쓰기 거부. report.json을 완료 marker로 마지막에 저장한다. 실패 시 새 부분 출력이 생길 수 있으나 완료 보고는 없으며 기존 입력·산출물은 덮어쓰지 않는다.
6. 최근 연구 head의 train_ids와 원래 학습 manifest/사진·그룹을 읽기 전용 대조한다. 모델 결합/채택·threshold 변경·val의 학습 편입은 하지 않는다. 실행 가능한 다음 작업은 실제 모델/평가 계약의 근거로 결정한다.

## 구조·검사

신규 도구 함수 최대4개, 테스트 최대7개. prepare→coverage_report→point_rows→validate_annotations→validate_defect_points 최대4전이. prepare→request_for→photo_request→validate_annotations→validate_defect_points 최대4전이. CLI는 module guard에서 prepare 직접 호출.

합성 검사: SHA/coverage 변경·입력변경 거절, train/test 제외와 원본불변, 상대경로 동일사진, unknown/glare/geometry 보존, 정답없는 요청과 원래 양성/정상/실제점 분모 보존, 출력 덮어쓰기 거절. 기존 coverage/listing 관련 회귀 실행. main 통합 후 같은 검사와 실제 동결자료 준비 실행.

HTML: docs/collaboration/reports/a3-evaluation-preparation-20261028.html 및 artifacts/a3-evaluation-preparation-20261028/REPORT.html. 수치/근거 정적대조와 열기/렌더 상태를 기록한다. 이전 file: 보안 차단을 우회하지 않는다.

롤백: 통합 source 커밋 git revert 후 관련 검사·일반 push. 원래 A3 채택본과 모델은 보존한다. 격리 checkout은 검증·push 후 최근1개 보존 규칙을 따른다.

## 구현 검증

신규도구2함수, 테스트7함수(6검사+fixture1). 합성/회귀19+37=56개 OK. 각경로 최대4전이. 원래 freeze 도구의 미종료 open ResourceWarning은 알려진 기존한계이며 이 task에서 수정하지 않았다. 소스만 격리checkout에서 구현했으며 실제 사진/모델 검산은 기본checkout에서만 수행한다. 검증된 후보head의 train IDs는 A3 val group/photo와 중복0, 미해결ID0이지만 아직 새사진 추론/점수는 없다.

main cb5abe3 검증56개OK·실제val100/active99/요청99/E2분모1596생성. 상세검사·한계·롤백은동명reports문서.

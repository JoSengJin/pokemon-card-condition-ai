task_id: frozen-suite-assessment-20261026
owner: Codex
status: integrated
base_sha: 04c1916bf6cf8a04b854a0c858ec71efef0b7687
branch: codex/frozen-suite-assessment-20261026
goal: 같은 봉인/후보/역할별 영수증의 평가보고서만 결속하고 원본 정답·분모를 재대조해 전범위 수치조건과 누락된 증거를 자동 보고한다. 보고서 혼합/중복/정답바꿔치기를 거절한다.
allowed_files:
- card_condition/evaluation_suite.py
- card_condition/evaluation_suite_inputs.py
- card_condition/evaluation_suite_metrics.py
- card_condition/evaluation_suite_cli.py
- tests/test_evaluation_suite.py
- tests/test_evaluation_suite_inputs.py
- tests/test_evaluation_suite_safety.py
- docs/collaboration/tasks/frozen-suite-assessment-20261026.md
- docs/collaboration/reports/frozen-suite-assessment-20261026.md
- ignored artifacts/frozen-suite-assessment-20261026/index.html
forbidden_files: 기존 모든소스/Claude소유파일/원본/라벨/학습/모델/기존실험/진척률/기준/소비서비스/비밀설정
contract:
- 각 역할별 보고서는 원래 저장한 path/SHA256을 명시한다. 사전 고정 후보의 역할별보고서/receipt/hash/seal/checkpoint/threshold/manifest/input_hashes가 일치해야 한다. 가짜독립성·단순 'final'명칭만으로 통과시키지 않는다. 셀 선택은 고정: edge/corner/surface=region_final, centering=side_final, observation=observation_final. 사후 더좋은역할로 교체하지 않는다.
- 원래 sealed manifest의 역할별 projection과 각 prediction ID·정답·group·side·사진·geometry를 대조한다. 누락/추가/중복/바뀐정답 거절. side의 group/side는 기존 row생성 계약으로 복구하며 추측하지 않는다.
- raw .5에서 질문/앞뒤 FN/FP·양성/정상단위와 group수를 다시 계산한다. D2의C수치20단위/5실물, D1각30실물, D3실물사건Wilson10%/20%를 구분한다. 보류분모제외금지·점수None미측정·미확인정답정상화금지.
- 사람 metadata의 language/edition(비어있지않은문자열 또는미확인), annotation.visibility_issues에 따른 촬영제한 하위군 분모와 미확인범위를 공개한다. 이름/사진에서 언어/판본을 추정하지 않는다. source에 없는값은unknown으로만 집계한다.
- 실제점 양성반응은 구역점수와 다르므로 별도실측이 없으면 unmeasured로 남긴다. 품질/독립성의 별도근거를 가정하지 않고 d1/d2/d3_verified 및 production_ready=false, progress불변.
- 입력/기존결과를 수정하지 않고 신규보고서만 atomic no-overwrite. 학습·모델추론·외부AI0(체크포인트metadata torch.load만 사용). 합성fixture/mock보고서로검증.
structure: 각 신규파일함수<=7. main→assess_suite→matched_reports→read_candidate→file_sha256=4전이; main→assess_suite→projection→load_manifest=3전이; main→assess_suite→physical_uncertainty→event_summary→wilson_upper=4전이. projection/불확실성호출을 별도wrapper로 감싸지않는다.
checks: 보고서혼합·정답/geometry변경·누락/중복·잘못된영수증·잘못된rawmetrics거절, 부분지원/빈분모/미측정·하위군unknown·저장보존 합성검증, AST/diff/HTML/main/push.
experiment: 불필요, 저장자료 읽기 및 합성검사만.
handoff: 실제검사·변경·미검증·위험·롤백·HTML을 완료후기록.

최종검사: main3553c49+fixture3c08a2b+schema3d935ee. 합성/mock44개PASS·compileall/diff PASS. 함수1/2/3/1 및검사7/6/4. 실제품질/독립검증미실행·진척30유지. 보고서와HTML/롤백은 reports/frozen-suite-assessment-20261026.md.

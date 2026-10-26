task_id: observation-evaluation-model-sha-20261026
owner: Codex
status: integrated
base_sha: 5023444f7e0b8b2259b4317c33240fc6405782b8
branch: codex/observation-evaluation-model-sha-20261026
goal: 관찰독립평가에서도구역/면별평가와같이실제로로드한analyzer.model_sha256을사전고정checkpointSHA와대조하여다른모델의점수를정상후보로기록하지못하게한다.
allowed_files:
- card_condition/observation_heldout.py
- card_condition/evaluation_inputs.py
- tests/test_observation_evaluation_model_sha.py
- tests/test_observation_heldout.py
- tests/test_physical_uncertainty_evaluation.py
- tests/test_frozen_test_evaluation.py
- tests/test_frozen_candidate_evaluation.py
- tests/test_evaluation_suite.py
- docs/collaboration/tasks/observation-evaluation-model-sha-20261026.md
- docs/collaboration/reports/observation-evaluation-model-sha-20261026.md
- ignored artifacts/observation-evaluation-model-sha-20261026/index.html
forbidden_files: 다른소스/실checkpoint·사진·정답/학습실행/기존기록/진척·기준/소비서비스/Claude소유파일
contract:
- 기존matched_model helper를VisibilityAnalyzer생성직후/사진analyze전에호출한다. 고정파일SHA초기·종료검사와새로드바이트SHA를연결한다. 필드/점수/정답/threshold/정책은유지한다.
- modelSHA불일치면ValueError, 결과파일미생성, 실제사진추론0. sealedclaim이이미생겼다면보존하고같은시험자동재시도를막는다. 기존CLIJSON오류계약유지.
- 정상mock은실제checkpointSHA를명시하도록기존fixture만보완한다. 본문조건을무력화하는patch는금지한다. 실제학습하는legacy테스트는이번에실행하지않으며추론전guard/정상대조는별도minimal metadata합성fixture로검증한다.
structure: observation_heldout1→1, 기존검사함수수유지, 신규검사<=7. 기존helper재사용으로main→evaluate_heldout→matched_model2전이,새wrapper없음.
checks: 수정전wrong loadedSHA를허용하고4개analyze후정상checkpointSHA보고재현. 수정후wrongSHA/correctSHA/CLI/claim보존·재시도거절, 기존97회귀(legacy실학습모듈제외)/AST/diff/HTML/main/push. 실사진추론·새학습·외부AI0.
experiment: 없음,합성입력/mock로딩검사만.
handoff: 실제검사/미실행legacy학습/리스크/롤백/원격상태기록.

계약보완(같은모델식별경계): 공유matched_model이alias경로변경으로고정hashmap의키를찾지못하면KeyError로CLI계약을깨는반례를확인했다. missing expected SHA는동일ValueError로거절하며어떤다른hash도추정하지않는다. evaluation_inputs함수5→5유지, 임시symlink교체회귀추가.

완료: mainc37dd49+공유guard975ed95.102개합성회귀PASS/compileall/diff PASS. 함수source1/5·신규검사6,oldmock정확한SHA명시. actuallegacy학습/실사진추론/외부AI0. 리스크/롤백/HTML은 reports/observation-evaluation-model-sha-20261026.md.

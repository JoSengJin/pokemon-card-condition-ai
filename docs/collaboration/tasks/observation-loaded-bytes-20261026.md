task_id: observation-loaded-bytes-20261026
owner: Codex
status: implementing
base_sha: 13e4e8fb632e3b0de64c63121886a8d76ecdc2d0
branch: codex/observation-loaded-bytes-20261026
goal: 관찰모델의가중치로드/SHA계산을같은바이트로묶고, 변경파일함수최대7개를지키도록본문변경없는최소책임분리를한다.
allowed_files:
- card_condition/visibility_model.py
- card_condition/observation_fitting.py
- card_condition/observation_side_diagnostics.py
- tests/test_observation_loaded_bytes.py
- docs/collaboration/tasks/observation-loaded-bytes-20261026.md
- docs/collaboration/reports/observation-loaded-bytes-20261026.md
- ignored artifacts/observation-loaded-bytes-20261026/index.html
forbidden_files: 나머지소스/데이터/라벨/학습실행/기존실험/기준/진척/소비서비스/Claude소유파일
contract:
- visibility_model의class_group_weights/fit_centroid/fit_side_centroids 3함수와side_diagnostics 1함수만별도파일로이동한다. AST본문을기준SHA와대조하여수학·조건·분모가동일함을확인한다. 기존visibility_model이이름을re-export하여학습/평가호출자의import를유지한다.
- VisibilityAnalyzer/observation_features/observation_logits/experiment는기존module namespace에유지하여기존patch대상과호출방식을보존한다. 새wrapper/호출깊이추가금지.
- 관찰checkpoint는Path.read_bytes의snapshot을torch.load(BytesIO,weights_only=True)로deserialize하고같은snapshotSHA를보고한다. 아키텍처/관찰점수/보류정책/전처리/파일checkpoint스키마는불변.
- visibility_model 함수11→7, 신규fitting3/diagnostics1, 신규검사<=7. import순환없음확인. release·source pin은변경소스를검출하므로기존test후보를자동재핀해재실행하지않는다.
checks: mock가중치적용중파일교체반례·기존함수export·모듈구조/본문동일성·finite_logits합성tensor검사·기존50개회귀·AST/diff/HTML/main/push. 실제사진추론·새학습·외부AI0. 실모델성능/일반화개선미주장.
experiment: 없음. 이동은기존본문동일성검사, 모델수정은deserialize무결성회귀만수행한다.
handoff: 실제검사/미실행/리스크/롤백/HTML을완료시기록.

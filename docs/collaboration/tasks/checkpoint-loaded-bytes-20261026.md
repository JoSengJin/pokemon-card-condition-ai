task_id: checkpoint-loaded-bytes-20261026
owner: Codex
status: implementing
base_sha: fb9d9cd62e4b20e3f4a751fc64a40cf7e6e6112c
branch: codex/checkpoint-loaded-bytes-20261026
goal: RegionAnalyzer/SideAnalyzer가 실제deserialize한checkpoint바이트의SHA를보고하게하여,로드중파일교체가다른모델을정상SHA로식별하지못하게한다.
allowed_files:
- card_condition/region_model.py
- card_condition/side_model.py
- tests/test_checkpoint_loaded_bytes.py
- docs/collaboration/tasks/checkpoint-loaded-bytes-20261026.md
- docs/collaboration/reports/checkpoint-loaded-bytes-20261026.md
- ignored artifacts/checkpoint-loaded-bytes-20261026/index.html
forbidden_files: 다른소스/라벨/원본/기존실험/진척/기준/소비서비스/Claude소유파일
contract:
- Path.read_bytes로한번읽은immutable bytes에서torch.load(BytesIO,weights_only=True)와SHA를계산한다. point아키텍처의추가load_probe_model에도같은바이트를전달한다. 기존path입력/metadata/모델계층/점수/보류/API결과는유지한다.
- 새로운snapshot helper나전체CLI catch를추가하지않는다. modulefunction수 region2→2/side4→4, 호출깊이불변(기존load_probe_model은filelike를torch.load에전달하므로수정불필요).
- visibility_model.py는기존함수11개로이번작업에서수정하지않는다. 관찰모델의동일종류SHA결속한계는남은의존으로명시하며전릴리스검증완료를주장하지않는다. 기능분리/훈련코드대규모이동은별도수술적계약이필요하다.
- 모델로딩중경로를교체하는mock반례로수정전실패/수정후통과, 일반구역/point/side모두확인. actualmodel forward·학습·외부AI0. 기존합성/mock회귀와diff/AST/HTML/main/push.
structure: 신규test파일함수<=7, 기존region2/side4유지. 기존생성경로wrapper추가없음.
experiment: 없음, 저장바이트무결성검사이며성능평가가아니다.
handoff: 완료후실제검사/잔여관찰모델한계/메모리리스크/롤백기록.

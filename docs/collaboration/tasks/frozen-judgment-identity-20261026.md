task_id: frozen-judgment-identity-20261026
owner: Codex
status: integrated
base_sha: 43c6a44e27eba314fe32c11e6889a1f0e0780f67
branch: codex/frozen-judgment-identity-20261026
goal: 독립평가의동일사진/구역/질문이alias ID로중복계수되거나동일픽셀사진이앞뒤로모순배정되는것을숫자판정전에거절한다.
allowed_files:
- card_condition/frozen_test.py
- card_condition/evaluation_suite.py
- card_condition/evaluation_suite_inputs.py
- tests/test_evaluation_suite.py
- tests/test_frozen_judgment_identity.py
- docs/collaboration/tasks/frozen-judgment-identity-20261026.md
- docs/collaboration/reports/frozen-judgment-identity-20261026.md
- ignored artifacts/frozen-judgment-identity-20261026/index.html
forbidden_files: 다른소스/실manifest/사진/정답/모델/기존기록/진척/기준/소비서비스/Claude소유파일
contract:
- seal_test는실제로드한decoded사진이두면으로배정되면봉인전에거절한다. excluded행은새side검사에서제외하고원래바이트추적/개발중복거절은그대로유지한다.
- assess_suite는source manifest의card_id→side→decodedSHA를checked_predictions에전달한다. q별정답이알려진단위의(decodedSHA,side,area또는face,question)가다른ID에서반복되면거절한다. 중복소스의box가달라도자동label전이/합산하지않는다.
- 서로다른사진,다른구역,다른질문은별도단위로유지한다. 미확인정답은정상으로세지않으며같은사진의비중복질문/미확인행을무조건삭제하지않는다. 정답/분모를자동dedup해결하지않고원본중복을오류로남긴다.
- 바이트봉인은모든평가projection의수량감사를대신하지않는다. alias포함manifest가봉인되더라도수치판정은중복known unit을거절한다. D1인증false유지. 기존직접평가기/라벨/모델추론은수정하지않는다.
structure: 기존frozen_test3/suite1/inputs2유지, 기존suite검사7유지(합성fixture옵션만추가), 신규검사<=7함수. 추가wrapper/호출전이없음.
checks: 수정전동일사진alias봉인가능·동일1사진/구역이TP2계수재현. duplicateknown labels/다른geometry/앞뒤모순거절,서로다른q/unknown/다른영역허용, 실제봉인/assessment경로합성검증·기존91회귀/AST/diff/HTML/main/push. 실사진추론·새학습·외부AI0.
experiment: 없음. 합성source/report검증만.
handoff: 실제검사/도입영향/정답보존/롤백기록.

완료: main91b8647.97개합성회귀PASS/compileall/diff PASS. 함수3/1/2및검사7/7유지. 실제정답/원본/사용이력불변·실사진추론/학습/외부AI0. 도입영향/롤백/HTML은 reports/frozen-judgment-identity-20261026.md.

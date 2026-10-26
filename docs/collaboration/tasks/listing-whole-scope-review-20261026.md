task_id: listing-whole-scope-review-20261026
owner: Codex
status: implementing
base_sha: aa119eab4f4e0fc6386c196ef8b01560973e6114
branch: codex/listing-whole-scope-review-20261026
goal: 기존42개구역검토에앞뒤센터링/관찰제한4개사람확인항목을추가하고전체질문검토상태를분리기록한다. 모델보류/관찰제한을결함으로혼동하지않는다.
allowed_files:
- card_condition/listing_review.py
- tests/test_listing_review_whole_scope.py
- docs/collaboration/tasks/listing-whole-scope-review-20261026.md
- docs/collaboration/reports/listing-whole-scope-review-20261026.md
- ignored artifacts/listing-whole-scope-review-20261026/{index.html,demo.html,fixture inputs}
forbidden_files: 다른소스/Claude진행소스/실원본/라벨/기존실험/모델/진척/기준/소비서비스/비밀설정
ownership: 이전Claude listing-review-evidence task tip5bdf0ec의main cherry-pick대응이확인되었고이후변경없음. 새소유권은Codex의이task로한정한다. 데이터확보소스는건드리지않는다.
contract:
- 모델출력42구역/score/상태/보류이유·전체blockers는그대로유지한다. 추가4항목은area=face의사람감사항목이며모델score=None/state=unknown으로표시한다.
- 센터링은기존검토decision의의미를표시한다. 관찰제한은confirmed_limited/confirmed_observable/undecidable만허용하고손상·정상용corrected_defect/normal을재사용하지않는다. 사진/영역누락이면undecidable/blank만허용한다.
- 내보내기face_decisions는정확한report SHA에결속한다. 새입력은4항목각1회·알려진decision만수용한다. legacy입력에필드가없으면기존region review_completed 의미/집계를유지하되full_scope_review_completed=false로표시한다. region_review_completed와face_review_completed를별도공개한다.
- 새face집계는기존counts·pilot정정량과섞지않는다. ground_truth/used_for_training/changes_model_verdict=false유지. 전체질문검토완료는모델전체완료/70%coverage/E2기준통과를뜻하지않는다.
- 공개함수수listing_review6→7, 새helper1개이하, 호출전이기존경로에최대1추가·전체4이하. 새프레임워크/서버제품/의존성추가없음.
checks: 합성사진·고정fixture결과로4항목표시/관찰의미/legacy호환/부분검토/중복·정답종류오류·누락사진정상거절/escape/CLIrecord, 기존listing_review*와관련57개회귀. 기존검사에무작위합성checkpoint추론포함가능하며실사진추론·새학습·외부AI0. demo만127.0.0.1정적서버로노출하여CUA의DOM/화면/내보내기JS확인후서버종료한다(외부네트워크/터널없음).
experiment: 없음. 실제모델성능평가/비교아님.
handoff: 실제검사/화면확인/리스크/롤백/원격동기화를완료후기록.

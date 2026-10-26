# E2 전체 사진 질문 검토 · 센터링/관찰 제한

전체진척30/100 (usable-card-analysis-v1.0, 변화0%p). 기존구역검토와별도로앞뒤센터링/관찰제한4개사람감사항목을추가했다. E2의70%coverage·실제사용완주·모델성능은평가하지않았다.

## 변경 / 계약
- card_condition/listing_review.py: whole_face_cells를추가(함수6→7). 기존42개구역의모델score/state/보류이유와전체blockers를유지한다. 추가4개질문은area=face, state=unknown, score=None이며사람검토만기록한다. 관찰제한은confirmed_limited/confirmed_observable/undecidable로구분하고손상정정용decision을재사용하지않는다. 사진/카드영역누락은판단불가만허용한다.
- HTML은42개기존행과4개수동행을별도table로표시하고별도face_decisions를내보내도록구성한다. 원래report SHA에결속하고새입력은4항목각1회/정확한decision만받는다.
- legacy입력의review_completed와counts는기존42구역의의미를그대로유지한다. region_review_completed/face_review_completed/full_scope_review_completed를별도로보고한다. face_counts는pilot정정량에섞지않는다. ground_truth/used_for_training/changes_model_verdict는false이고새face값도모델판정이아니다.
- tests/test_listing_review_whole_scope.py (7함수): 표시·정답종류·legacy/부분검토·중복/누락·사진없는정상거절·SHA/escape·CLI기록6개회귀. task/본보고서추가. 모델·라벨·데이터·진척·소비서비스변경없음.

## 실행 근거
검증소스SHA 28f31354e9df324cb11cc04dcc287d2b0299d92a.
CPU torch.set_num_threads(1)로 unittest모듈 test_listing_review_whole_scope/test_listing_review/test_listing_review_evidence 및기존관찰·로드바이트·릴리스·finite_logits·frozen_candidate/frozen_test/evaluation_suite/physical_uncertainty/evaluation_inputs 검사를실행했다:71개PASS(5.254초). 신규6+기존listing8+관련57. 기존listing검사에는합성무작위checkpoint의실제추론이포함된다. 실사진추론·새학습·외부AI0, 모델성능개선주장없음. 전체suite미실행.
compileall소스1/신규검사1, diff --check PASS. 새주요경로 main→review_page/review_record→whole_face_cells2전이, 기존evidence_view/recall/사진경로유지. 새wrapper/재귀없음.

## 브라우저 확인 / 차단된 검사
합성데모 demo.html만127.0.0.1 임시포트64689로제공했다. CUA로접근성·DOM에서42개구역/4개추가질문, 관찰제한의다른선택지, 누락뒷면의판단불가전용선택지를확인했다.42개구역과4개수동항목선택도DOM에서확인했다. 스크린샷으로사진위구역/누락뒷면/추가질문표배치를확인했고viewport812px/documentWidth812px로가로넘침없었다. 모바일375px은미검증이다.
JSON다운로드대기API가브라우저권한거절(user declined)로차단되었다. 내보내기버튼click까지도실행되지않았고status문구는빈문자열이었다. 실제브라우저파일다운로드/내보내기JS실행성공/다운로드파일CLI결속은미검증이다. 같은다운로드를우회/재시도하지않았다. 로컬단위/CLI기록검사는이권한거절전에완료한별도검증이다.
읽기전용화면확인후임시탭을닫고HTTP서버를SIGINT로종료했다(exit130, 의도한정리). 외부주소/터널/실자료노출없음.

## 리스크 / 남은 조건
- 전체질문review완료는사람이모든항목을검토했다는감사상태다. 판단불가/사진누락도검토메모를남길수있으므로모델완료·관찰가능·정상·학습정답이나E2통과를뜻하지않는다.
- 기존review_completed는region범위를유지한다. 전체질문완료가필요한소비자는새full_scope_review_completed를확인해야한다. strictJSON소비자는추가필드에대응해야할수있다. face_counts와모델정정counts는서로다르다.
- 센터링/관찰제한의실제모델판정은계속보류한다. 동결자료의알려진관찰가능필수셀에대한비보류coverage≥70%는별도실측이필요하다. 새사람라벨을저장하거나기존완료라벨을다시요청하지않았다.
- 실제브라우저다운로드는사용자권한거절로미검증이며추가승인없이재시도하지않는다.
롤백: 진행중실행없을때 `./develop -- git revert 28f3135`. 만들어진검토기록은감사자료로보존한다. 기존모델/정답복원불필요.
성과HTML artifacts/listing-whole-scope-review-20261026/index.html, 합성제품demo.html. 성과HTML열기응답은제품demo의화면확인과구분한다.

성과HTML파일열기응답은Codex browser queued이며이파일자체의렌더는미확인. 합성제품demo.html의CUA실제화면확인은위기록대로완료했다.

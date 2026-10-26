# 독립평가 판정단위의 사진·면·구역·질문 정합성

전체진척30/100 (usable-card-analysis-v1.0, 변화0%p). alias ID로같은판정단위를중복계수하는것을막고동일사진의앞뒤모순을거절했다. 실제모델성능·독립시험·진척점수상향미평가.

변경파일: card_condition/frozen_test.py, evaluation_suite.py, evaluation_suite_inputs.py, tests/test_evaluation_suite.py, 신규test_frozen_judgment_identity.py 및task/보고서.
핵심diff: seal_test는현재test의nonexcluded decoded사진에한면만배정하도록검사한다. assess_suite는원본card_id→side→decodedSHA를projection검증기에전달한다. 알려진필수질문의(decodedSHA,side,area/face,question)가다른ID에중복되면오류다. box가달라도자동라벨전이·합산하지않는다. 서로다른사진/구역/질문과미확인행은유지한다. 새wrapper나정답/분모자동수정은없다.

수정전재현: 같은사진의alias record를봉인할수있었고, 같은한사진/구역/질문을다른ID로두번주면TP2로집계됐다. 바이트봉인은원래projection수량감사까지보장하지않는다. 수정후숫자판정기는중복known unit을거절하고실제sealer는같은픽셀의앞뒤배정을거절한다.

검증코드SHA 91b86479fb74732c551fe400301af8242eb0dbb4.
CPU torch.set_num_threads(1)로신규test_frozen_judgment_identity와기존pilot/검토/로드바이트/관찰/릴리스/finitelogit/frozen/evaluation_suite/physical_uncertainty/evaluation_inputs를실행:97개PASS(8.023초), 신규6+기존91. 수정전duplicateknown회귀는ValueError미발생으로실패했으며수정후통과했다. 합성source/renderedreport/metadata/mock모델만사용했고기존pilot/listing회귀의무작위합성checkpoint추론을포함한다. 실사진추론·새학습·외부AI0. 전체suite미실행.
- 실제manifest/후보/3개사용영수증/저장보고서경로에서alias projection거절, 결과파일미생성, source바이트·기존사용영수증보존확인.
- 같은사진의다른질문/unknown행은그대로유지되고unknown을정상/추가양성으로세지않음.
- compileall변경소스3/수정검사1/신규검사1, diff --check PASS. 함수frozen_test3/suite1/inputs2유지, 기존검사7/신규검사7. 호출wrapper/전이추가없음.

리스크: 과거에ID만달리해중복저장한자료는새판정기에서거절될수있다. 이수정은어떤정답을고를지결정하지않으며원본중복/geometry정합성감사뒤새manifest를동결해야한다. 완료한사람라벨을재요청하거나자동삭제하지않았다.
같은사진에다른box로다시그린알려진같은질문은독립단위로두번세지않는다. 출처·실물그룹이실제로같은카드인지,안보이는결함·미확인면정답은자동판단하지않는다. excluded행의바이트/개발history검사는기존대로유지하며새side검사만nonexcluded대상이다.
기존직접평가기의원래동작은바꾸지않았다. 새숫자판정기는alias중복을거절하지만바이트봉인만으로A3/D1수량충족·사용미사용·실제점정확도등을인증하지않는다. d1/d2/d3_verified=false유지.
롤백: 진행중작업없을때 `./develop -- git revert 91b8647`. 원본/라벨/사용영수증은그대로보존한다. source pin변경후이미사용한시험을자동재핀해재사용하지않는다.
HTML artifacts/frozen-judgment-identity-20261026/index.html 생성·97검사/SHA/30점/리스크/롤백내용대조. 브라우저다운로드재시도없음. 성과파일열기응답과실제렌더는구분한다.

성과파일열기요청은queued,실제렌더미확인.

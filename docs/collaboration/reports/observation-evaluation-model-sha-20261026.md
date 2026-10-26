# 관찰독립평가의 실제 로드 모델 SHA 대조

전체진척30/100 (usable-card-analysis-v1.0, 변화0%p). 실제로드모델과사전고정후보를관찰평가에서도연결하고alias변경을검증오류로처리했다. 실제모델품질·독립시험통과미평가.

변경: card_condition/observation_heldout.py는VisibilityAnalyzer생성직후/사진analyze전에기존matched_model을호출한다. evaluation_inputs.py의공유guard는경로alias가바뀌어expected hash키가없으면기존ValueError로거절한다(임의SHA추정없음). 모델점수/정답/임계값/정책/결과필드는유지한다.
신규tests/test_observation_evaluation_model_sha.py는wrong/correctSHA·CLI오류·sealedclaim보존/재시도거절·임시symlink교체를검사한다. 기존observation_heldout/physical_uncertainty_evaluation/frozen_test_evaluation/frozen_candidate_evaluation/evaluation_suite의정상mock은실제checkpointSHA를명시하도록보완했다. guard를우회하는patch는추가하지않았다. task/본보고서추가.

수정전재현: 고정checkpoint와다른model_sha256의mock관찰모델을허용하여4개사진analyze후정상후보SHA를보고했다. alias교체시공유guard는KeyError로종료했다. 수정후wrongSHA는analyze0/결과파일미생성/CLIstdoutempty·exit1·JSON오류이며alias도ValueError다. sealedclaim은보존되어동일시도재실행이차단된다. 정상SHA대조군은4개합성입력점수를기존형식으로저장한다.

검증코드SHA 975ed958d511417cc29a59e6efab468cb641f3e5.
CPU torch.set_num_threads(1)로신규test_observation_evaluation_model_sha와이전frozen_judgment_identity/pilot/검토/로드바이트/관찰/릴리스/finitelogit/frozen_candidate/frozen_test/evaluation_suite/physical_uncertainty/evaluation_inputs를실행:102개PASS(8.058초), 신규5+기존97. 기존pilot/listing회귀에무작위합성checkpoint추론포함, 실사진추론·새학습·외부AI0. 실제학습fixture를사용하는legacy test_observation_heldout 전체는이번에실행하지않았다(정상mock1줄/compile검사만). 전체suite미실행.
compileall소스2/검사6, diff --check PASS. 함수observation_heldout1/evaluation_inputs5/신규검사6, 기존검사함수수유지(각7이하). main→evaluate_heldout→matched_model2전이, 새wrapper없음.

리스크: 실제클래스는기존부터model_sha256을제공하므로정상API호출은같다. custom mock은정확한SHA를명시해야한다. alias가바뀌면다른대상을추정하지않고보수적으로거절한다. 이미봉인claim이생긴뒤모델불일치면실제추론0이어도시도기록을남기고자동재시도하지않는다. 오류수정이지데이터독립성/질·전체수용조건충족의증거가아니다.
롤백: 실행중작업없을때 `./develop -- git revert 975ed95 c37dd49`. 입력/원본/정답/사용영수증은보존한다. 새mockSHA명시와legacyfixture변경도해당커밋으로복원된다.
HTML artifacts/observation-evaluation-model-sha-20261026/index.html 생성·102검사/SHA/30점/리스크/롤백대조. 브라우저다운로드를재시도하지않았다. 파일열기응답과렌더확인은구분한다.

성과파일열기요청은queued,실제렌더미확인.

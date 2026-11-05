# 관찰모델 동일 로드바이트 SHA와 함수수 제한

전체진척30/100 (usable-card-analysis-v1.0, 변화0%p). 관찰모델도실제로deserialize한checkpoint바이트의SHA를보고하게했다. 모델성능/일반화개선은미평가, F1pending.

변경: card_condition/visibility_model.py, 신규observation_fitting.py/observation_side_diagnostics.py, tests/test_observation_loaded_bytes.py, task/본보고서.
핵심diff: 기존함수수11개를7개로맞추기위해class_group_weights/fit_centroid/fit_side_centroids3함수와side_diagnostics1함수를각각응집된파일로이동했다. legacy visibility_model은동일이름을re-export한다. VisibilityAnalyzer/experiment/observation_features/observation_logits는기존namespace에남겨기존import·patch·학습호출을보존했다. 모델은Path.read_bytes로한번읽은snapshot의BytesIO를torch.load(weights_only=True)에주고동일snapshotSHA를계산한다.

검증소스SHA 9e361e2f5d3b3b3a39f1549e789f8f4c1ff98467.
`PYTHONPATH=tests .venv/bin/python -m unittest test_observation_loaded_bytes test_checkpoint_loaded_bytes test_release_null_entries test_finite_logits test_frozen_candidate test_frozen_candidate_evaluation test_frozen_test test_frozen_test_evaluation test_evaluation_suite_inputs test_evaluation_suite test_evaluation_suite_safety test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs`:57개PASS(2.107초), 기존50+관찰3+finite_logits4. 전체suite미실행. 새실사진추론·학습·외부AI0. finite_logits는합성tensor의작은선형head출력으로NaN/Inf거절을검증했다(실모델성능측정아님).
- 가중치적용중파일교체mock에서관찰SHA는최초deserialize바이트와일치하고교체파일과다르다.
- 네이동함수는13e4e8f기준AST와각각완전동일(include_attributes=False), 수학/분모/조건변경없음.
- 공개함수alias, training함수global, class/featuremodule경로, 기존featurepatch와interior좌표불변검사통과.
- compileall변경소스3/신규검사1, diff --check PASS. 함수visibility7/fitting3/diagnostics1/신규검사4. 새wrapper/재귀/호출전이추가없음.

리스크: 함수정의module위치가바뀌나legacy이름은같은객체로노출한다. 외부사용자가이동한함수의privateglobals를monkeypatch하는행위까지호환보장하지않는다. 기존프로젝트의feature/finite-logitpatch경로는유지·검증했다. 새학습을실행하지않았으므로실학습재생결과는이번턴검증범위가아니다(본문동일성과호환만확인).
전체checkpointbytes의임시메모리비용은미계측이다. 코드파일목록/SHA가바뀌므로이전동결candidate는의도대로거절된다. 이미쓴시험을새핀으로재사용하지않는다.
이작업과이전region/side수정으로세역할의실제로드바이트SHA결속경로를마쳤지만, 품질통과후보·승인소비경로·깨끗한설치/복구등F1전체완료는여전히미충족이다.
롤백: 진행중실행없을때 `./develop -- git revert 9e361e2`; 원본/라벨/모델파일을복원할필요는없다. 다시관찰SHA재읽기문제가돌아오므로해당회귀가실패한다.
HTML artifacts/observation-loaded-bytes-20261026/index.html 생성·57검사/SHA/30점/리스크/롤백대조. 화면렌더는열기응답과구분한다.

HTML열기: Codex browser queued, 실제화면렌더미확인.

# 실제 로드한 checkpoint 바이트와 model SHA 결속

전체 진척률30/100 (usable-card-analysis-v1.0, 변화0%p). 이번성과는구역/면별분석기의실제로드내용식별보완이다. 모델성능·속도변화미평가, F1pending.

변경: card_condition/region_model.py, card_condition/side_model.py, tests/test_checkpoint_loaded_bytes.py 및task/보고서.
핵심diff: checkpoint를한번읽은bytes에서torch.load(BytesIO,weights_only=True)와SHA를계산한다. 구역의point아키텍처도같은snapshot을기존load_probe_model에전달한다. 모델구조/전처리/점수/외부API/weights_only는불변이며새helper를추가하지않았다.

수정전재현(합성metadata·mockbackbone/head): state_dict를적용하는사이에경로를교체하면 region/side모두 reported_matches_loaded_bytes=False, reported_matches_replacement=True였다. 실제로드한모델과보고SHA가불일치했다.
수정후: 경로를교체해도최초deserialize한bytes의SHA와일치하고교체파일SHA와는다름을확인했다. point경로는실제load_probe_model을호출하고backbone/head만mock하여BytesIO호환·같은snapshot전달을확인했다. 잘못된snapshot은backbone로딩전에거절한다.

검증코드SHA 572a70bd14b40faa27738488b423903506ea8352.
`PYTHONPATH=tests .venv/bin/python -m unittest test_checkpoint_loaded_bytes test_release_null_entries test_frozen_candidate test_frozen_candidate_evaluation test_frozen_test test_frozen_test_evaluation test_evaluation_suite_inputs test_evaluation_suite test_evaluation_suite_safety test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs`:50개PASS(2.183초), 신규3/관련47. 전체suite미실행. 학습·실사진추론·모델forward·외부AI0, 실제checkpoint deserialize와mockstate_dict적용만수행했다.
compileall변경소스2/신규검사1, diff --check PASS. 함수수 region2→2/side4→4/신규검사7, 호출wrapper추가없음.

리스크: 초기화중checkpoint전체bytes를보유하므로파일크기만큼임시메모리사용이늘수있다(미계측). 이후학습/추론성능/정확도개선은주장하지않는다. 경로가로드후바뀌어도실제로로드한snapshot을보고한다는의미다.
남은한계: visibility_model의관찰모델은아직경로를재읽어SHA를계산한다. 기존함수11개라구조기준내의분리계약없이한줄만수정하지않았다. 전릴리스세역할의바이트결속완료를주장하지않으며후속분리·수정을필요의존으로남긴다.
롤백: 진행중실행없을때 `./develop -- git revert 572a70b df72abf`. 원본/라벨/모델파일변경없음. 로드SHA회귀가돌아오므로원래50개검사의해당3개가실패할수있다.
HTML artifacts/checkpoint-loaded-bytes-20261026/index.html 생성·50검사/SHA/30점/리스크/잔여의존/롤백내용대조. 실제렌더상태는별도로기록.

HTML: Codex browser 열기는queued응답이며실제화면렌더는미확인이다.

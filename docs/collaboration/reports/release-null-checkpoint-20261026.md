# null checkpoint를 기존 CLI 오류 계약으로 거절

전체 진척률 30/100 (usable-card-analysis-v1.0, 변화0%p). 이번 성과는 릴리스 실패입력의 uncaught KeyError 수정이다. F1pending, 모델품질미평가.

변경 파일: card_condition/release.py, tests/test_release_null_entries.py, task/본보고서.
핵심 diff: read_release의 optional생략 판정을 entry is None에서 role not in checkpoints로 바꿨다. 키가없으면생략, 선언된값은기존file/sha256 object검사를받으므로null은ValueError가된다. 함수수3→3, 호출깊이불변. 신규검사는4함수다.

재현: 수정전합성 region:null manifest로 uncaught KeyError 'region', model_load_calls0. 회귀검사는 region/observation/recall null3경우모두ValueError가없어실패했다. 수정후세경우모두CLI exit1/stdoutempty/stderrJSON requires_gemini=true 및모델로딩0이다. optional관찰/recall생략과정상명시·SHA불일치거절은유지된다.

검증코드SHA 66fd35cb243ea6c553e194f3d13f939597026e66.
`PYTHONPATH=tests .venv/bin/python -m unittest test_release_null_entries test_frozen_candidate test_frozen_candidate_evaluation test_frozen_test test_frozen_test_evaluation test_evaluation_suite_inputs test_evaluation_suite test_evaluation_suite_safety test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs`:47개PASS(2.029초), 신규3/관련44. 학습·실사진추론·외부AI0, null입력에서는모델로딩0. 기존test_release.py의실제무작위모델추론검사와전체suite는이번에재실행하지않았다.
compileall/release와신규검사, diff --check PASS.

리스크: optional역할을없애려면키를생략해야한다. 이전에 observation:null/recall:null을사용하던입력은명시적으로거절된다. 정식계약의optional object형식에맞춘변경이다. 기존유효릴리스/정답/모델/정책은변경없다. 이오류처리수정은품질통과릴리스와소비경로·복구완료를뜻하지않는다.
롤백: 실행중작업없을때 `./develop -- git revert 66fd35c`. 신규null회귀가다시실패하는것은원래결함의복원이다. 원본/라벨/모델복구불필요.
HTML artifacts/release-null-checkpoint-20261026/index.html 생성/47검사·SHA·30점·리스크·롤백내용대조. 열기와렌더는별도기록.

HTML 열기: Codex browser queued, 실제렌더미확인.

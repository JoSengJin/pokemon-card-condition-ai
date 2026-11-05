# D1/D2 입력 봉인·시험 사용기록

전체 진척률 30/100 (usable-card-analysis-v1.0, 변화0%p). 이번 성과는 시험 입력 무결성·재사용 차단 구현이다. D1/D2는 pending이며 실제 모델 품질을 측정하지 않았다.

## 변경 파일 / 핵심 diff
- card_condition/frozen_test.py: 기존 test-only manifest와 제공 history의 ID/group/decoded사진 중복을 거절하고 manifest·사진·정답·group SHA를 새 JSON에 봉인한다. SHA를 명시한 평가에서는 모든 입력을 재검증하고, checkout별 ledger에서 이미 사용한 group/사진은 봉인복사·재봉인·모델교체·평가기변경에도 재사용을 막는다. flock과 no-overwrite atomic 파일로 동시claim을 직렬화한다.
- card_condition/frozen_test_cli.py: `python -m card_condition.frozen_test_cli TEST SEAL --history HISTORY` (여러 history 반복). 성공시 seal_sha256 출력. d1_verified/d2_verified false.
- card_condition/{region_evaluation,side_evaluation,observation_heldout}.py: 선택 keyword-only test_seal/test_seal_sha256. 기존 호출은 no-op. 추론 직전에 exposure_claimed를 영속하고 보고서에 영수증 SHA를 넣는다. 이후 오류가 나도 사용이력은 남겨 재시도를 차단한다.
- card_condition/cli.py: 세 평가 명령의 --test-seal/--test-seal-sha256 전달. side regression에서 봉인 사용은 거절한다.
- tests/test_frozen_test.py, tests/test_frozen_test_evaluation.py: 봉인복사·모델변경·재봉인·group만/사진만중복·동시2요청·변조·기존손상영수증·추론로딩실패·세평가기·공용CLI·출력보존 검증.
- task/본보고서. 데이터·라벨·학습·기준·진척점수·소비프로젝트 변경 없음.

## 실행 검사
코드 SHA: 669463484a20fb24cd51c722e48421850dab3389
`PYTHONPATH=tests .venv/bin/python -m unittest test_frozen_test test_frozen_test_evaluation test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs -v`: 23개 PASS (0.691초). 신규11 + 관련기존12. 실제 모델은 mock, 사진과 checkpoint는 합성이다. 학습/실사진추론/외부AI0.
`PYTHONPYCACHEPREFIX=/private/tmp/frozen-test-pycache .venv/bin/python -m compileall -q ...`: 소스6개·신규검사2개 PASS. diff --check PASS. 전체suite는 미실행.
AST 함수수: 신규 frozen_test3/frozen_test_cli1, 기존 세평가기각1→1/cli1→1, 신규검사7/6. 새 주요경로 cli.main→evaluator→claim_test→read_seal→file_sha256 4전이. CLI 봉인: main→seal_test→load_manifest/track_photos 2전이(기존 I/O 경로 활용). 새 재귀 없음. 기존 모델 호출경로에 전이를 추가하지 않았다.

## 제한 / 리스크
- 봉인과 ledger는 제공한 사용이력과 human group에 의존한다. 이름만 바꾼 같은 실물의 다른사진, 누락된 개발이력, 사람정답 의미, 선택 전 시점은 자동증명하지 않는다. 하위군/30실물 전범위분모는 아직 검증하지 않는다.
- 옵트인 평가만 보호하며 ledger는 checkout별이다. 실제평가는 기본checkout 단일 담당자만 실행하고 ledger를 보존해야 한다. 기존 직접평가나 ledger 삭제를 막는 보안장치는 아니다.
- 한 번 claim한 자료는 로딩실패에도 보수적으로 소비됨 처리한다. 자동삭제·자동재시도 없음. 독립시험이 아닌 것으로 사용기록을 남기고 새로운 독립자료가 필요하다.
- 현재 단일 평가기 실행마다 한 번 사용한다. 동일자료에 region/side/observation을 각각 실행하는 전범위 묶음은 새 후보선택 없이 한 번 묶어 실행할 별도 수용절차가 필요하다. 이 구현만으로 전범위 D2를 완료하지 않는다.
- 봉인 검증과 기존 입력검사가 파일 I/O를 추가한다. 추론속도 향상 또는 모델정확도 변화는 측정하지 않았다.

## 롤백 / HTML
`./develop -- git revert 6694634` 후 관련23개검사. 이미 생긴 usage영수증은 평가 노출 증거이므로 삭제하지 않는다. 봉인·원본·정답은 보존한다.
HTML: artifacts/frozen-test-use-20261026/index.html. 고정점수/검증SHA/실행검사/한계/롤백을 내용대조했다. Codex 파일열기 요청과 실제렌더 여부는 별도로 인계한다. 임의서버·터널은 생성하지 않는다.

HTML 열기 결과: Codex browser 도구는 queued(열기 대기) 응답이다. 실제 렌더는 미확인이다. 이 응답을 화면 확인 성공으로 계산하지 않는다.

# 봉인시험의 동결 후보 묶음 / 역할별 1회 사용

개발 진척률 30/100 (usable-card-analysis-v1.0, 변화0%p). 이번 성과는 후보 묶음 고정과 역할별 단일사용 연결이다. 모델 품질과 D1/D2/D3 완료는 평가하지 않았다.

## 파일과 핵심 diff
- card_condition/frozen_candidate.py (신규2함수): 후보는 봉인SHA, 명시한 region_final/side_final/observation_final의 checkpoint 경로·SHA, package *.py 전체 파일목록·SHA, Python/torch/torchvision/Pillow 버전, 요청장치(cpu/mps), threshold0.5를 고정한다. read_candidate는 모든 역할 모델·모든 소스와 런타임을 재검증한다.
- card_condition/frozen_candidate_cli.py (신규1함수): `python -m card_condition.frozen_candidate_cli TEST SEAL CANDIDATE --seal-sha256 SHA --device cpu --region MODEL --side MODEL --observation MODEL` (역할은 명시한 subset도 허용). 출력candidate_sha256을 보존한다. 모델 로딩/학습/선택 없음.
- card_condition/frozen_test.py (3→3함수): 같은 seal SHA·candidate SHA로 미리 명시한 다른 역할만1회씩 허용한다. 이전 일반claim·후보변경·같은역할 재실행·새봉인은 거절한다. 역할별 영수증을 남겨 실패 후 같은역할 재시도는 막는다.
- card_condition/{region_evaluation,side_evaluation,observation_heldout}.py, cli.py(각1→1): keyword-only test_candidate/test_candidate_sha256과 CLI --test-candidate/--test-candidate-sha256. 기존 선택봉인 경로와 일반 호출 유지. 실제 후보를 쓸 때는 --device cpu/mps를 명시해야 한다(auto 거절).
- tests/test_frozen_candidate.py (6함수), tests/test_frozen_candidate_evaluation.py(6함수): 모델3역할 각각1회, 새후보/역할재실행/체크포인트변경/소스변경/파일추가/런타임변경/장치변경/누락핀 거절, 실제CLI 전달, 추론 중 다른역할 checkpoint변경시 결과파일미생성 및 claim유지.
- 작업계약과 본보고서. 원본/라벨/학습/기존실험/평가기준/진척점수/소비서비스는 불변.

## 실행 근거
검증소스 SHA 790081880de82986fd3786b6d3e498382fb75723.
`PYTHONPATH=tests .venv/bin/python -m unittest test_frozen_candidate test_frozen_candidate_evaluation test_frozen_test test_frozen_test_evaluation test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs -v`: 32개 PASS(0.861초). 신규9개/관련23개. 실제 모델은 mock, 사진·checkpoint는 합성이다. 학습/실사진추론/외부AI0. 전체suite 미실행.
명시한 임시 PYTHONPYCACHEPREFIX를 사용한 compileall(변경소스7개/신규검사2개), diff --check PASS.
주요 새 경로 main→evaluator→claim_test→read_candidate→file_sha256(4전이), main→pin_candidate→read_seal→file_sha256(3전이). 새 wrapper/재귀 없음. 기존 모델 추론경로의 전이는 추가하지 않았다.

## 리스크 / 독립 검증 조건
- 후보가 소스 전체를 묶으므로 관련 없는 Python 소스 추가도 실행을 차단한다. 시험 중 재핀해서 풀지 않는다. 실제 평가는 새 CLI 프로세스에서 수행한다. source SHA는 이미 import한 오래된 메모리 객체, 실제 하드웨어, dependency 내부 바이트나 결정론적 kernel까지 인증하지 않는다.
- 첫 역할 오류가 나도 동일 후보의 사전지정 다른역할은 각1회 계속할 수 있다. 실패한 역할의 새 모델/재시도는 금지하며 전범위 통과로 합산할 수 없다. 부분 결과를 완성된 독립시험으로 보고하지 않는다.
- 같은 물리카드의 다른사진/잘못된group/누락된개발이력은 자동판단하지 못한다. test-only 봉인만으로 개발미사용·사람정답·30실물분모·실험선택전 이력·하위군을 인증하지 않는다. d2_verified=false 및 진척30유지.
- 검증은 추가 파일SHA I/O를 사용한다. 실제 성능/속도개선은 미평가다. 외부 strict JSON소비자는 선택봉인 결과의 candidate_sha256/operation 필드 추가에 대응해야 할 수 있다.

## 롤백 / 보고
`./develop -- git revert 7900818` 후 관련32개검사. 기존 시험사용 영수증은 삭제하지 않는다. 이전 candidate 소스 핀은 롤백 후 불일치할 수 있으므로 자동새핀으로 재시험하지 않는다.
HTML artifacts/frozen-candidate-plan-20261026/index.html 생성 및 점수/32검사/SHA/한계/롤백 내용 대조. 열기응답과 렌더확인은 별도로 기록한다.

HTML: Codex browser 열기 요청은 queued. 실제 화면 렌더는 미확인. 열기요청을 렌더성공으로 보고하지 않는다.

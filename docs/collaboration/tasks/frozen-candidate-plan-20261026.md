task_id: frozen-candidate-plan-20261026
owner: Codex
status: integrated
base_sha: ccc9365a214f0ba3d2233b0fc49de6cfdd2259d4
branch: codex/frozen-candidate-plan-20261026
goal: 같은 봉인시험에 사용할 역할별 checkpoint·평가소스·런타임·threshold를 사전에 하나의 후보파일로 고정하고, 고정된 다른 역할만 각1회 허용한다. 후보교체·역할재실행·코드/런타임변경은 추론 전 차단한다.
allowed_files:
- card_condition/frozen_candidate.py
- card_condition/frozen_candidate_cli.py
- card_condition/frozen_test.py
- card_condition/region_evaluation.py
- card_condition/side_evaluation.py
- card_condition/observation_heldout.py
- card_condition/cli.py
- tests/test_frozen_candidate.py
- tests/test_frozen_candidate_evaluation.py
- docs/collaboration/tasks/frozen-candidate-plan-20261026.md
- docs/collaboration/reports/frozen-candidate-plan-20261026.md
- ignored artifacts/frozen-candidate-plan-20261026/index.html
forbidden_files: 나머지 파일/Claude 소유소스/원본/라벨/기존실험/진척률/기준/소비서비스/비밀설정
contract:
- 선택적 candidate 파일 SHA를 평가자가 명시한다. 후보는 seal SHA, region_final/side_final/observation_final 중 명시한 역할별 checkpoint SHA와 소스 전체 *.py SHA, Python/torch/torchvision/Pillow 버전을 고정한다. 고정 threshold .5. checkpoint metadata가 지원범위/전처리의 정본이며 SHA가 이를 묶는다.
- 첫 역할의 claim 후 같은 봉인·같은 후보·다른 예정역할만 이어서 허용한다. 같은역할·새후보·새봉인·같은사진 재사용은 차단한다. 기존 candidate 없는 한번사용 경로는 유지한다. 오류 후 같은 역할 재시도 금지.
- 모델파일·소스·런타임·정책변경 또는 대응안되는 역할은 claim 전에 거절한다. 평가 중 파일 변경도 최종 입력SHA검사로 거절한다. 후보 파일 핀을 자동으로 갱신하지 않는다.
- 독립성/사람정답/시험봉인 전 모델선택 이력/수치통과를 인증하지 않는다. 점수와 D1/D2/D3상태 유지. 합성/mock만 검사, 실제학습·실사진추론·외부AI0.
structure: 신규 candidate최대3함수/CLI1함수, frozen_test3유지, 기존 각evaluator/CLI1유지, 테스트 파일별7이하. 신규 경로 main→evaluator→claim_test→read_candidate→file_sha256 4전이, 기존 경로 추가래퍼 없음.
checks: 역할별1회·전체묶음모델핀·코드/런타임변조·재핀/역할재실행거절·기존봉인회귀·공용CLI 합성검증, AST/diff, HTML생성/내용대조/열기, main통합/push.
experiment: 없음
handoff: 완료 후 실제검사·미검증·리스크·롤백 기록.

최종검사: main 구현7900818, 32개 합성/mock PASS, compileall/diff PASS. 신규소스2/1함수, frozen_test3 및 기존각1유지, 신규검사6/6함수. 세부위험/롤백/HTML은 reports/frozen-candidate-plan-20261026.md.

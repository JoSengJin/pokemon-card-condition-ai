task_id: physical-card-uncertainty-20261026
owner: Codex
status: implementing
base_sha: 4128dd1bf9891596fa0ccab4a82294fb24086d25
branch: codex/physical-card-uncertainty-20261026

goal: 기존 region/side 최종평가 출력에 질문×앞뒤 실물별 하나이상 누락/오탐 사건률과 단측95% Wilson 상한을 추가한다. 합성 반례로 패치 복제·양면 혼합·미확인/미지원/점수누락의 거짓 통과를 방지한다.
allowed_files:
- card_condition/physical_uncertainty.py
- card_condition/region_evaluation.py
- card_condition/side_evaluation.py
- tests/test_physical_uncertainty.py
- tests/test_physical_uncertainty_evaluation.py
- docs/collaboration/tasks/physical-card-uncertainty-20261026.md
- docs/collaboration/reports/physical-card-uncertainty-20261026.md
- ignored artifacts/physical-card-uncertainty-20261026/index.html
forbidden_files: 그 외 소스, Claude 소유 파일, 사진/라벨/기존 실험/진척률/평가기준/PokeCollector/비밀설정
contract:
- fixed threshold .5, z=1.6448536269514722, 누락상한 .10, 오탐상한 .20, 각30실물 최소.
- positive: 알려진 양성 중 하나이상 raw 누락 사건. negative: 해당 질문/면의 제공 판정단위가 모두 알려진 정상인 실물에서 하나이상 raw 오탐 사건. 양성/미확인 포함 실물은 정상 분모로 바꾸지 않는다. 전체 카드 정상 증거는 아님.
- 미확인 정답은 별도 집계, 알려진 정답에 점수 없음은 명시적 미측정. 누락 점수를 정상이나 누락으로 추측하지 않으며 해당 사건률/상한은 None. 실물 식별은 기존 group을 신뢰하고 동일 group 내 중복구역은 독립 실물로 세지 않는다.
- 앞뒤/질문별 분리. 지원되지 않는 필수질문도 빈 분모로 표시. gradable은 D3 질문이 아님.
- 새 필드는 진단 수치조건만 나타내고 milestone_verified=false 유지. D1/D2 봉인/독립성, 촬영조건/언어/판본 하위군 및 전범위 품질은 별도 근거 필요. 점수 자동변경 없음.
- 기존 평가 raw FN/FP, 반환 필드, 보류정책 불변. 실제 추론/학습/외부호출 없이 mock/합성 검사만 수행.
structure:
- physical_uncertainty.py 신규 4함수 이하, region_evaluation.py 1→1, side_evaluation.py 1→1.
- 신규 경로 evaluate_regions/evaluate_sides → physical_uncertainty → event_summary → wilson_upper (3전이), 모든 함수 표준 라이브러리만 사용. 기존 추론경로 전이 추가 없음.
checks: stdlib 합성단위검사, 기본checkout 통합 후 test_evaluation_inputs.py(mock 추론)/기존 평가 회귀, AST 함수수, diff --check, HTML 생성/내용 대조/열기(렌더 여부 별도).
experiment: 없음. 합성 검사만. 새 실험/실사진 추론/AI호출 없음.
handoff: 구현 후 실제 결과/리스크/롤백/HTML 열기 결과를 기록한다.

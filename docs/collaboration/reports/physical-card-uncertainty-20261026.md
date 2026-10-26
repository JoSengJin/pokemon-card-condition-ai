# 실물별 누락·오탐 사건률과 불확실성 계산

개발 진척률 30%(usable-card-analysis-v1.0, 직전 대비 0%p). D3 수치 판정을 위한 계산을 구현했으며 D3 자체는 pending이다. 모델 성능 변화는 평가하지 않았다.

## 변경 파일과 핵심 diff

- `card_condition/physical_uncertainty.py`: 질문 5개×앞뒤별 실물 group 단위 하나이상 누락/오탐, 단측95% Wilson 상한(z=1.6448536269514722), 최소30실물 및 상한10%/20% 수치조건을 계산한다.
- `card_condition/region_evaluation.py`, `card_condition/side_evaluation.py`, `card_condition/observation_heldout.py`: 기존 최종평가 보고서에 `physical_card_uncertainty` 필드를 추가한다. 기존 raw FN/FP·정책·모델 출력은 유지한다. side_rows는 side 필드가 없으므로 생성 코드가 보장하는 id의 /front·/back 접미사를 사용한다.
- `tests/test_physical_uncertainty.py`: Wilson 경계값, 잘못된 값 거절, 패치 복제 불변, 질문·앞뒤 분리, 부족/미지원/미확인/점수누락의 거짓통과 방지.
- `tests/test_physical_uncertainty_evaluation.py`: region/side/관찰제한 평가기 연결, 기존 raw 분모 유지, JSON 저장을 합성/mock으로 검증한다.
- 작업계약 및 본 보고서. 사진·라벨·학습·실험·진척점수·PokeCollector 변경 없음.

## 실제 검사

검증 코드 SHA: a15912211c7529af22dc5247d9e534a3078d4455 (main 통합 후). 문서 커밋은 별도다.

`PYTHONPATH=tests .venv/bin/python -m unittest test_physical_uncertainty test_physical_uncertainty_evaluation test_evaluation_inputs -v`: 12개 PASS(0.427초). 전체 suite는 미실행. 학습·실사진 추론·외부AI 호출 0. 기존 평가기 및 모델은 mock이며 입력은 합성이다.

`PYTHONPYCACHEPREFIX=/private/tmp/uncertainty-pycache .venv/bin/python -m compileall -q ...` 대상 소스4개/신규검사2개 PASS. 최초 worktree compileall은 macOS 외부 cache 쓰기 권한 오류로 미완료였으며 명시한 임시 cache 경로로 해결했다. `git diff --check` PASS.

초기 통합검사는 side row에 side 필드가 있다고 잘못 가정하여 실패했다. 생성 코드 side_experiment.side_rows의 ID 계약과 대조한 수정(35c0268) 뒤 위 검사를 통과했다. 실패를 통과로 바꾸어 기록하지 않는다.

AST 함수수: physical_uncertainty 3, region_evaluation 1→1, side_evaluation 1→1, observation_heldout 1→1, 새 단위검사6, 새 통합검사2. 신규 경로 evaluator→physical_uncertainty→event_summary→wilson_upper(3전이), math.sqrt까지4전이. 재귀·새 동적 디스패치 없음. 기존 모델 로딩/추론 호출경로 전이 추가 없음.

## 결과 의미와 리스크

실물 30개에서 누락0개인 합성 예시의 단측95% 상한은 약8.27%다. 같은 실물의 구역을 반복해도 실물수/상한이 달라지지 않는다. 이 예시는 모델 측정값이 아니다.

정상 분모는 해당 질문/면에 제공된 모든 단위의 정답이 알려진 정상인 실물만 센다. 양성·미확인이 함께 있는 실물을 정상으로 세지 않는다. 관찰하지 않은 다른 구역까지 전체 카드 정상이라고 증명하지 않는다. 알려진 정답에 raw 점수가 없으면 분모를 유지하고 사건률/상한은 None으로 남긴다. 보류된 단위도 raw 점수가 있으면 판정에 포함한다.

리스크: 기존 group 식별과 제공 평가단위 범위를 신뢰한다. 잘못된 group 또는 빠진 구역의 정답을 검증/복원하는 도구가 아니다. 새 JSON 키를 거절하는 외부 strict 소비자는 업데이트가 필요할 수 있다. 평가 호출에 수치 집계 비용이 추가된다(사진 decode/모델 호출 추가 없음). 과거 저장 보고서는 변경하지 않는다.

D3 완료에 추가로 필요한 근거: D1 봉인 시험자료, D2 동일 동결후보, 전체질문·앞뒤 최소분모/성능, 언어·판본·촬영조건 하위군과 제외범위. 이 구현은 milestone_verified=false이며 점수를 올리지 않는다. E2/F1/F2의 품질통과 후보·소비경로 승인·실사용도 대신하지 않는다.

## HTML / 롤백

`artifacts/physical-card-uncertainty-20261026/index.html`에 이 결과와 고정 진척률을 표시했다. 열기 결과는 아래 인계에 기록한다.

롤백: 실행 중 개발/평가가 없는 상태에서 `./develop -- git revert a159122 35c0268 30397ec` 실행 후 위 12개 검사. 계약/보고 문서는 감사기록으로 보존해도 된다. 원본/라벨/모델 복구는 필요 없다.

최종 열기 결과: macOS open은 NSOSStatusErrorDomain -10661(호환 실행 앱 없음)로 실패. Codex browser 열기는 queued 응답뿐이며 렌더 성공 증거가 아니다. CUA에서 file URL 확인은 Browser Use URL policy로 차단됨. 화면 렌더 미확인. HTML 내용 대조(30/100, 기준버전, 코드 SHA, 12검사, pending, 리스크/롤백)는 완료. 로컬 파일 링크로 인계하며 서버/터널을 만들지 않았다.
worktree: 이번 Codex checkout은 최신 완료 작업의 롤백 확인용으로 유지한다. 다른 Claude/기존 Codex checkout은 이 작업에서 소유·통합·사용중 여부가 확정되지 않아 변경하지 않았다.

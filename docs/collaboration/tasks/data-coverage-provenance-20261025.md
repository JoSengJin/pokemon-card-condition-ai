# 데이터 부족표 출처·중복 감사 — Claude 배정

- task_id: `data-coverage-provenance-20261025`
- owner: Claude
- status: ready_for_review
- base_sha: `bdc8fa616d3da756524927c6a4bd6637a8f38b08`
- branch: `claude/data-coverage-provenance-20261025`
- worktree: 로컬 경로는 Codex의 전달 메시지를 사용한다. 개인 절대경로를 커밋하지 않는다.

`base_sha`는 감사할 소스 기준이다. worktree는 이 작업 계약을 추가한 후의 커밋에서 시작한다. 그 사이에는 이 계약 문서만 추가하며, 모델·감사 소스는 바꾸지 않는다. 실제 시작 SHA는 전달 메시지의 `dispatch_sha`로 확인한다.

## 목표와 승인 범위

기존 `data-coverage` 집계가 출처·종류·면·정정 이력·중복을 잘못 해석하는지 검토하고, 최대 3개 발견에 각각 코드 행/근거 SHA/최소 반례/영향을 제시한다. 사람 입력 없이 확정할 수 있는 다음 수정 또는 source 매핑을 최대 1개 제안한다. 실제 반례가 없으면 오류 없음 또는 근거 부족으로 보고하며 기능을 만들지 않는다.

최신 소비 TODO의 2026-10-24 상단과 `artifacts/data-coverage-20261024/CLAUDE_NEXT_PROMPT.md`가 근거다. 휴먼인루프는 일시 중지이며 새 라벨·사진 요청, 검토 서버, 학습·사진 추론·모델 비교·외부 AI 호출·운영 교체는 이 작업에 포함하지 않는다. 과거 캐시 불일치 실험을 재개하지 않는다.

이번 작업은 검토와 합성 반례 확인까지다. 운영 소스의 수정안은 Codex 검토 후 후속 task로 분리한다. 기존 사람 정답·분할·수치 기준은 고치지 않는다.

## allowed_files — 아래 3개만 추가·수정 가능

1. `docs/collaboration/tasks/data-coverage-provenance-20261025.md` — 상태·검사 결과·인계 SHA 기록.
2. `docs/collaboration/reports/data-coverage-provenance-20261025.md` — 신규 감사 보고서.
3. `tests/test_data_coverage_provenance.py` — 실제 반례 또는 미검증 경계가 있을 때만 신규 합성 fixture 테스트. 테스트를 만들기 위해 실제 정답을 복사하지 않는다.

잠금으로 생성되는 `artifacts/development-cycle/workspace.lock`과 가상환경·임시 테스트 파일은 로컬 실행 산출물로 허용하되 커밋하지 않는다. 새 테스트 파일 편집도 `./develop -- <실제 수정 명령>` 안에서 수행한다.

## forbidden_files / 병렬 소유권

- 위 목록 밖의 모든 추적 파일은 읽기 전용이다. 특히 `card_condition/`, 기존 `tests/`, `AGENTS.md`, `PAIR_CODING.md`, README, 진행률·수용 기준, 공통 실행기·자동 검토 코드를 변경하지 않는다.
- 원본 `data/`, 사진·모델·라벨·과거 artifacts·provider 키는 변경하지 않는다. 기본 checkout에서 명령 실행·설정 변경·branch 이동·push를 하지 않는다.
- Codex는 이 task가 인계될 때까지 이 task의 허용 파일을 병행 편집하지 않는다. 감사 대상 소스의 추가 변경이 생기면 기준 SHA 차이를 먼저 기록하고 검토 범위를 다시 정한다.
- Git에 없는 로컬 근거는 아래 snapshot만 읽는다. 내부에 적힌 과거 절대경로를 따라 기본 checkout이나 소비 프로젝트를 추가 탐색하지 않는다.

## 읽을 코드와 로컬 근거

- `card_condition/data_coverage.py`, `point_dataset.py`, `regions.py`, `data.py`, `visibility_model.py::visibility_rows`, `cli.py`의 data-coverage 분기.
- `tests/test_data_coverage.py`, `test_point_dataset.py`, `test_region_dataset.py`, `test_regions.py`, `test_review.py` 및 fixture 제공 파일.
- `artifacts/collaboration/data-coverage-provenance-20261025/evidence/index.json`: 복사 근거의 원본 상대경로·snapshot 경로·SHA·누락 기록. 로컬 근거는 Git에 올리지 않는다.
- snapshot의 REPORT/기존 인계/부족표/출처 비교/inventory/verification과 국소자료 12출처를 대조한다. index SHA가 다르거나 필요한 정정 근거가 빠졌으면 해당 매핑만 미해결로 남긴다.

특히 side가 없거나 full_back_anchor와 사진이 다르다는 이유만으로 front를 추정하지 않는다. 과거 W 모호한 정상·실패한 모서리 정상 감사를 정상 확정으로 되살리지 않는다. 여러 점·구역·snapshot을 여러 실물로 합산하지 않는다. unknown·관찰 제한·미검토 box·종류별 실제점을 분리하고 test 라벨·사진을 해석하지 않는다. 기존 코드가 방어하는 조건은 실제로 깨지는 반례가 없으면 결함으로 보고하지 않는다.

## checks — 구현 worktree

1. `git status --short`, `git branch --show-current`, `git merge-base --is-ancestor bdc8fa616d3da756524927c6a4bd6637a8f38b08 HEAD`로 checkout과 소스 기준 확인.
2. `.venv/bin/python -c 'import card_condition; print(card_condition.__file__)'`가 자신의 worktree를 가리켜야 한다. 다른 checkout의 `.venv`·site-packages를 연결하지 않는다.
3. index의 snapshot SHA를 실제 파일과 대조한다. 이미지 경로는 출처 문자열일 뿐 사진을 열거나 추론하지 않는다. 누락된 근거의 내용을 추정하지 않는다.
4. `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions -q` 실행. 신규 테스트를 추가했으면 같은 명령에 `test_data_coverage_provenance`를 추가한다. 전체 `test_pipeline` suite는 학습을 포함하므로 실행하지 않는다.
5. 기존 코드의 실제 반례를 찾은 새 테스트가 실패하면 실패를 그대로 기록한다. 이 task의 완료는 결함을 숨겨 모든 테스트를 통과시키는 것이 아니라 재현 가능한 검토 결과를 전달하는 것이다. 의존성·권한 오류는 코드 반례와 구분한다.
6. `git diff --check`, `git diff --name-only <base_sha> HEAD`, 미커밋 diff를 대조한다. base 이후 Codex가 추가한 이 task 문서를 제외한 변경은 allowed_files 안이어야 한다. 비밀값·사용자 홈 절대경로·실제 라벨/사진을 보고서에 넣지 않는다.

## checks — Codex 인계 후

허용 파일·전체 diff·근거 SHA·재현 결과를 대조한다. 새로운 회귀 실패는 자동 채택하지 않고 별도 수정 계약의 입력으로 보존한다. 기존 정상 동작 검증에는 위 4개 모듈과 `test_review`를 사용하며 HTTP bind 권한 오류는 따로 보고한다. 합성 테스트가 통과해도 원본 국소자료의 정답·면 매핑이 입증됐다고 보지 않는다.

## 성공·실패·인계

- 성공: 최대 3개 근거 있는 발견 또는 확인한 범위의 오류 없음/미해결을 분리하고, 다음 수정/확정 가능 매핑 최대 1개와 최소 검사·판정 기준을 제시한다. 사실·가설·누락을 구별하고 allowed_files를 지킨다.
- 실패/대기: SHA 불일치·누락 근거·의존성 부재는 해당 검사를 미완료로 기록한다. 없는 라벨/side/성능을 추정하거나 금지 파일을 바꾼 결과는 인계 수용 불가다.
- experiment: 없음. 데이터 감사·합성 반례 확인이며 `./experiment`·실제 `./review --auto`·외부 provider를 실행하지 않는다. 모델 성능·개발 진척률 변경을 주장하지 않는다.
- handoff: 전체 커밋 SHA와 순서, 변경 파일, 최대 3개 발견, 실행 명령/종료코드, 미검증, 다음 수정 최대 1개, 리스크, 롤백을 보고한다. 별도 에이전트 메시지·push 권한은 부여하지 않는다.
- rollback: 아직 통합 전에는 작업 브랜치를 main에 반영하지 않는다. 후속 소유 변경을 확인한 뒤 통합 커밋만 revert한다. 이 task의 문서/합성 테스트 때문에 원본 데이터·모델을 복원하지 않는다.

## Claude 실행 결과

2026-10-25, 배정 worktree에서 실행. 보고서: `docs/collaboration/reports/data-coverage-provenance-20261025.md`.

- check 1: 브랜치 `claude/data-coverage-provenance-20261025`, HEAD=dispatch `91252d77b60e6de31b91a504daca5fadceaa9641`. `merge-base --is-ancestor bdc8fa6… HEAD` 종료코드 0. 시작 시 `git status --short`가 깨끗했고, base 이후 변경은 이 문서뿐이었다.
- check 2: 이 worktree의 `.venv`에 `requirements-tested.txt`와 `pip install --no-deps -e .`를 설치했다. `card_condition.__file__`가 이 worktree를 가리킨다.
- check 3: index 46개 SHA가 모두 일치했고, 누락 0, 미등재 0이었다. 사진은 열지 않았다.
- check 4: `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions test_data_coverage_provenance -q` → 31개 중 29개 통과, 2개 실패, 종료코드 1. 기존 4모듈 29개는 신규 테스트 추가 전후 모두 통과했다.
- check 5: 실패 2개는 의도한 반례 재현이다. 의존성·권한 오류는 없었다.
  - `test_off_target_typed_point_is_projected_or_traced`: 발견 1. 대상 구역 밖 점이 skip 기록 없이 빠진다.
  - `test_one_decoded_photo_counts_on_one_side_only`: 발견 3. 한 사진이 앞·뒤 두 단위로 집계된다.
- check 6: `git diff --check` 통과. base 이후 변경은 allowed_files 3개뿐이다. 보고서에 홈 절대경로·비밀값·실제 정답값·사진을 넣지 않았다.
- 미실행: `test_review`(Codex 인계 후 검사), 기본 checkout 재감사, `./experiment`, `./review --auto`.
- 발견 요약:
  1. 대상 밖 typed point 추적 누락(실제 1건, 수량 영향 0).
  2. 최신 보완 6행 `side=front`의 사람 근거가 snapshot에 없음(면미확인).
  3. 동일 사진 양면 이중 집계(실제 0건).
- 다음 수정 1개: 발견 1의 skip reason `point_outside_target_area`를 기록한다.

### 재검증 — Codex 리뷰 반영 (후속 커밋, 부모 `7c24c0924575753dd3b0f6f41d568e89a1361c7b`)

위 절은 최초 감사 커밋의 기록이며 수정하지 않았다. 이번 후속 커밋은 같은 allowed_files 3개만 바꾸고, 운영 코드는 바꾸지 않는다.

- 발견 1 테스트: 무엇이든 skip이 있으면 통과하던 조건을, 다섯 필드가 모두 일치하는 skip이 정확히 1개 있어야 하는 조건으로 바꿨다. 다섯 필드는 card_id, `side='front'`, `label='corner_defect'`, `area='middle_right'`, `reason='point_outside_target_area'`이다. typed point 1점/1실물과 양성 구역 0단위 단언은 유지했다.
- 발견 3 테스트: `test_one_decoded_photo_counts_on_one_side_only`의 앞뒤 합계 1 단언을 삭제했다. 대신 `test_one_decoded_photo_assigned_to_both_sides_is_rejected`를 넣었다. 서로 다른 앞뒤 사진의 대조 입력이 정상 처리된 뒤, 같은 디코딩 사진을 양면에 지정하면 `ValueError`가 나야 한다는 계약이다.
- 보고서: photo-4 행은 "면만 back으로 확인, 구역 대응 등 나머지 조건 미검증, primary 채택 불가"로 범위를 고쳤다. 발견 3의 계약·판정 기준·후속 설명을 거절 계약에 맞췄고, 최초/재검증 이력 절을 추가했다.
- 실행 결과:
  - `PYTHONPATH=tests .venv/bin/python -m unittest test_data_coverage test_point_dataset test_region_dataset test_regions test_data_coverage_provenance -v` → 31개 중 29개 통과, 2개 실패, 종료코드 1.
    - 실패 1: `test_off_target_typed_point_is_projected_or_traced` `AssertionError: 1 != 0`. 정확한 skip 기록이 없다.
    - 실패 2: `test_one_decoded_photo_assigned_to_both_sides_is_rejected` `AssertionError: ValueError not raised`. 대조 입력은 통과했다.
    - 둘 다 의도한 단언 실패이고, 의존성·권한 오류는 없었다.
  - `... test_data_coverage test_point_dataset test_region_dataset test_regions -q` → 29개 통과, 종료코드 0.
  - 메모리 안에서 `coverage_report`를 감싼 대조 실행(운영 코드 변경 없음): 무관한 `surface_defect` skip, 다른 reason, 다른 area → 실패. 정확한 기록 → 통과.
  - `git diff --check` 통과. 변경 파일은 allowed_files 3개 안이다.
- skip이나 expectedFailure는 추가하지 않았다.
- 미실행: `test_review`, 기본 checkout 재감사, `./experiment`, `./review --auto`.

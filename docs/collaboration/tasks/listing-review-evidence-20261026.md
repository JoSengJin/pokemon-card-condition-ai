task_id: listing-review-evidence-20261026
owner: Claude
status: ready_for_review
base_sha: 8e063ceed46713a3522cf501a79878a459747516 (2026-10-26 fetch한 origin/main)
branch: claude/listing-review-evidence-20261026
worktree: 세션에서만 전달
assignment: 사용자가 "동일한 방식으로 다음 개발도 이어가 달라"고 지시했다(2026-10-26). 데이터 확보를 제외한 개발 중 미소유 항목을 골랐다. Codex task 문서는 없고, 통합 전에 Codex가 계약을 검토한다.

## 중복 확인 (2026-10-26)
- origin/main은 8e063ce 그대로. tasks 문서, worktree 10개, 로컬·원격 브랜치 전부의 변경 파일을 대조했다. listing_review.py·tests/test_listing_review*를 건드리는 미통합 작업은 없다. cli.py를 건드리는 미통합 작업은 pilot-usage-record-20261026(F2 측정)뿐인데 이 task는 cli.py를 바꾸지 않는다.
- 제외: surface-normal-coexclusion(다른 Claude 세션이 구현 인계), cross_review 계열(Codex·다른 세션), A3·자료 확보·gold example, E2 coverage 계산기(동결 평가표 형식이 A3에 의존).
- 두 task는 서로 독립이다. 통합 순서 제약 없음. README.md는 서로 다른 단락을 수정했다(이 task는 릴리스 단락 끝 문장 하나). 같은 파일이라 cherry-pick 때 인접 충돌이 나면 두 변경을 모두 유지하면 된다.
- 최근 보관 작업(PAIR_CODING 정리 규칙): claude/gold-example-selection-20261025 @ 3e23bd8(롤백용). 이 task의 worktree는 통합 후 정리 대상이다.

## 발견한 공백
E2는 "원본사진·근거구역·모델버전·판정/보류이유를 확인하고 정정/검토를 완료"할 수 있어야 한다. 기존 검토 페이지(26d00fa 통합)는 결과의 `observation_evidence`와 `recall_review`를 전혀 쓰지 않았다. recall 후보는 주 모델이 놓쳤을 수 있는 의심 칸이라 검토자에게 가장 필요한 근거인데 화면에도 기록에도 없었다. 또 F1 인계의 미검증 항목이었던 "observation·recall을 포함한 release 실행"이 어떤 테스트에도 없었다(관련 테스트가 region만 사용).

## goal
검토 페이지가 관찰 신호와 recall 후보를 보조 근거로 보여 주고, 불일치한 근거는 거절하며, 검토 기록이 두 모델 SHA와 후보 칸을 묶는다. region+recall+observation 릴리스의 실행·식별을 실제 경로로 확인한다.

## allowed_files
- card_condition/listing_review.py
- README.md (릴리스 단락 끝 문장 하나)
- tests/test_listing_review_evidence.py (신규)
- docs/collaboration/tasks/listing-review-evidence-20261026.md
- ignored 산출물: artifacts/listing-review-evidence-20261026/{index.html,demo-three-role.html}

## forbidden_files
cli.py, listing_model.py, release.py, region_model.py, visibility_model.py, recall_review.py, listing_observation.py, listing_readiness.py, pyproject.toml, 라벨·데이터·실험 기록, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, 운영 Gemini 경로, 다른 task 소유 파일.

## contract
- recall 후보는 결과의 칸(면·구역·종류)과 정확히 하나씩 대응해야 한다. 어느 칸과도 맞지 않거나 중복이거나, 값이 문자열이 아니거나, primary/secondary 점수가 유한한 숫자가 아니면 ValueError로 페이지와 기록을 만들지 않는다(기록 단계도 같은 검사).
- 관찰 근거: records는 목록이고 side는 front/back, 점수는 None 또는 0~1, 사람 관찰 제한·글레어 구역은 None 또는 목록이어야 한다. 아니면 페이지를 만들지 않는다.
- 표시: 사진 위 recall 후보 구역 테두리, 칸 표의 "추가 근거" 열(primary·secondary), 관찰 면별 표(사람 제한 미검토/없음(호출자 주장)/목록, 모델 신호, 이유), 두 모델 SHA, 정책·판정 문구, 릴리스 줄의 고정 모델 역할. 모든 결과 문자열은 html.escape한다. 보정되지 않은 신호이며 제한 해제·결함 확정·거절에 쓰지 않는다는 문구를 함께 둔다.
- 기록: 칸 판정 스키마는 그대로이고 observation_model_sha256, recall_model_sha256, recall_candidate_cells를 추가한다. ground_truth·used_for_training·changes_model_verdict는 계속 false. 기존 형식의 결과(근거 블록 없음)는 모델 SHA None·후보 없음으로 같은 방식으로 처리된다.
- 모델 판정, 보류 의미, centering_not_evaluated·whole_listing_observability_not_validated 표시는 바꾸지 않는다.

## structure (ast 실측)
- listing_review.py 4→6(checked_inputs, recall_cells, evidence_view, side_view, review_page, review_record), tests/test_listing_review_evidence.py 신규 6, cli.py 변경 없음.
- 호출 경로: review_page → evidence_view → recall_cells = 2회, review_record → recall_cells = 1회, review_page → side_view → photo = 2회. 기존 ListingAnalyzer 경로 변경 없음. 재귀·동적 디스패치 없음.

## checks (실제 실행)
- `unittest discover -s tests -p 'test_listing_review*.py'` OK(8): 실제 3-checkpoint release 보고서의 근거 표시·기록 결속, 구성한 후보 1칸의 표시와 다른 칸 비표시, 불일치 근거 12종 거절과 양성 대조, 이스케이프.
- 변형 검사 9개(셀 표시 제거, 중복·문자열·유한성 검사 제거, 관찰 상한 완화, 이스케이프 제거, 기록 필드 3종)가 모두 실패로 감지됨을 확인하고 소스를 백업과 cmp로 복원했다.
- 실제 경로: region+recall+observation 릴리스(무작위 초기화 합성 checkpoint)를 ListingAnalyzer(release=)로 실행해 checkpoint_sha256에 세 역할이 식별되고 후보 9칸·관찰 면 2개가 나옴을 확인했다.
- 격리 설치: tools/release/verify_install_rollback.py 7/7 PASS. 같은 wheel 설치본(저장소 밖 site-packages)에서 3-role manifest로 listing-predict → listing-review가 성공(42칸, 후보 9, 관찰 면 2, 역할 3개).
- 전체 suite 802개: 오류 104는 모두 worktree에 없는 ignored 파일(nemotron-review.json 101, artifacts 3, import 1)이며 변경 파일 관련 실패 0. 기본 checkout에서 재실행 필요.
- 브라우저: 로컬 정적 서버에서 데모 페이지 렌더(데스크톱·375px 모바일, 가로 넘침 없음, recall 구역 9, 표 42행, 모바일 스크린샷으로 근거 패널 확인), 성과 보고서 렌더.
- 무작위 초기화 합성 checkpoint와 생성 이미지만 사용. 학습·실사진 추론·성능 비교·외부 호출 0.

## experiment
불필요.

## HTML
artifacts/listing-review-evidence-20261026/index.html(성과 보고, ignored)과 demo-three-role.html(설치본이 만든 합성 데모). 합성 점수는 모델 품질이 아님을 표시했다.

## risks
- 후보의 `box`와 `reason`/`action` 필드는 표시나 검증에 쓰지 않는다(칸이 기준). 형식이 바뀌면 recall_review 쪽 변경과 함께 봐야 한다.
- 관찰 신호는 면 전체 값이라 구역 제한을 대신하지 못한다.
- 페이지가 사진을 base64로 내장해 크다. 실사진 페이지는 Git 밖에 둔다.
- 실사진(EXIF 회전·큰 이미지)·여러 매물 묶음·사람 사용성은 미검증이다.

## rollback
`./develop -- git revert <이 문서 커밋> <구현 커밋>`. 기존 검토 기록 파일은 그대로 유효하다(새 필드만 없다). 모델·라벨·실험 기록·진척 기준 변경 없음.

## handoff
- 구현 커밋: 6819527c965ce92ed342df56bd2f7cd707c03eec. 이 문서 커밋이 뒤따른다. 통합 순서: 구현 → 문서. cherry-pick은 ./develop 안에서.
- 기본 checkout에서 통합 후 확인: 전체 suite, tools/release/verify_install_rollback.py 7/7, README 인접 충돌(pilot 브랜치와 같은 파일).
- F1: 승인된 소비경로·품질통과 후보 때문에 pending 유지. 이번에 observation·recall 포함 릴리스의 설치본 실행 미검증 항목은 합성 fixture로 닫았다. 실제 모델 품질과 소비경로는 아니다.
- E2: pending 유지. 남은 조건은 센터링 포함 전 범위, 비보류 coverage ≥70%, blocker 해소이다. 전체 진척 30/100 유지.

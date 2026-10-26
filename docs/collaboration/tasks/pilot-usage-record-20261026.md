task_id: pilot-usage-record-20261026
owner: Claude
status: ready_for_review
base_sha: 8e063ceed46713a3522cf501a79878a459747516 (2026-10-26 fetch한 origin/main)
branch: claude/pilot-usage-record-20261026
worktree: 세션에서만 전달
assignment: 사용자가 "데이터 확보 제외 개발을 확인해 진행하고 Codex에 공유할 수 있게 준비, 중복 개발 방지"를 지시했다(2026-10-26). Codex task 문서는 없다. 통합 전에 Codex가 계약을 검토한다.

## 중복 확인 (2026-10-26)
- docs/collaboration/tasks 전체와 worktree 9개, 로컬 브랜치 전부의 변경 파일을 대조했다. card_condition/cli.py·listing_model.py·pilot_*·tests/test_pilot_*를 건드리는 미통합 작업은 없다(F1/E2 브랜치는 cherry-pick으로 통합된 같은 내용).
- 제외한 항목: surface-normal-coexclusion은 다른 Claude 세션(claude/task-1026-1, a350866)이 구현 인계까지 했으므로 건드리지 않았다. review-correct-input·review-manifest-dedupe는 cross_review 계열 소유. A3·자료 확보·gold example·pair-control은 데이터 또는 별도 도구.
- 데이터 없이 진행 가능하지만 없던 항목: F2의 측정 수단(요청별 기록, 조건별 요약). E2 coverage 계산기는 동결 평가표 형식이 A3 산출물에 달려 있어 형식 충돌을 피하려고 제외했다.
- 최근 보관 작업(PAIR_CODING 정리 규칙): claude/gold-example-selection-20261025 @ 3e23bd8 (롤백용 유지). 내 이전 F1·E2·front-joint-holdout·계약 worktree는 2026-10-26 정리 보고서대로 제거됐고 브랜치와 SHA는 보존돼 있다. 이 task는 그 코드를 main에서 그대로 사용한다.

## goal
승인된 shadow/보조 사용에서 요청마다 F2 측정에 필요한 사실을 개인 정보 없이 남기고, 릴리스별로 F2 문턱과 대조한 요약을 계산하되 통과를 인증하지 않는다.

## allowed_files
- card_condition/pilot_record.py (신규)
- card_condition/pilot_summary.py (신규)
- card_condition/cli.py (listing-predict --usage-log, pilot-summary 하위 명령)
- README.md (한 단락)
- tests/test_pilot_record.py, tests/test_pilot_summary.py (신규)
- docs/collaboration/tasks/pilot-usage-record-20261026.md
- ignored 산출물: artifacts/pilot-usage-record-20261026/index.html

## forbidden_files
listing_model.py, release.py, listing_review.py, region_model.py, listing_readiness.py, pyproject.toml, 라벨·데이터·실험 기록, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, 운영 Gemini 경로, 다른 task 소유 파일.

## contract
- `--usage-log`가 없으면 listing-predict의 stdout·stderr·종료 코드와 파일 생성은 이전과 같다(테스트로 확인).
- 기록 한 줄(schema 1): outcome, error_type(예외 클래스 이름만), request_id(문자열일 때만), faces, 시작 시각, total/load/analyze 초, warm, release(결과의 release 블록), attempted_release_id(실패 시 manifest의 release_id를 best effort로 읽음), release_requested, model_sha256, device, image_size, batched_views, report_sha256(출력된 stdout 바이트의 SHA256), 칸 수(normal/defect/unknown), 보류 이유 집계. 사진 경로·오류 문장은 쓰지 않는다.
- 기록을 쓸 수 없으면 그 요청은 실패로 끝나고 stdout은 비어 있다(fail-closed). 실패한 요청도 기록한다.
- warm = 같은 UsageRecorder가 이미 한 요청을 끝낸 뒤의 요청. CLI는 항상 cold. warm p95 조건은 warm이고 ok이며 faces==2인 요청의 analyze_seconds로 계산하고, 요청 구간이 겹치면(동시성>1) 충족으로 판정하지 않는다.
- 요약은 릴리스별로 나눈다(합치지 않음). 직접 checkpoint 실행과 manifest를 읽지 못한 실패는 별도 그룹이며 pinned=false. 문턱: 기간 ≥7일, 요청 ≥100, 고유 request id ≥50(실물 신원은 미검증 표시), warm 앞뒤 한 쌍 p95 ≤30초, 기록된 실패율 ≤1%. 표본이 없으면 met=None(통과 아님).
- 사람 검토 기록(listing-review-record)은 report_sha256이 정확히 같을 때만 연결한다. 완료되지 않은 기록과 연결되지 않은 기록은 수로만 보고한다.
- `not_computed`에 정상 카드 거짓 경고율, Gemini 호출·검토 시간 변화, 승인·실물 신원, hard crash 미기록을 남기고 pilot_certified=false를 고정한다. F2 점수나 진척 기준은 바꾸지 않는다.

## structure (ast 실측)
- pilot_record.py 신규 7(append_line + UsageRecorder 메서드 6), pilot_summary.py 신규 5, cli.py 1→1, test_pilot_record.py 5, test_pilot_summary.py 7.
- 호출 경로: main → UsageRecorder.finish → append_line = 2, main → UsageRecorder.finish → entry = 2, main → summarize → release_group → p95/max_overlap = 3. 기존 ListingAnalyzer 로딩·분석 경로에는 호출 전이를 더하지 않았다(recorder는 main에서 직접 호출). 재귀·동적 디스패치 없음.

## checks (실제 실행)
- `unittest discover -s tests -p 'test_pilot_*.py'` OK(9). 기존 test_cli*, test_listing*, test_release OK.
- 변형 검사 10개(경계 ≥/>, p95 올림/내림, 겹침 무시, warm 정의, 출력 형식, 실패 귀속 3종)가 모두 실패로 잡힘을 확인하고 소스를 복원했다(백업과 cmp 일치).
- 전체 suite 807개: 오류 104는 모두 이 worktree에 없는 ignored 파일(nemotron-review.json 101, artifacts kieuk13·kieuk14·fixed67 3, import 1)이다. 기본 checkout에서 재실행이 필요하다.
- 기존 tools/release/verify_install_rollback.py 7/7 PASS(새 모듈 포함 wheel). 격리 설치본에서 --usage-log 두 번 성공·한 번 실패 후 pilot-summary가 요청 2·실패 0·직접 실패 그룹 분리를 출력했다. 설치된 모듈은 저장소 밖 site-packages에서 import됐다.
- 합성 fixture와 손으로 만든 기록만 썼다. 모델 학습·실사진 추론·성능 비교·외부 호출 0.

## experiment
불필요.

## HTML
artifacts/pilot-usage-record-20261026/index.html (ignored). 결과 표와 요약 예시는 합성 fixture 기반임을 표시한다.

## risks
- request id가 실물 id라는 운영 약속에 의존한다. 신원 검증이 아니다.
- 실패율은 기록된 실패만 센다. 기록 전에 죽는 hard crash는 소비 측 요청 수와 대조해야 한다.
- 로그가 로컬 파일이라 삭제·수정을 막지 않는다(append 전용 관례). 조작 방지는 범위 밖이다.
- listing-predict의 try/except 들여쓰기 변경으로 cli.py diff가 있다. 동작 동일성은 테스트로 확인했다.

## rollback
`./develop -- git revert <구현 커밋> <이 문서 커밋>` 후 편집 설치를 갱신한다. 모델·라벨·실험 기록·진척 기준 변경 없음. 기존 usage log 파일은 보존해도 된다(새 코드가 없으면 읽히지 않을 뿐이다).

## handoff
- 구현 커밋: 71fabbdcd74784eb4e360815eb17507389e86690. 이 문서 커밋이 뒤따른다. 통합 순서: 구현 커밋 → 문서 커밋. cherry-pick은 ./develop 안에서.
- HTML: artifacts/pilot-usage-record-20261026/index.html(ignored, 합성 예시). 로컬 정적 서버에서 렌더 확인(스크린샷, 가로 넘침 없음)했고 파일을 사용자에게 전송했다. 임시 서버 설정은 삭제했다. file:// 직접 열기는 하지 않았다.
- 기본 checkout에서 통합 후 확인할 것: 전체 suite 재실행(worktree의 오류 104는 ignored 파일 부재), tools/release/verify_install_rollback.py 7/7, README 충돌(claude/pair-control이 README.md를 수정함).
- 미검증: 실제 모델·실사진 요청의 지연 분포, 장시간 동시 기록, 로그 회전, 소비 서비스 연동.
- F2 pending·전체 30/100 유지. 이번에 끝난 부분은 측정 수단이다. 남은 조건은 승인된 배포, 7일 이상 실제 사용 기록, 정상 카드 30실물 확인, Gemini·검토 시간 실측이다.

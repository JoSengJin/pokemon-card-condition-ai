task_id: release-package-rollback-20261025
owner: Claude
status: ready_for_review
base_sha: 416e2edf40cb221c81caaf81863afab54793fdeb
branch: claude/release-package-rollback-20261025
worktree: 세션에서만 전달
assignment: Codex task 문서가 없어 Claude가 계약안을 제시했고, 사용자가 채팅에서 "개발 이어나가"로 진행을 지시했다(2026-10-25). Codex의 통합 전 계약 검토가 필요하다.

goal: 릴리스 manifest로 고정한 패키지 버전·checkpoint SHA를 설치본 CLI가 추론 전에 검증해 불일치를 거절하고, 저장소 밖 격리 설치에서 fixture 릴리스 A→B→A 복구 후 패키지·SHA·결과가 A와 같다.

allowed_files:
- card_condition/release.py (신규)
- card_condition/listing_model.py (release= 인자, 결과 release 블록)
- card_condition/cli.py (listing-predict --release)
- pyproject.toml (version 0.4.99 → 0.5.0)
- README.md (release 실행 한 단락)
- tests/test_release.py (신규)
- tools/release/verify_install_rollback.py (신규)
- docs/collaboration/tasks/release-package-rollback-20261025.md
- ignored 산출물: artifacts/release-rollback-20261025/{results.json,index.html}

forbidden_files: region_model.py, listing_readiness.py, visibility_model.py, data/, 라벨·사람 정답, 기존 실험 기록, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, 비밀 설정, 운영 Gemini 경로, A3 브랜치/worktree.

contract:
- manifest 키는 정확히 release_id, package_version, input_contract="listing-request-v1", checkpoints{region 필수, observation·recall 선택: {file, sha256}}. file은 manifest 폴더 기준 상대경로이며 절대경로·`..`는 거절한다. supported·image_size·architecture·전처리는 checkpoint meta가 정본이며 manifest에 중복하지 않는다(SHA가 고정).
- 추론 전 거절: 설치 패키지 버전 불일치, input_contract 불일치, 파일 SHA 불일치, 로드 후 model_sha256 ≠ manifest(로드 중 교체), 미등록 역할, 파일 누락. 최신 파일 탐색·자동 선택 없음.
- `--release`와 직접 checkpoint 인자를 함께 쓰면 거절한다. 직접 `listing-predict CHECKPOINT REQUEST` 출력은 그대로이며 release 키를 넣지 않는다.
- release 결과에 release{release_id, package_version, input_contract, manifest_sha256, checkpoint_sha256{역할}}를 넣는다.
- 오류는 기존 CLI 경로(stderr JSON·requires_gemini·exit 1, stdout 비움)를 사용한다. 새 예외 계층·fallback 없음. 미지원·사진누락·관찰미확인·보류·centering_not_evaluated·whole_listing_observability_not_validated 의미는 유지한다.

structure (함수 수 전→후, 실측은 handoff):
- card_condition/release.py: 신규 → 3 이하
- card_condition/listing_model.py: 3 → 3
- card_condition/cli.py: 1 → 1
- 새 호출 경로: main → ListingAnalyzer.__init__ → read_release → file_sha256 (3회). 기존 main → ListingAnalyzer.__init__ → RegionAnalyzer.__init__ → load_probe_model → … 경로에 전이를 추가하지 않는다. analyze 경로 불변.

checks:
- tests/test_release.py: 정상 수용·결과 release 블록, SHA·버전·계약 불일치 거절, 로드 중 교체 거절, 손상 checkpoint 시 stdout 비움, 직접 checkpoint 호환, --release와 checkpoint 동시 사용 거절.
- 기존 tests/test_listing_model.py, tests/test_cli_checkpoint_error.py, 관련 listing 테스트 재실행.
- tools/release/verify_install_rollback.py: 합성 region checkpoint A/B, wheel 0.5.0+fixture.a/.b를 scratch 격리 venv에 --no-deps 설치. A 실행 → B 실행 → A 재설치 → 버전·SHA·결과 A 일치, 교차 manifest 거절 확인.
- HTML: artifacts/release-rollback-20261025/index.html 생성·내용 대조·열기.

experiment: 불필요. 학습·실사진 추론·성능 비교 없음. 합성 checkpoint는 무작위 초기화이며 품질 근거가 아니다.

handoff:
- 구현 커밋: 88208dfa2b6f58f68813c6749d0bd3722cf54121 (이 문서 커밋이 뒤따른다). cherry-pick 순서: 구현 커밋 → 문서 커밋.
- 변경 파일: card_condition/release.py(신규), card_condition/listing_model.py, card_condition/cli.py, pyproject.toml(0.4.99→0.5.0), README.md, tests/test_release.py(신규), tools/release/verify_install_rollback.py(신규).
- 핵심 diff: `ListingAnalyzer(checkpoint=None, ..., release=None)`. release가 있으면 read_release로 버전·계약·파일 SHA를 확인한 뒤 그 파일만 로드하고, check_loaded로 로드한 model_sha256을 manifest와 대조한다. release를 쓰면 결과에 `release`를 넣는다. CLI는 `listing-predict [CHECKPOINT] REQUEST --release`이며 둘 중 정확히 하나만 받는다.
- 구조 실측(ast): release.py 신규 3, listing_model.py 3→3, cli.py 1→1, tests/test_release.py 신규 6, verify_install_rollback.py 신규 5. 새 경로 main → ListingAnalyzer.__init__ → read_release → file_sha256(3회), main → __init__ → check_loaded(2회). 기존 RegionAnalyzer 로딩·analyze 경로에는 전이를 추가하지 않았다. 재귀 없음.
- 검사:
  - `.venv/bin/python -m unittest discover -s tests -p 'test_release.py'` OK(4), `-p 'test_listing*.py'` OK, `-p 'test_cli*.py'` OK. git diff --check OK.
  - 전체 `unittest discover -s tests`: 789개 중 오류 104. 오류 101개는 `nemotron-review.json` 누락, 3개는 worktree에 없는 ignored artifacts(kieuk13/14, fixed67 worker)이며 cross-review·학습 감사 모듈이다. 이번 변경 파일과 무관한 환경 의존으로 판단하지만, 기본 checkout에서 통합 후 재실행해야 한다.
  - `tools/release/verify_install_rollback.py --work <scratch 밖 경로>`를 88208df에서 실행해 7/7 PASS. 저장소 밖 venv에 wheel 0.5.0+fixture.a/.b를 --no-deps --no-index로 설치했다. 1 A 실행(exit0, model b9ad05e4…, pred c3bf8f94…) → 2 B 실행(exit0, 72817497…/74de402c…) → B 설치본에 A manifest(exit1, 버전 불일치, stdout 비움) → 3 A 재설치(exit0, A와 버전·SHA·release·predictions 일치) → 변조 checkpoint(exit1, SHA256 mismatch, stdout 비움). 모듈은 저장소 밖 site-packages에서 import했고, review.html·review_chat.html 리소스가 있다. 기본 venv의 pokemon_card_condition-0.2.0 editable 설치는 변경되지 않았다.
  - wheel SHA: a 61f2a28ae1ac8344a2b668630e636118043138c44bcf4935071a212f914ae7ab, b b834d2a9dcf9761c33d870c5a11b4482a1e60ba013a12b99cddc5976e5651040 (합성 fixture, 배포용 아님).
- HTML: artifacts/release-rollback-20261025/index.html(ignored). 내용 대조: PASS 7·FAIL 0·SHA 88208df·30/100·단계 표 일치. `open` exit 0(열기 요청 성공). 브라우저 pane과 Playwright가 file:// 열람을 차단해 렌더 화면은 확인하지 못했다.
- 미검증: 실제 품질 통과 checkpoint의 릴리스(후보 없음), observation·recall을 포함한 설치본 release 실행(단위 경로만 공유, fixture 미포함), 승인된 소비 경로(PokeCollector) 연동, MPS 장치, 다른 Python 버전, 의존성 포함 깨끗한 설치(torch는 기존 venv 경로를 .pth로 읽음).
- 리스크: wheel A/B는 코드가 같고 버전 문자열과 checkpoint만 다르다. 즉 이전 코드 버전으로의 복구가 아니라 패키지·checkpoint 쌍의 복구를 검증했다. pyproject 0.5.0 승격으로 기존 소비자의 버전 비교가 바뀔 수 있다. manifest 파일과 checkpoint를 같은 폴더에 두어야 한다.
- 롤백: `./develop -- git revert <문서 커밋> 88208df` 후 editable 재설치. 모델·라벨·실험 기록은 변경하지 않았다.
- F1: pending 유지(30/100). 이번에 끝난 부분은 릴리스 식별·추론 전 불일치 거절·격리 설치·이전 구성 실제 복구(합성)이다. 남은 조건은 C/D 품질 통과 후보, 그 후보의 릴리스 고정, 승인된 소비 경로 통합 검증, 배포 승인, 장애 시 기존 경로 복귀의 소비 측 검증이다.

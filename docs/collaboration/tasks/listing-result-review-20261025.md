task_id: listing-result-review-20261025
owner: Claude
status: ready_for_review
base_sha: ad4219d38591ee2f952ccd1f4f5f4650f2f319dc (release-package-rollback-20261025의 끝, F1 release 블록에 의존)
branch: claude/listing-result-review-20261025
worktree: 세션에서만 전달
assignment: 사용자가 채팅에서 E2 사용 흐름 개발과 성능 검토를 함께 지시했다(2026-10-25). Codex task 문서는 없다. 통합 전에 Codex가 계약을 검토해야 한다.

goal: listing-predict 결과 하나에 대해 원본 사진·근거 구역·릴리스/모델 SHA·칸별 판정 또는 보류 이유를 보여 주는 화면에서 사람이 모든 칸을 검토·정정하고, 같은 결과에 묶인 별도 검토 기록으로 완료를 남긴다.

allowed_files:
- card_condition/listing_review.py (신규)
- card_condition/cli.py (listing-review, listing-review-record 하위 명령)
- README.md (한 단락)
- tests/test_listing_review.py (신규)
- docs/collaboration/tasks/listing-result-review-20261025.md
- ignored 산출물: artifacts/listing-result-review-20261025/{demo.html,index.html,decisions.json,record.json,fixture/}

forbidden_files: listing_model.py, release.py, region_model.py, listing_readiness.py, pyproject.toml(F1 소유), review.py·performance_view.py(재사용만), data/, 라벨, 실험 기록, development-progress.json, PROGRESS_CRITERIA.md, PokeCollector, Gemini 경로.

contract:
- 입력: listing-predict JSON 결과와 그때 쓴 request JSON. id가 다르거나, 사진 SHA가 결과의 input_photo_sha256와 다르면 페이지를 만들지 않는다.
- 페이지: 원본 사진(EXIF 보정 JPEG 내장), 사람 카드 영역, 3×3 근거 구역(전부 보류인 구역 표시), 사진·카드 영역 누락 면 표시, 릴리스 ID·패키지 버전 또는 "고정 릴리스 아님", model_sha256, 결과 SHA, whole_listing_blockers, 칸별 판정·점수·보류 이유. 외부 CDN·네트워크 없음.
- 검토: 칸마다 confirmed / corrected_defect / corrected_normal / undecidable 중 하나 또는 빈 값. 내보내기 JSON은 결과 SHA·id·칸 목록을 갖는다.
- 기록: 결과 SHA·id가 같고 모든 칸이 정확히 한 번 있으며 값이 허용 목록일 때만 쓴다. 기존 파일은 덮어쓰지 않는다. 빈 칸이 있으면 review_completed=false. ground_truth·used_for_training·changes_model_verdict는 항상 false.
- 모델 판정·보류 의미, centering_not_evaluated·whole_listing_observability_not_validated는 바꾸지 않는다.

structure (ast 실측):
- card_condition/listing_review.py: 신규 → 4 (checked_inputs, side_view, review_page, review_record)
- card_condition/cli.py: 1 → 1
- tests/test_listing_review.py: 신규 → 6
- 경로: main → review_page → side_view → photo(performance_view) = 3회, main → review_page → checked_inputs = 2회, main → review_record = 1회. 재귀 없음.

checks:
- `unittest discover -s tests -p 'test_listing_review.py'` OK(4). test_listing*·test_release·test_cli*·test_review.py·test_review_chat.py OK. git diff --check OK.
- test_performance_view(1)와 test_review_contract·test_review_loop_resilience(23) 오류는 worktree에 없는 ignored 파일(artifacts/kieuk13…, nemotron-review.json) 때문이며 이번 파일과 무관하다. 기본 checkout에서 통합 후 재실행해야 한다.
- 브라우저 실검증: 로컬 정적 서버(127.0.0.1:8791)에서 demo.html 렌더 확인(스크린샷), 42행, 가로 넘침 없음. 5칸만 고른 내보내기는 "미검토 37칸 — 완료로 기록되지 않음", 전부 고르면 "모든 칸 검토". 브라우저 내보내기 바이트 SHA 336f6e37…가 Python 재구성과 같았고, listing-review-record가 42칸·완료·ground_truth=false로 기록했다.

experiment: 불필요. 합성 무작위 checkpoint·생성 이미지만 사용. 모델 품질과 무관하다.

performance_review (읽기 전용, 새 실행 없음, 기존 수치 재인용):
- 최신 후보 20261024T093945-04a7e5e8: 개발 147구역 표면 FN 12/94(12.77%)·FP 13/53(24.53%), typed51 FN 20/51(39.22%). 기준은 FN ≤5%, FP ≤10%이다. 이후 101432(공간 노출 감사)와 103800(joint holdout 가능성)은 진단이며 수치 변화는 0.00%p이다.
- A3 부족표(artifacts/data-coverage-20261024/REPORT.md): train 10칸 중 수량 충족은 엣지-뒤·표면-앞 2칸뿐이고 val은 0칸이다. C1~C5는 앞뒤 모두 충족해야 하므로 모델이 완벽해도 지금은 어느 C 항목도 점수 판정 대상이 아니다. 가장 가까운 칸은 표면(뒤 정상 7단위 부족)과 엣지(앞 양성 8단위 부족)이다.
- 표면 앞면은 같은 head로 독립 정상 대조가 1실물뿐이고, 경계 집중 가설은 지지되지 않았다(101432). 따라서 현재 근거로 특정 head·손실·전처리 변경을 채택할 수 없다.
- 제안 1(실험, Codex 실행): 103800에서 가능성을 확인한 앞면 4-fold 실물 joint holdout을 현재 후보 설정 그대로 실행해, 그룹을 분리한 앞면 표면 FN/FP 기준선을 만든다. 변경 변수는 평가 분리 방식 하나이며 개선 실험이 아니라 이후 개선을 판정할 기준이다.
- 제안 2(자료, 사용자 판단): C3 표면은 뒤 정상 7단위(실물 추가 불필요), C1 엣지는 앞 양성 8단위가 부족하다. 이 라벨을 확보하면 두 항목이 판정 대상이 된다. 라벨 요청·추정은 이번에 하지 않았다.

handoff: 커밋 SHA와 HTML 결과는 아래 커밋 메시지 순서로 기록한다. 롤백: `./develop -- git revert <이 브랜치 커밋들>`. 모델·라벨·실험 기록 변경 없음. F1·E2 pending, 30/100 유지.

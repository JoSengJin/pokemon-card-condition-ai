# 보류 worktree 19개 확인·통합 결과 — 2026-11-05

**개발 진척 78/100(v1.13), 변화 0점. 19개 확인, 32KB 수정 1건 통합, 원래 worktree·브랜치 전부 보존.**

검증 소스 main `8bfb16050989668ad4ebd3f8d299a156368c8aa9`; 통합 `8bfb16050989668ad4ebd3f8d299a156368c8aa9` ← 원본 `0ce69d886576927264b3bcb1bbafcfa4cae46098`. 이후 보고 문서 커밋과 구분한다.

제외된 pair-control worktree 두 곳은 이번 턴에 읽기·수정·정리하지 않았다. 해당 서버·미커밋 변경을 조회하거나 조작하지 않았다. 과거 자동 상태는 사용자 제공 snapshot으로만 인용한다. 소스 충돌 없이 main 기존 .claude/ 미추적 파일을 보존하고 이번 허용 경로만 stage했다.

## 항목별 판정

| branch | 제안/결과 | HEAD |
|---|---|---|
| codex/review-manifest-dedupe-20261025 | 기통합·archive 사용자 결정 | `4ef75f4491c31c22ff459b255ec449ca9ea57df2` |
| claude/adopt-train-batches-20261031 | 보류·기록 정정 | `7a0a56c7b59a043a9e6e2f52a5bc587be3a6b15b` |
| claude/card-corner-click-review-20261031 | 보류 | `f44896f64b8eaa6b24e8a97eaac6d63938cb7c5c` |
| claude/a3-data-intake-batch-20261025 | 사용자 결정 | `6c0d7ba6d81815082f385b55c58be3938d68f786` |
| claude/mobile-label-pages-20261031 | 보류 | `2d74f82bfe6ee5a2c23b1393281324b2ce929a8c` |
| claude/surface-normal-coexclusion-implementation-20261025 | 기통합·초안 보존 | `ee6587a6e94942457ae4f20fb9dc225a27b7b753` |
| claude/review-correct-input-20261025 | 통합 | `0ce69d886576927264b3bcb1bbafcfa4cae46098` |
| claude/task-1026-1 | 기통합·문서 재적용 보류 | `a3508669bedfe54c6c4cc5eb16e85726df0d54b5` |
| claude/task-1026-2 | 사용자 결정·보존 | `341acc95acf2a0e20d824ad5d66f44447aa55210` |
| claude/task-1027-1 | 사용자 결정·보존 | `d964af5ae60cdc68aaa484719da55b981c15916c` |
| claude/task-1027-3 | 사용자 결정·보존 | `16dce587f5c8b27774d5dced64dd5f79ff9ea798` |
| claude/task-1027-4 | 사용자 결정·보존 | `5f1b17c3ea2dd180901e155b0590600ab34afb01` |
| claude/task-1028-1 | 사용자 결정·보존 | `1e5a8db9c0c255a30444db60ea81c3caeca2b5b3` |
| claude/task-1028-2 | 사용자 결정·보존 | `2dfde1819bd3f900805f92ea2ec5b9f4b7fb822c` |
| claude/task-1028-3 | 사용자 결정·보존 | `43d2532ac03ea802e901d35c9d2e861e5a2ad660` |
| claude/task-1028-4 | 사용자 결정·보존 | `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf` |
| claude/task-1028-5 | 사용자 결정·보존 | `d2d8843d56eb45b02d7908774319a44c1990e6b5` |
| claude/task-1028-6 | 사용자 결정·보존 | `8c8a8224e1eeee4276ca4b29892a0ac655e51106` |
| claude/task-1028-7 | 사용자 결정·보존 | `d65948283f91363c9c2926a079f386f79b32ce25` |

### codex/review-manifest-dedupe-20261025

4ef75f4491c31c22ff459b255ec449ca9ea57df2→785e21f11030d1635228ad863d44e9e0bc18cb77 기통합. 읽기 전용 DB의 exact-cwd 조회에서 소유 세션01a15109-e475-7c20-b6cb-2f3984059215를 찾음(archived=0,is_pinned=0; 현재 실행 중임/종료됨을 뜻하지 않음). 공식 문서는 연결 채팅 archive 시 관리 worktree 삭제와 snapshot/복원 동작을 설명한다. 이번 요청의 삭제 금지에 따라 archive도 실행하지 않음. 권장: 사용자 승인 후 해당 세션의 앱 archive 절차 사용.

근거: `785e21f11030d1635228ad863d44e9e0bc18cb77`; `artifacts/worktree-followup-20261105/app-owner.json`; [OpenAI 공식 worktree 문서](https://learn.chatgpt.com/docs/environments/git-worktrees)

전체 전달 커밋 대응:
- `4ef75f4491c31c22ff459b255ec449ca9ea57df2` → `785e21f11030d1635228ad863d44e9e0bc18cb77`; Deduplicate review source hashes within 24KB evidence packet; 변경: `card_condition/cross_review_auto_sources.py`, `card_condition/cross_review_evidence.py`, `card_condition/cross_review_evidence_budget.py`, `card_condition/cross_review_evidence_codec.py`, `card_condition/cross_review_evidence_cohort.py`, `card_condition/cross_review_evidence_manifest.py`, `card_condition/cross_review_manual.py`, `docs/collaboration/tasks/review-manifest-dedupe-20261025.md`, `tests/test_cross_review_app_server.py`, `tests/test_cross_review_manifest_budget.py`

### claude/adopt-train-batches-20261031

도구/테스트 미통합. 과거 편입 결과와 코드 통합 상태를 구분하도록 main 계약 status를 blocked로 정정했다. coverage units에 없는 기존 사진은 선행 leak_check가 놓치지만 후단 load_manifest가 train/val 교차를 거절한다. 그 전에 생성된 부분 manifest가 남고 ADOPTION.json은 없다. 누수 채택 성공이라고 주장하지 않는다. 성공·val 불변의 재현 가능한 합성 테스트와 실패 출력 처리 보완 전에는 채택하지 않는다. 명시적 full base SHA 계약도 불명확하다.

근거: `7a0a56c:tools/adopt_train_batches.py:49`; `7a0a56c:tools/adopt_train_batches.py:54`; `7a0a56c:tests/test_adopt_train_batches.py:56`; `docs/collaboration/tasks/adopt-train-batches-20261031.md:34`

전체 전달 커밋 대응:
- `5e3d9f93f173e6bcf69680893fcbe437cf374189` → `5e3d9f93f173e6bcf69680893fcbe437cf374189`; feat(experiments): run back-edge head bagging (ensemble AUC 0.663, criterion not met; single-head AUC std 0.17); 변경: `docs/collaboration/reports/performance-top3-consensus-20261030.md`, `tools/experiments/edge-back-bagging-20261031/plan.json`, `tools/experiments/edge-back-bagging-20261031/worker.py`
- `cd337768df17deb66d6d5c3f4794cb328fd42a52` → `cd337768df17deb66d6d5c3f4794cb328fd42a52`; docs(collaboration): task contract for train-batch adoption tool; 변경: `docs/collaboration/tasks/adopt-train-batches-20261031.md`
- `7a0a56c7b59a043a9e6e2f52a5bc587be3a6b15b` → 대응 없음; feat(tools): adopt reviewed train batches into a new development manifest with val cells unchanged; 변경: `tests/test_adopt_train_batches.py`, `tools/adopt_train_batches.py`

### claude/card-corner-click-review-20261031

현재도 미통합. 순서 검증 계약 불일치와 구조 제한 미충족. 서버는 TL/TR/BR/BL 외 역순·시작점 변경을 허용하며 JS 시험도 역순을 의도적으로 허용한다. review.html의 기존 7함수 초과를 예외 승인으로 보지 않는다. 한 항목을 통합하려고 대규모 UI 분리를 실행하지 않았다. 향후 순서 의미 확정·회귀·구조 보완 필요.

근거: `f44896f:card_condition/regions.py:111`; `f44896f:tests/card_corners.test.cjs:21`; `f44896f:docs/collaboration/tasks/card-corner-click-review-20261031.md:28`; `docs/collaboration/CODEX_RETURN_HANDOFF_20261031.md §6-2`

전체 전달 커밋 대응:
- `ad8e61d38c3dda75873fe79198a1e0a45e5645dd` → 대응 없음; docs(task): card-corner-click-review 작업 계약; 변경: `docs/collaboration/tasks/card-corner-click-review-20261031.md`
- `f44896f64b8eaa6b24e8a97eaac6d63938cb7c5c` → 대응 없음; feat(review): card region by four clicked corners with optional card_corners; 변경: `card_condition/regions.py`, `card_condition/review.html`, `docs/collaboration/tasks/card-corner-click-review-20261031.md`, `tests/card_corners.test.cjs`, `tests/test_regions.py`

### claude/a3-data-intake-batch-20261025

계약만 main 조상, 보고서 커밋84478ed190/54b930d703/6c0d7ba6d8 미통합. 보고서는 2026-10-25 당시 진척30·A3 미충족과 후속 검토 결과를 담는 과거 자료다. 현재 상태로 잘못 읽히지 않도록 역사 문서로 채택할지 사용자 결정. 권장: branch와 Git 제외 감사에서 보존하고 main 문서 추가는 승인 후 수행.

근거: `6c0d7ba:docs/collaboration/reports/a3-data-intake-batch-20261025.md:3`; `PROGRESS_CRITERIA.md:5`

전체 전달 커밋 대응:
- `712cb892a6b8cb867d5f74c09ef8b058c25cb446` → `712cb892a6b8cb867d5f74c09ef8b058c25cb446`; docs(data): A3 실자료 검토와 수집 작업 배정; 변경: `docs/collaboration/prompts/a3-data-intake-batch-20261025.md`, `docs/collaboration/tasks/a3-data-intake-batch-20261025.md`
- `84478ed190600654eb011a3de78e6949fd2ffa44` → 대응 없음; docs(data): A3 실자료 부족량·검토 패킷·수집 명세 준비 결과; 변경: `docs/collaboration/reports/a3-data-intake-batch-20261025.html`, `docs/collaboration/reports/a3-data-intake-batch-20261025.md`, `docs/collaboration/tasks/a3-data-intake-batch-20261025.md`
- `54b930d703272e7943ee31c1a3726641e3b85d7d` → 대응 없음; docs(data): A3 준비 인계와 HTML 열기 결과 기록; 변경: `docs/collaboration/reports/a3-data-intake-batch-20261025.md`, `docs/collaboration/tasks/a3-data-intake-batch-20261025.md`
- `6c0d7ba6d81815082f385b55c58be3938d68f786` → 대응 없음; docs(data): 라운드 1 채택 결과와 라운드 2 준비 기록; 변경: `docs/collaboration/reports/a3-data-intake-batch-20261025.html`, `docs/collaboration/reports/a3-data-intake-batch-20261025.md`, `docs/collaboration/tasks/a3-data-intake-batch-20261025.md`

### claude/mobile-label-pages-20261031

계약에 base_sha 없음(merge-base를 계약 base로 확정하지 않음). importer가 box_reviewed=true인 기존 상자를 다른 값으로 덮어쓰는 합성 반례. 테스트 파일은 함수/메서드 10개로 ≤7 위반. main의 후속 mobile_edge_zone_label_pages.py와 상당 부분 중복되고 현 소비경로는 기존 Codex 채팅이다. 구판 전체 채택보다 필요한 안전한 importer 범위만 별도 계약하는 방향을 제안.

근거: `2d74f82:tools/mobile_label_import.py:28`; `main:tools/mobile_edge_zone_label_pages.py:80`; `F2_PILOT_PREPARATION.md:5`; `docs/collaboration/tasks/mobile-label-pages-20261031.md:16`

전체 전달 커밋 대응:
- `98878bb78e0ad49ad93e47072565e948427ca01a` → 대응 없음; feat(tools): mobile-only box and edge-area label pages with validated importer; 변경: `tests/test_mobile_label.py`, `tools/mobile_label_import.py`, `tools/mobile_label_pages.py`
- `2d74f82bfe6ee5a2c23b1393281324b2ce929a8c` → 대응 없음; feat(tools): edge-only notice and prefilled recheck pages for mobile labels; 변경: `tests/test_mobile_label.py`, `tools/mobile_label_pages.py`

### claude/surface-normal-coexclusion-implementation-20261025

HEAD ee6587a6e94942457ae4f20fb9dc225a27b7b753는 main 조상. plan SHA 동일. worker 7함수와 테스트의 전체 줄 diff를 확인했다. 주된 차이는 H1/H2/H3 원시 조건·단독 대조 FP 및 유한성 guard·재생 점수 출력·구조 시험 강화다. 검토 범위에서 main에 없는 초안의 고유 의도를 찾지 못했다. 세 파일 SHA 검증 복사본을 artifacts에 보존했고 원래 untracked 상태도 유지. 삭제 판단/실행 없음.

근거: `main:docs/collaboration/tasks/surface-normal-coexclusion-20261025.md:153`; `artifacts/worktree-followup-20261105/draft-comparison.json`; `artifacts/worktree-followup-20261105/worker.py.diff`; `artifacts/worktree-followup-20261105/test_normal_coexclusion_worker.py.diff`

전체 전달 커밋 대응:
- `d7017a6e3f3ec645d3b79c18f8536180b307d8ff` → `d7017a6e3f3ec645d3b79c18f8536180b307d8ff`; docs(experiment): front joint-holdout diagnosis and normal co-exclusion contract; 변경: `docs/collaboration/tasks/surface-normal-coexclusion-20261025.md`
- `386425b4f546aa424f3a88d0e70940eff00e6f22` → `386425b4f546aa424f3a88d0e70940eff00e6f22`; docs(experiment): record call-depth approval for normal co-exclusion task; 변경: `docs/collaboration/tasks/surface-normal-coexclusion-20261025.md`
- `ee6587a6e94942457ae4f20fb9dc225a27b7b753` → `ee6587a6e94942457ae4f20fb9dc225a27b7b753`; docs(experiment): approve corrected normal co-exclusion contract; 변경: `docs/collaboration/tasks/surface-normal-coexclusion-20261025.md`

### claude/review-correct-input-20261025

원본 0ce69d886576927264b3bcb1bbafcfa4cae46098 → main 8bfb16050989668ad4ebd3f8d299a156368c8aa9. 저장 응답·합성 correction.errors로 현재 프롬프트 32666→31440 bytes(한도32000). 관련 mock 회귀207 통과, 기준이 다르면 원문 유지. 실제 correct 응답은 미검증.

근거: `main:card_condition/cross_review_auto_context.py:88`; `main:tests/test_cross_review_correct_input.py:7`

전체 전달 커밋 대응:
- `0ce69d886576927264b3bcb1bbafcfa4cae46098` → `8bfb16050989668ad4ebd3f8d299a156368c8aa9`; fix(review): send identical cohort gates once so correct fits 32KB; 변경: `card_condition/cross_review_auto_context.py`, `docs/collaboration/tasks/review-correct-input-20261025.md`, `tests/test_cross_review_correct_input.py`

### claude/task-1026-1

구현1fec3d7→196664ec, 인계a350866→084a2c3b 기통합. 미대응20cf15f4는 레거시 작업 계약 문서, d2e899fd는 status implementing 변경뿐이다. 현재 main의 integrated 및 2026-10-27 정합 보완이 더 나중 상태다. 구판 implementing을 다시 적용하면 상태가 퇴행한다. 미대응 문서를 폐기한 것으로 기록하지 않는다.

근거: `main:docs/collaboration/tasks/surface-normal-coexclusion-20261025.md:168`; `d2e899fdf07d01052569498d1d00c467915ee73b`; `20cf15f467f87d163bc948a6b29bf3243c9655a5`

전체 전달 커밋 대응:
- `20cf15f467f87d163bc948a6b29bf3243c9655a5` → 대응 없음; docs(task): task-1026-1 작업 계약; 변경: `docs/collaboration/tasks/task-1026-1.md`
- `d2e899fdf07d01052569498d1d00c467915ee73b` → 대응 없음; docs(task): surface-normal-coexclusion 구현 시작 상태; 변경: `docs/collaboration/tasks/surface-normal-coexclusion-20261025.md`
- `1fec3d7e64eb71608adb7528f752581b25fc0015` → `196664eca9e6d344bec6087a41981b955a3dd36c`; feat(experiment): normal co-exclusion diagnostic worker, plan and synthetic tests; 변경: `tests/test_normal_coexclusion_worker.py`, `tools/experiments/surface-normal-coexclusion-20261025/plan.json`, `tools/experiments/surface-normal-coexclusion-20261025/worker.py`
- `a3508669bedfe54c6c4cc5eb16e85726df0d54b5` → `084a2c3b854f59cbe4d5d6f72e10312e8a1ba95c`; docs(task): normal co-exclusion 구현 인계·미실행 검사 기록; 변경: `docs/collaboration/tasks/surface-normal-coexclusion-20261025.md`

### claude/task-1026-2

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 assigned+보관(레거시). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `341acc95acf2a0e20d824ad5d66f44447aa55210` → 대응 없음; docs(task): task-1026-2 작업 계약; 변경: `docs/collaboration/tasks/task-1026-2.md`

### claude/task-1027-1

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 assigned+보관(레거시). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `d964af5ae60cdc68aaa484719da55b981c15916c` → 대응 없음; docs(task): task-1027-1 작업 계약; 변경: `docs/collaboration/tasks/task-1027-1.md`

### claude/task-1027-3

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(깃 검사 실패). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `16dce587f5c8b27774d5dced64dd5f79ff9ea798` → 대응 없음; docs(task): task-1027-3 작업 계약; 변경: `docs/collaboration/tasks/task-1027-3.md`

### claude/task-1027-4

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(깃 실패). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `5f1b17c3ea2dd180901e155b0590600ab34afb01` → 대응 없음; docs(task): task-1027-4 작업 계약; 변경: `docs/collaboration/tasks/task-1027-4.md`

### claude/task-1028-1

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 cancelled(수동으로 잘못 생성). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `1e5a8db9c0c255a30444db60ea81c3caeca2b5b3` → 대응 없음; docs(task): task-1028-1 작업 계약; 변경: `docs/collaboration/tasks/task-1028-1.md`

### claude/task-1028-2

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(잘못명령). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `2dfde1819bd3f900805f92ea2ec5b9f4b7fb822c` → 대응 없음; docs(task): task-1028-2 작업 계약; 변경: `docs/collaboration/tasks/task-1028-2.md`

### claude/task-1028-3

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(과금정책). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다. 과거 다음 가설·자료 부족은 이후 다른 계약의 다중 클릭 실험 및 후속 라벨/D2 평가로 일부 후속 작업이 진행됐다. 이것이 이 레거시 task의 재개 승인이나 특정 실물 대조 조건의 완전 충족은 아니다. 11-04 인계는 새 자료 없는 표면 개선 루프를 종료했다. 같은 과거 질문/완료 라벨을 재요청하지 않는다.

근거: `사용자가 제공한 Claude 상태 snapshot(이번에 재조회하지 않음)`; `docs/collaboration/tasks/surface-all-human-points-20261028.md:47`; `docs/collaboration/CLAUDE_HANDOFF_20261104.md:64`

전체 전달 커밋 대응:
- `1bb2e9f39d8634682cf49a51bb7be8996d623e1f` → 대응 없음; docs(task): task-1028-3 작업 계약; 변경: `docs/collaboration/tasks/task-1028-3.md`
- `43d2532ac03ea802e901d35c9d2e861e5a2ad660` → 대응 없음; docs(task): task-1028-3 성능 개선 근거 부족 인계; 변경: `docs/collaboration/reports/task-1028-3-handoff.md`

### claude/task-1028-4

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(메인인계오류). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다. 과거 다음 가설·자료 부족은 이후 다른 계약의 다중 클릭 실험 및 후속 라벨/D2 평가로 일부 후속 작업이 진행됐다. 이것이 이 레거시 task의 재개 승인이나 특정 실물 대조 조건의 완전 충족은 아니다. 11-04 인계는 새 자료 없는 표면 개선 루프를 종료했다. 같은 과거 질문/완료 라벨을 재요청하지 않는다.

근거: `사용자가 제공한 Claude 상태 snapshot(이번에 재조회하지 않음)`; `docs/collaboration/tasks/surface-all-human-points-20261028.md:47`; `docs/collaboration/CLAUDE_HANDOFF_20261104.md:64`

전체 전달 커밋 대응:
- `f94b8e59128feded6c0c652f1ca2cc449a854781` → 대응 없음; docs(task): task-1028-4 작업 계약; 변경: `docs/collaboration/tasks/task-1028-4.md`
- `9c4f6df3a8c174fa8e7bcaaa79da696314cb51bf` → 대응 없음; docs(task): task-1028-4 상태 보고 — 데이터 부재와 승인 지점; 변경: `docs/collaboration/reports/task-1028-4-status-20261028.html`, `docs/collaboration/reports/task-1028-4-status-20261028.md`

### claude/task-1028-5

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 rejected(레거시). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다. 과거 다음 가설·자료 부족은 이후 다른 계약의 다중 클릭 실험 및 후속 라벨/D2 평가로 일부 후속 작업이 진행됐다. 이것이 이 레거시 task의 재개 승인이나 특정 실물 대조 조건의 완전 충족은 아니다. 11-04 인계는 새 자료 없는 표면 개선 루프를 종료했다. 같은 과거 질문/완료 라벨을 재요청하지 않는다.

근거: `사용자가 제공한 Claude 상태 snapshot(이번에 재조회하지 않음)`; `docs/collaboration/tasks/surface-all-human-points-20261028.md:47`; `docs/collaboration/CLAUDE_HANDOFF_20261104.md:64`

전체 전달 커밋 대응:
- `c81f54bd26b2fa68fe4482a301d2130b9b3f4a17` → 대응 없음; docs(task): task-1028-5 작업 계약; 변경: `docs/collaboration/tasks/task-1028-5.md`
- `d2d8843d56eb45b02d7908774319a44c1990e6b5` → 대응 없음; docs(task): task-1028-5 상태 보고 — 데이터 부재와 승인 지점; 변경: `docs/collaboration/reports/task-1028-5-status-20261028.md`

### claude/task-1028-6

계약 커밋8c8a8224e1eeee4276ca4b29892a0ac655e51106만 존재하고 구현 코드 없음. 사용자 전달 snapshot은 review_pending(검사 실패 포함), 폐기 기록 없음. 폐기로 추정하지 않는다. 권장: 현 상태 유지 후 사용자가 레거시 보관 또는 새 계약으로 재개 중 선택. 실패 원인은 금지된 실행 상태 경로를 읽지 않아 재확인하지 않음.

근거: `8c8a8224e1eeee4276ca4b29892a0ac655e51106:docs/collaboration/tasks/task-1028-6.md:1`

전체 전달 커밋 대응:
- `8c8a8224e1eeee4276ca4b29892a0ac655e51106` → 대응 없음; docs(task): task-1028-6 작업 계약; 변경: `docs/collaboration/tasks/task-1028-6.md`

### claude/task-1028-7

구현 코드 변경 없음; 계약 및 일부 상태·인계 문서만 미통합. 사용자 전달 과거 상태는 assigned·시작 거절(사유 불명). 금지된 pair-control 경로의 state.json은 이번에 읽지 않았으므로 현재 런타임 상태는 미확인이다. 폐기/보관 승인을 사용자에게 올리고 기존 worktree·브랜치는 유지한다.

근거: `branch의 전체 전달 커밋·변경 파일 목록(아래)`

전체 전달 커밋 대응:
- `d65948283f91363c9c2926a079f386f79b32ce25` → 대응 없음; docs(task): task-1028-7 작업 계약; 변경: `docs/collaboration/tasks/task-1028-7.md`

## 실행 검증과 미검증

- `PYTHONDONTWRITEBYTECODE=1 ./develop -- env -u CARD_CONDITION_WORKSPACE_LOCK_FD .venv/bin/python -m unittest discover -s tests -p test_cross_review*.py`: 207개 통과. 최초 상속 lock 실행은 실패1/오류26이었고 임시 fixture와 기본 checkout의 lock identity 차이가 원인. 부모 main lock은 계속 유지하고 자식의 임시 root에 자체 잠금을 쓰게 해 재검증했다. 첫 로그도 보존했다.
- `probes.py`: 4점 순서 3종 수용, 기존 확인 상자 덮어쓰기 수용, importer 테스트 구조10함수, train/val 교차 후단 거절 및 부분 manifest 잔류를 합성 입력으로 확인. 원본 candidate correct 테스트는 main 수정 전1실패/수정안2통과였으며 실제 통합본은 위207개에서 재검증했다.
- `context_budget.py`: 과거 packet·저장 verify 응답을 재사용하되 correction.errors만 합성해, 현재 prompt 구성의 통합 전32666/후31440 bytes를 확인(한도32000, 후 여유560). exact 과거 요청 replay·새 모델 응답으로 주장하지 않는다. 호출·토큰 절감률 미측정.
- 초안3파일 복사 SHA 대조·전체 diff 보존, 19개 branch tip 및 porcelain 전후 동일 확인. main 소스의 import 경로를 기본 checkout으로 사용했고 다른 worktree 환경/서버를 사용하지 않았다.
- 아래 별도 기록의 normal-coexclusion 검사는 합성/mock 회귀이며 실제 fit/모델 평가가 아니다.
- 미실행: card-corner 통합 후 지정 검사(point3_save/test_review_contract/test_review_loop_resilience), 브라우저의 4클릭·undo 실동작, 실제 correct 응답, 실제 train 편입, 학습·성능 실험·사진 추론·외부 AI. 보류된 후보를 통합 검증 완료로 쓰지 않는다. HTML 열기/렌더 최종 상태는 ignored decisions.json에 기록한다.

## 사용자만 결정할 사항

1. task-1028-6: 현 상태 보관 또는 구체 새 계약으로 재개. review_pending을 폐기로 바꾸지 않는다.
2. A3 과거 보고서와 레거시 상태 보고서를 main의 역사 문서로 채택할지 여부. 권장: 당장은 branch에 보존해 현재 상태와 혼동을 피한다.
3. D 목록10개의 폐기/장기 보관 승인. 코드가 없거나 과거 rejected/cancelled라는 이유만으로 삭제하지 않는다. 승인 전 worktree·브랜치 그대로다.
4. 앱 관리 checkout의 연결 세션 archive 여부. 소유 세션은 확인됐지만 archive가 worktree 삭제로 이어질 수 있어 이번 요청에서는 실행 금지다.

## 변경·리스크·롤백

- 변경 파일: `card_condition/cross_review_auto_context.py`(+7줄); `tests/test_cross_review_correct_input.py`(신규2검사·helper, 정의3개); `docs/collaboration/tasks/review-correct-input-20261025.md`; `docs/collaboration/tasks/adopt-train-batches-20261031.md`; `docs/collaboration/tasks/worktree-followup-20261105.md`; 이 보고서. Git 제외 artifacts에는 감사 JSON·합성 검사·로그·초안 복사/해시·HTML을 둔다. 로컬 절대경로·비밀값을 이 원격 문서에 넣지 않는다.
- 핵심 diff: 동일 cohort ID/acceptance만 결과 표 참조로 교체, 다른 기준은 원문 보존. train 편입 문서는 과거 결과와 코드 미통합 상태를 구분하고 blocked를 명시. 다른 구현은 채택하지 않았다.
- 구조: 수정 production 파일 함수1→1, 테스트 정의3개(≤7). 추가 호출은 함수 내부 sorted/json.dumps뿐. 기존 전체 동적 호출 경로나 타 소스의 구조 준수를 새로 인증한 결과가 아니다.
- 리스크: 이 고정 입력의 바이트 여유만 측정했으며 미래 입력은 다시 차단될 수 있다. 브라우저/실제 AI 응답은 미검증. 구판 UI·importer의 발견 문제는 이번에 수정하지 않아 채택 보류다. 초안 보존은 자동 실행·실험 재개 승인이 아니다.
- 롤백: `./develop -- git revert 8bfb16050989668ad4ebd3f8d299a156368c8aa9` 후 관련 mock 회귀·일반 push. 문서 정정은 해당 문서 커밋을 별도 revert. worktree·branch·원본 사진·라벨·모델·진척 기준은 변경하지 않았다. 정리(remove/prune/branch delete)는 수행하지 않는다.

normal-coexclusion 검사 로그 요약:
```
----------------------------------------------------------------------
Ran 6 tests in 0.871s

OK
```

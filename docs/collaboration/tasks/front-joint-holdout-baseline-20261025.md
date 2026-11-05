task_id: front-joint-holdout-baseline-20261025
owner: Claude (준비), Codex (기본 checkout 실행)
status: ready_for_review
base_sha: 416e2edf40cb221c81caaf81863afab54793fdeb (origin/main, F1·E2 브랜치와 독립)
branch: claude/front-joint-holdout-baseline-20261025
worktree: 세션에서만 전달
assignment: 사용자가 성능 개선 제안 1(앞면 joint holdout 기준선)의 개발 진행을 채팅으로 지시했다(2026-10-25). Codex task 문서 없음. 실행 전에 Codex가 계약을 검토한다.

goal: 103800에서 검증만 하고 학습하지 않은 앞면 4-fold 실물 공동 제외 분할로, 현재 후보와 같은 설정의 head를 fold별로 학습해 다른 실물로의 앞면 표면 FN/FP 기준선을 공통 실행기 하나로 측정할 수 있게 준비한다.

allowed_files:
- tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py (신규, 추적 정본)
- tools/experiments/surface-front-joint-holdout-baseline-20261025/plan.json (신규)
- tests/test_front_joint_holdout_worker.py (신규, 합성)
- docs/collaboration/tasks/front-joint-holdout-baseline-20261025.md
- ignored 산출물: artifacts/front-joint-holdout-20261025/index.html(준비 보고)

forbidden_files: card_condition/* 전부(모델·runner 변경 없음), 기존 artifacts/experiments 기록, 라벨, 캐시, development-progress.json, PROGRESS_CRITERIA.md, F1·E2 브랜치 파일.

contract:
- 변경 변수 하나: 앞면 평가 분할(단독 제외 저장 head → 고정 4-fold 공동 제외 head). 특징 캐시(typed-training-tokens.pt, legacy와 features·mask·앞면 토큰 동일 확인), 학습 행 153개(훈련 전용 6개 포함), 실물·클래스 균형 가중치, max_bound, L2=1, threshold 0.5, 뒷면 head(093945)는 그대로 둔다.
- 분할 정본은 103800 joint-fold-proposal.json(SHA 318634349c0f…)이며 worker가 SHA를 대조한다. fold를 다시 계산해 train·held ID가 정본과 순서까지 같은지, 실물·원본 SHA·디코딩 해시 누수가 없는지, 앞면 91행이 각각 한 번만 평가되는지 확인한다.
- 실행 전에 현재 후보 맵을 재생해 093945 maps와 reference before_scores가 2e-5 안에서 같은지 확인한다. 다르면 학습하지 않고 실패한다.
- required_cohorts 11개와 기준은 103800 계획 그대로이다. 기준은 사전 고정이며 결과를 본 뒤 바꾸지 않는다.
- 결과는 독립 시험이 아니고 모델 채택이 아니다. 통과하든 실패하든 앞면 기준선으로만 쓴다.

structure (ast 실측):
- worker.py: 신규 → 7 (sha, check_folds, joint_holdout_maps, front_metrics, render, prepare, finish)
- 학습 경로: 시작 함수 joint_holdout_maps → fit_detail_head → (LBFGS) closure → detail_bag_loss → point_bag_loss = 4회. 모듈 guard(함수 아님)에서 직접 호출해 main을 거치지 않게 했다. closure는 torch LBFGS 콜백이라 정적 확정이 안 되므로 리뷰에서 확인한다.
- 기록 경로: finish → render → side_image → prepared_image = 3회. prepare → check_folds = 1회.
- tests/test_front_joint_holdout_worker.py: 신규 → 6 (synthetic, 중첩 fold, 중첩 fake_fit, 테스트 3개)

run (Codex, 기본 checkout, 잠금 없음·다른 실험 없음 확인 후):
```sh
mkdir -p artifacts/surface-front-joint-holdout-baseline-20261025
cp tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py artifacts/surface-front-joint-holdout-baseline-20261025/worker.py
shasum -a 256 tools/experiments/surface-front-joint-holdout-baseline-20261025/worker.py artifacts/surface-front-joint-holdout-baseline-20261025/worker.py
./experiment --plan tools/experiments/surface-front-joint-holdout-baseline-20261025/plan.json -- .venv/bin/python artifacts/surface-front-joint-holdout-baseline-20261025/worker.py
```
러너는 card_condition/ 또는 artifacts/ 아래 코드만 포착하므로 artifacts 미러가 필요하다. 두 SHA는 같아야 한다. 계획 파일 경로는 러너가 직접 읽으므로 tools 아래 그대로 쓴다.

checks:
- `unittest discover -s tests -p 'test_front_joint_holdout_worker.py'` OK(3): fold 누락·디코딩 누수 거절, 앞면은 자기 fold head만·뒷면 불변, 가중치 클래스 질량 균형·max_bound 전달, FN/FP 분모·새 오답·복구 집계.
- 러너 계획 검사를 실험 폴더를 만들지 않고 읽기 전용으로 재현: acceptance 형식, reference record completed·SHA 검증, point guard 일관성, required_cohorts 11개 동결과 기존 기준 보존 OK.
- 실제 정본 대조(읽기 전용, 사진·추론 없음): 재계산 fold의 train/held ID가 정본과 같음(74/23, 75/22, 71/26, 77/20, 앞면 91행). typed·legacy 캐시의 features 동일, 앞면 토큰 동일.
- 미실행: 실제 fold 학습·점수·required cohort 판정(Codex 실행 대상), 사진 디코딩 해시 대조, HTML 사진 패널 생성.

experiment: 필요. 가설 ID surface-front-joint-holdout-baseline-20261025. 사전 기준 FN<=12, FP<=13, 새 오답 없음, required_cohorts 기존 기준. 대조 근거 artifacts/experiments/20261024T103800-512a2260/result.json.

handoff: 아래 커밋. 리스크: 4개 fold는 학습이 겹쳐 독립 복제가 아니다. 앞면 실물은 클릭 8, 정상 8뿐이라 수치 변동이 크다. 같은 사진 대조는 여전히 1실물이다. 롤백: 이 브랜치 커밋 revert, 실행 후에는 실험 폴더를 기록으로 보존한다. 진척 30/100 유지.

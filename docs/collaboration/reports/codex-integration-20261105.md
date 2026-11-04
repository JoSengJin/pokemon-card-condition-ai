# Claude 전달 SHA 통합 검토 — 2026-11-05

개발 진척 **78/100, v1.12, 이번 변화 0점**. 전달 소스 `987480bf4bb3bf0008403d63317f33b1ebb6eea5`의 회귀 테스트 999개 통과. 성능 개선·독립 검증·운영 채택을 새로 확인한 작업이 아니다.

## 범위와 핵심 diff

fetch 후 origin/main은 `9daa425f06aa8c70415f0a72565cfc7a45ec835b`. 전달 브랜치와 main의 HEAD는 동일한 `987480bf4bb3bf0008403d63317f33b1ebb6eea5`; 23개 커밋, 32개 파일이다. main에 이미 포함되어 cherry-pick/revert는 수행하지 않았다. 후속 커밋은 검토 문서·HTML과 기존 인계 문서의 공백 정리만 포함한다.

- 제품: `back_triage_cli.py` 사용 기록/요약 옵션, `back_triage_usage.py` JSONL 계측, 관련 테스트. 시범 인증은 항상 false이며 F1은 pending.
- 실험: 8개 worker/plan 및 문서. 새 모델·릴리스 후보 채택 없음.
- 라벨: force-add된 답/매핑 5개는 과거 근거 그대로 보존. 미확인 라벨을 추정하거나 추가 라벨을 요청하지 않았다.
- 진척: 기존 승인 원문·F1 보류 기록. 기준/배점/점수 변경 없음. `PROGRESS_CRITERIA.md`, `development-progress.json`, v1.12 snapshot을 읽고 earned 합 78과 F1 pending을 확인했다. 전체 과거 verified 근거를 새로 독립 재심사한 것은 아니다.

## 실행 검증

1. `git fetch origin main` 성공. 시작 시 tracked 변경 없음, untracked `.claude/` 보존. `./develop --check` 성공. 프로세스 확인 시 다른 실험/자동 검토 없음(이번 unittest만 실행 중).
2. `.venv/bin/python -m unittest discover -s tests`: 권한 상승 실행 **999 tests / 136.730s / OK**. 로그: `artifacts/codex-integration-20261105/unittest-unsandboxed.log`. 외부 모델 호출을 위한 실행이 아니라 기존 합성·mock·회귀 검사다.
3. 첫 시도는 검토자가 잘못 붙인 `./develop`의 잠금 상속 때문에 999개 중 failures=4/errors=122. 직접 실행한 샌드박스 시도는 failures=8/errors=8(HTTP bind 및 격리 실행 환경 제약). 이 둘을 통과로 기록하지 않으며 로그를 보존했다. 권한 상승 재실행은 소스를 고치지 않고 통과했다.
4. AST로 변경 Python 13파일의 함수 수를 계수. 카드 집계 worker만 8개, 나머지는 1~6개. AST 호출식과 suite의 part 구성 코드를 대조해 CLI 엣지 경로 6전이를 확인했다. 전체 최대 깊이 인증은 하지 않았다. 로그: `artifacts/codex-integration-20261105/structure.json`.
5. 기존 실험 8건의 `record.json`은 completed, `evaluation.json`의 criterion_met는 모두 false. record에 등록된 파일의 SHA-256은 모두 일치했다. 재실행 없이 읽기/무결성 검사만 했다. 목록: `artifacts/codex-integration-20261105/experiments.json`.
6. ViT-B 가중치 346378731 bytes, SHA-256 `0b8b82f85de91b424aded121c7e1dcc2b7bc6d0adeea651bf73a13307fad8c73` 확인. 다운로드·추론·학습 없음.
7. `git diff --check 9daa425..HEAD`의 기존 인계 문서 65행 trailing whitespace를 정리했다. 최종 diff-check는 후속 커밋 직전에 실행한다.

## 구조·절차 위반 처리

- 과거 worker의 함수 8개는 그대로 보존한다. 검토자가 과거 증거 보존 예외를 설명한 뒤 사용자 답변 **“이번엔 그냥 둬”**를 받았다. 이번 보존 결정이며 일반 규칙 완화나 새 실행 승인이 아니다. 재사용하려면 별도 규칙 준수 구현/계획이 필요하다.
- 실제 CLI 경로는 `main → run → BackTriageSuite.analyze → BackEdgeTriage.analyze → zone_scores → view_tensors → prepared_image`로 **6전이**다(원래 main은 run 없이 5전이). **최대 4 규칙을 충족하지 않는다.** 사용자에게 초과 사실을 알렸으며 이번에는 기존 소스를 보존한다. 동적 PyTorch forward/최적화 callback·importlib worker 경로는 최대 깊이 미인증이다. 구조 검사를 통과했다고 보고하지 않는다.
- 과거 main 직접 작성·develop 미사용·D1 기술 분석 사용은 소급 해소할 수 없다. D1 자료를 다음 후보의 미사용 독립 시험으로 재명명하지 않는다.
- 과거 비교의 성능 HTML 의무는 개선 성공 여부와 무관하므로 Claude의 “개선 없음이라 해당 없음” 해석은 맞지 않는다. 이번 성과/진척 HTML은 생성하되 과거 사진별 성능 HTML 누락을 해소한 것으로 쓰지 않는다.
- 재판정 도구 2개에는 오류였던 “화이트닝은 정상” 안내가 남아 있다. 과거 증거로 보존하고 새 라벨 요청에 재사용하지 않는다. §97 재정정과 실제 안내문 차이를 함께 읽어야 하며 라벨 불일치 원인/라벨 천장 인과는 미확인이다. 기준 본문의 표면 화이트닝 문구와 이전 페이지 안내도 일치하지 않아 후속 라벨 규약 정리가 필요하다. 사용자 정답/기준은 이번에 수정하지 않았다.

## 성능·진척 해석과 미실행

새 성능 평가 없음. FN/FP·분모·이전 대비 %p 변화는 이번 작업에서 미측정이다. 저장된 실험 8건은 모두 사전 기준 미충족이며 일반화 개선 미확인. 표면/모서리 앙상블의 개발 신호는 채택 근거가 아니고 엣지는 구간이 0을 포함한다. 속도·Gemini 절감률도 새로 측정하지 않았다. F1/F2 pending, 센터링/앞면 미지원 유지.

새 학습·사진 추론·실험 재실행·외부 AI 호출·깨끗한 venv 휠 설치/업그레이드 복구 재검증은 하지 않았다. ignored 사진/가중치/실험 기록을 원격 push가 전달하지 않는다. 매핑 JSON은 로컬 절대경로를 포함해 다른 checkout에서 바로 재현할 수 없다. force-add 자료는 이번 인계에 포함된 과거 이력이며 이력 재작성은 하지 않는다.

## worktree 정리 점검

등록된 다른 checkout 27개를 점검해 전부 보존, 삭제 0개. 이번 전달은 별도 checkout이 없다. 직접 main 조상인 예전 checkout 1개도 미커밋 2줄과 ignored 파일 22847개가 있어 보존했다. 나머지는 미통합/커밋 대응 미확인/앱 관리/오래된 등록이다. 고유 증거·사용 중 여부 확인 없이 정리하지 않았다. 로컬 감사: `artifacts/codex-integration-20261105/worktrees.json`.

## 리스크·롤백

구조 기준 미충족, 라벨 규약 모순, D1 봉인 범위 밖 분석, 과거 성능 HTML 누락은 남는다. 이번 통합 검증을 모델 품질/운영 준비 판정으로 사용할 수 없다.

원격 반영은 `git push origin main`만 사용하고, 성공 뒤 원격 main과 로컬 HEAD를 재확인하여 `artifacts/codex-integration-20261105/sync.json`에 기록한다. 이 문서의 검증 소스 SHA와 후속 문서 커밋 SHA를 구분한다.

롤백은 실행/잠금을 먼저 확인하고 `./develop -- git revert <대상 SHA>` 후 관련 검사·일반 push. 제품 사용 기록 기능은 `f667522`, 실험 기록은 전달된 각 커밋으로 개별 선택한다. 전체 통합을 되돌릴 때는 이후 의존 커밋부터 역순으로 검토하며 force push/reset --hard를 사용하지 않는다. ignored 자료는 삭제하지 않아 별도 복원이 필요하지 않다.

## HTML 산출물과 열기

`docs/collaboration/reports/codex-integration-20261105.html`: 실제 합성/회귀 검사 결과·78점·변경 목록·미검증·리스크·롤백을 담은 정적 로컬 HTML. 모델 성능 그래프/새 사진 추론은 없다. 열기 명령 결과는 로컬 `html-open.json`에 기록하며 명령 성공과 실제 렌더 확인을 구분한다.

## 전달 변경 파일 전체

- `artifacts/consistency-relabel-20261104/answers.txt`
- `artifacts/consistency-relabel-20261104/selection.json`
- `artifacts/zone-relabel-20261104/answers-1-60.txt`
- `artifacts/zone-relabel-20261104/answers-61-275.lines`
- `artifacts/zone-relabel-20261104/selection.json`
- `card_condition/back_triage_cli.py`
- `card_condition/back_triage_usage.py`
- `development-progress.json`
- `docs/collaboration/CLAUDE_HANDOFF_20261104.md`
- `docs/collaboration/reports/back-triage-suite-contract-20261103.md`
- `docs/collaboration/reports/f1-back-triage-release-20261104/README.md`
- `docs/collaboration/reports/performance-top3-consensus-20261030.md`
- `docs/collaboration/tasks/claude-handoff-20261104.md`
- `tests/test_back_triage_usage.py`
- `tools/experiments/card-aggregation-cv-20261104/plan.json`
- `tools/experiments/card-aggregation-cv-20261104/worker.py`
- `tools/experiments/corner-bb-ensemble-cv-20261104/plan.json`
- `tools/experiments/corner-bb-ensemble-cv-20261104/worker.py`
- `tools/experiments/edge-bb-ensemble-cv-20261104/plan.json`
- `tools/experiments/edge-bb-ensemble-cv-20261104/worker.py`
- `tools/experiments/surface-bb-ensemble-20261104/plan.json`
- `tools/experiments/surface-bb-ensemble-20261104/worker.py`
- `tools/experiments/surface-corrected-labels-cv-20261104/plan.json`
- `tools/experiments/surface-corrected-labels-cv-20261104/worker.py`
- `tools/experiments/surface-flip-tta-cv-20261104/plan.json`
- `tools/experiments/surface-flip-tta-cv-20261104/worker.py`
- `tools/experiments/surface-negfilter-cv-20261104/plan.json`
- `tools/experiments/surface-negfilter-cv-20261104/worker.py`
- `tools/experiments/surface-vitb14-cv-20261104/plan.json`
- `tools/experiments/surface-vitb14-cv-20261104/worker.py`
- `tools/relabel_consistency_page.py`
- `tools/relabel_zone_pages.py`

HTML 열기 실제 결과: macOS 기본 앱은 -10661 오류로 실패. Codex 브라우저 패널 열기는 queued(요청 접수)이며 실제 표시/렌더는 미확인. 정적 HTML 파싱 및 점수/SHA/테스트/리스크 내용 대조는 통과.

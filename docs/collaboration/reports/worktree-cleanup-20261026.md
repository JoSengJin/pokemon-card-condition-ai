# Claude worktree 정리 — 2026-10-26

개발 진척률 30/100 (usable-card-analysis-v1.0, 변화 0%p). main 통합 완료 checkout 13개 제거, 최근 완료 1개와 미통합/작성 중 5개 유지. 모델 학습·추론·성능 평가·외부 AI 호출 없음.

- 확인 기준 main SHA: `0ff00a45032e760b3b11a3ccb22288bc67438bbb` (정리 전후 동일).
- 모든 제거 대상의 main 대비 고유 커밋을 main 로그의 전체 SHA cherry-pick 기록과 대조했다. 미커밋/untracked 없음, 기존 개발 잠금 비차단 획득 후 일반 git worktree remove 성공.
- Git 제외 증거 11개 압축본의 파일별 SHA-256과 압축본 SHA-256 확인. 총 3701730 bytes. 재생성 환경/캐시는 보존하지 않았다.
- 제거 13개 경로 부재, 유지 6개 HEAD/status 불변 재확인. 앱 관리 Codex worktree와 별도 Codex 작업은 이번 Claude 디렉터리 정리 범위에서 제외.

| 브랜치 | 전달 SHA | 결과 |
|---|---|---|
| `claude/cross-review-worker-only-scope-20261025` | `8aebeb7d7eb05bcc4c7c669d168cbad1b9b7bc8d` | 제거 |
| `claude/data-acquisition-followup-20261025` | `c8315fff4668dae573e0de41c75556db55ea8e38` | 제거 |
| `claude/data-acquisition-strategy-20261025` | `3b498c61fe4e5aab5abb087794828260dcd74baf` | 제거 |
| `claude/a3-data-intake-batch-20261025` | `6c0d7ba6d81815082f385b55c58be3938d68f786` | 유지: main 통합 대응 불명/미통합 |
| `claude/evaluation-metrics-contract-batch-20261025` | `03811eae0d27afe607f692a755182a14fe83075a` | 제거 |
| `claude/evidence-snapshot-preparation-batch-20261025` | `e96c9fa02304fa9e6f6c0bf5353d8f9ff6a387ab` | 제거 |
| `claude/front-joint-holdout-baseline-20261025` | `7b6be457ddf5cd098e3fd5365885c999b28ae7dd` | 제거 |
| `claude/gold-example-selection-20261025` | `3e23bd890adf292af53e325026b63f1c6b1eea5f` | 유지: 최근 완료 롤백용 |
| `claude/listing-result-review-20261025` | `c52726f6977b770ac8f2e58a1b300e3ec8bd6892` | 제거 |
| `claude/metrics-neighbors-contract-20261025` | `c872e9649d2092eb1d2ad08a68e4284d22f421f1` | 제거 |
| `claude/surface-normal-coexclusion-contract-20261025` | `332f2646498db64a69361704e61702bd11addd4f` | 제거 |
| `claude/surface-normal-coexclusion-implementation-20261025` | `ee6587a6e94942457ae4f20fb9dc225a27b7b753` | 유지: 미커밋 파일 |
| `claude/pair-control` | `7209d863d649dd9916246a682a544c12ac40ca70` | 유지: main 통합 대응 불명/미통합 |
| `claude/provenance-source-followup-20261025` | `e07c3175b9442e54b1354f0e89f16eb63c81451f` | 제거 |
| `claude/review-correct-input-20261025` | `0ce69d886576927264b3bcb1bbafcfa4cae46098` | 유지: main 통합 대응 불명/미통합 |
| `claude/release-package-rollback-20261025` | `ad4219d38591ee2f952ccd1f4f5f4650f2f319dc` | 제거 |
| `claude/side-evidence-contract-20261025` | `d8079f807a6f902aa40a3faca79e1593de934602` | 제거 |
| `claude/side-evidence-validator-batch-20261025` | `3d807d6658d45075a0444f6f73edd55be27c46bd` | 제거 |
| `claude/task-1026-1` | `a3508669bedfe54c6c4cc5eb16e85726df0d54b5` | 유지: main 통합 대응 불명/미통합 |


변경 파일: AGENTS.md, PAIR_CODING.md, 이 보고서. 핵심 diff: 검증·push 후 최근 완료 작업 1개만 유지하는 정리 단계를 명시. 감사 정본과 HTML은 Git 제외 `artifacts/worktree-cleanup-20261026/audit.json`, `index.html`. 검사: 위 경로/HEAD/status/압축본 대조 및 git diff --check. 앱 열기/렌더 상태는 로컬 감사 기록에 별도 기록한다.

리스크: 제거한 가상환경은 재설치가 필요하며 기존 로컬 worktree 링크는 끊긴다. 미통합 대응이 불명확한 작업은 자동 채택/삭제하지 않았다. 모델 성능 검사를 실행하지 않았으므로 FN/FP 변화·일반화 개선은 미측정.

롤백: Git 브랜치와 커밋은 보존했다. git worktree add <복원 경로> <위 브랜치 또는 SHA>로 checkout을 다시 만들고 감사 JSON의 archive/file_sha256을 대조해 해당 증거만 복원한다. .venv는 requirements-tested.txt 기준으로 재설치한다. main 코드 롤백은 통합 SHA의 git revert와 관련 검사 후 일반 push를 따른다. 협업 규칙만 되돌릴 때는 이번 문서 커밋을 revert한다.

HTML 열기: Codex 패널 열기 요청은 queued. macOS open은 -10661(연결 앱 없음), 브라우저는 file URL 정책으로 차단됐다. 실제 렌더링은 미확인이다.

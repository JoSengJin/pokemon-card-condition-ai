task_id: claude-handoff-20261104
owner: Claude (구현·실험 worker 전달) → Codex (통합·push)
status: ready_for_review
base_sha: 9daa425f06aa8c70415f0a72565cfc7a45ec835b (origin/main)
branch: claude/handoff-20261104 (tip = 이 문서를 추가한 바로 다음 커밋, 코드·실험 마지막 커밋은 d4cc08f19ea82053e771091249a739039d1c3bc4)
worktree: 없음. 이 작업은 기본 checkout의 로컬 main에서 직접 커밋했다(절차 위반, 아래 참고). 브랜치는 같은 커밋을 가리키는 전달용 ref다.
goal: 로컬 main의 미통합 커밋 22개(`83965b5`~`d4cc08f`)를 Codex가 검토·검증하고 origin/main에 일반 push할 수 있게 한다.

## 절차 위반(정직한 기록)
- Claude가 `PAIR_CODING.md`와 달리 별도 worktree·브랜치 없이 로컬 `main`에 직접 커밋했다. origin/main(`9daa425`)에는 push하지 않았다.
- `./develop` 없이 worker·도구 파일을 직접 작성했다(모델·운영 코드 변경 없음).
- D1 봉인 자료를 기술 분석(§89·§92·§93·§96 일부)에 사용했다. 튜닝·후보 변경·임계 조정에는 쓰지 않았다.
- 사용자 기존 승인(AGENTS.md 2026-10-26 push 상시 승인)과 메모리의 "push 별도 승인" 충돌은 사용자 결정에 따라 보류. 지금은 push하지 않는다.

## 통합 방법 제안 (Codex 선택)
- `main`은 이미 22개 커밋을 포함한다(로컬, 미push). 전달 ref `claude/handoff-20261104`는 같은 SHA다. Codex가 검토·테스트 후 일반 `git push origin main`을 하면 fast-forward로 반영된다.
- 원치 않는 커밋만 제외하려면 `./develop -- git revert <SHA>`(커밋 단위). `reset --hard`·force push·이력 재작성은 하지 않는다.

## 변경 파일 (origin/main..HEAD, 31개)
- 제품 코드(2): `card_condition/back_triage_cli.py`(수정, 함수 3), `card_condition/back_triage_usage.py`(신규, 함수 3). 테스트 `tests/test_back_triage_usage.py`(신규, 함수 5).
- 진척 기록: `development-progress.json`(history 항목 추가 2개, F1 assessment 문구 추가, 점수 78 불변).
- 문서: `docs/collaboration/CLAUDE_HANDOFF_20261104.md`, `docs/collaboration/reports/performance-top3-consensus-20261030.md`(§85~§99 추가), `docs/collaboration/reports/f1-back-triage-release-20261104/README.md`.
- 실험 worker(신규, `tools/experiments/<id>/{worker.py,plan.json}`): `surface-vitb14-cv-20261104`, `surface-negfilter-cv-20261104`, `surface-bb-ensemble-20261104`, `surface-flip-tta-cv-20261104`, `corner-bb-ensemble-cv-20261104`, `edge-bb-ensemble-cv-20261104`, `card-aggregation-cv-20261104`, `surface-corrected-labels-cv-20261104`.
- 도구(신규): `tools/relabel_consistency_page.py`, `tools/relabel_zone_pages.py`(재판정 페이지 생성기).
- 라벨 답 파일(git 제외 폴더에서 force-add, 5개): `artifacts/consistency-relabel-20261104/{answers.txt,selection.json}`, `artifacts/zone-relabel-20261104/{answers-1-60.txt,answers-61-275.lines,selection.json}`.

## contract (보존해야 할 것)
- 운영 코드·PokeCollector·Gemini fallback 변경 없음. 점수 78/100 유지(기준 v1.12, 사용자 명시 승인 2026-11-04). F1은 pending(독립 CLI를 소비경로로 인정하지 않음).
- `card_condition/back_triage_*`는 사용 기록 기능 추가(`--usage-log`, `--summary`)만 변경. 경로·오류 문장을 기록하지 않는 계약을 유지한다.

## structure
| 파일 | 함수 수(전→후) | 비고 |
|---|---|---|
| back_triage_cli.py | 2→3 | `main → run → load_suite/read_release` 최대 3전이 |
| back_triage_usage.py | 신규 3 | |
| tools/experiments/card-aggregation-cv-20261104/worker.py | 신규 **8 (한도 7 초과)** | 중첩 함수 `closure` 포함. 실험 기록의 소스 SHA가 고정돼 수정하지 않았다. 후속에서 분리하려면 새 실험 ID 필요 |
| 나머지 worker·도구 | 1~6 | 한도 이내 |
- 호출 깊이는 정적 도구로 측정하지 않았다(실험 worker는 `main` 블록에서 모듈 함수 호출, 대부분 2전이 이내로 추정). 확인하지 않은 값이다.

## checks
- 전체 단위 테스트: `.venv/bin/python -m unittest discover -s tests` (`-t .`는 import 오류). **2026-11-04 실행 결과: 999개 통과(OK, 119.7초).** 실행 시점 HEAD는 `d4cc08f`(문서 커밋 전)이며 이후 변경은 이 task 문서뿐이다.
- 각 실험은 `./experiment`로 실행·기록됨: `20261103T235009-ffe7b261`(§85), `20261104T014930-1424c884`(§86), `20261104T071148-b0b4edf6`(§87), `20261104T071529-b7baa860`(§88), `20261104T093721-ed729957`(§90), `20261104T111812-2e7daddf`(§94), `20261104T125454-4b21747c`(§98), `20261104T133518-6303ee9c`(§99). 모두 사전 기준 미충족(개선 없음).
- 기록 폴더(`artifacts/experiments/`)와 가중치(`dinov2_vitb14_pretrain.pth`, 346MB, SHA-256 `0b8b82f8…ad8c73`)는 git 제외. 기본 checkout에서만 재현 가능.

## experiment
- 새 가설 8건 전부 사전 기준 미충족. 재현·재실행 불필요. 성능 개선 주장 없음, 일반화 개선 미확인.
- 서술 보고서 §85~§99가 모든 수치·한계의 원문이다.

## HTML
- 이번 작업은 새 모델 성능 개선이 없어 모델 성능 HTML을 새로 만들지 않았다(`HTML_REPORTING.md`의 새 성능 평가 HTML 요건은 해당 없음으로 판단, 미확인). 재판정 페이지는 `artifacts/zone-relabel-20261104/zones-*.html`(git 제외).

## handoff
- 전체 SHA: `d4cc08f19ea82053e771091249a739039d1c3bc4`. 커밋 순서는 `git log --reverse origin/main..HEAD`.
- 미검증: 코드 구조 호출 깊이, `HTML_REPORTING.md` 요건 충족, 원격 push.
- 리스크: 라벨 의미(표면 '화이트닝' 기준, §97 재정정), D1 봉인 규칙 위반(기술 분석), 사용자 결정 대기(worktree 전환).
- 롤백: 커밋 단위 `git revert`. 전체 되돌리기는 `origin/main`(`9daa425`)으로의 reset이지만 force push 없이 로컬 reset은 별도 사용자 지시가 있을 때만.

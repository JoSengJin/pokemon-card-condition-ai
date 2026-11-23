# Codex 메인 인계 준비 체크포인트 (Claude 메인 → Codex, 2026-11-13)

**준비 문서다. 역할 이양은 완료되지 않았다.** PAIR_CODING.md §7에 따라 새 메인(Codex)이 아래를 실제 Git·실행 상태와 대조해 일치할 때만 인수하고, 인수 전에는 Claude만, 인수 후에는 Codex만 상태를 바꾼다. 인수 후 승인된 다음 행동을 수행한 근거가 생기면 그때 "이양 완료"라고 쓴다. 새 프로세스는 이전 대화를 기억하지 못하므로 이 문서와 링크된 기록을 입력으로 쓴다.

## 1. 저장소·작업 상태 (2026-11-13 확인)
- 브랜치 `main`, 로컬 HEAD = origin/main = `9c1e69dc3db33d5d6797a6921959fde9730ba814`(fetch 후 일치). 작업 트리: 추적 변경 없음, untracked는 `.claude/`뿐.
- 이번 세션 커밋(오래된 순): `d940cc8` 독립 판정 사전 등록 초안, `d5f1f70`/`d60cc39` AI 판정자 파일럿 1·2, `777a884` AI-사람 결함 격차 진단, `19c3fd5` 문턱 A 탐색 160, `aeff056` 타 에이전트 루프 프롬프트, `d4b539c` 정정(파일럿·탐색 구역 겹침), `e71073c` 위임 결정 기록, `641e257` 가장자리 갤러리 실험 중단, `9c1e69d` 다음 개발 방향.
- 실행 중 학습·실험·검토·`./develop` 잠금: 이 세션에서 시작한 것 없음. `pgrep`은 다른 Claude 앱 프로세스만 보여 개발 명령 실행 여부는 **다른 세션 상태를 알 수 없음** → 인수 시 `./develop --check` 등으로 직접 확인한다.
- 다른 worktree(`git worktree list`): claude-adopt-train, card-corner-click, data-coverage-provenance, mobile-label, normal-coexclusion-implementation, pair-control, task-1026-1, codex-surface-global-lme-only. `docs/collaboration/tasks/worktree-closeout-20261105.md`에 레거시 종료 결정이 있다(기록 근거). 이 세션은 이들을 건드리지 않았다. 정리는 PAIR_CODING 절차대로 Codex가 판단한다.

## 2. 승인 범위
- 승계되는 것(기존 상시 승인): 검증한 변경의 main 통합과 일반 `git push origin main`(force·이력 재작성 금지). 이번 세션 push는 모두 이 범위.
- 이번 세션에서 **승인된 새 실험·새 학습·Gemini/Codex 호출은 없다.** AI 판정은 사용자 지시로 서브에이전트 3~12개를 판정자로 썼다(Claude 하위 에이전트, 외부 API 아님).
- 사용자 결정 대기(승계되지 않음, Codex가 임의로 정하지 않는다): ① 제품 출력을 순위 중심으로 바꿀지와 AUC +0.03 게이트 처리 ② 문턱 A 합의를 평가·학습 신호로 허용할지 ③ 새 학습 실험 승인. 사용자가 "네가 답해"로 위임한 항목(문턱 A 채택, 사람 반복 불가, 통과 조건 유지)은 `reports/independent-judgment-decisions-20261113.md`에 Claude 답변으로 기록돼 있고 번복 가능하다.
- 게이트 FN≤67/370, FP≤112/1406, AUC +0.03, `development-review.json`, 기존 라벨은 변경하지 않았다.

## 3. 현재 결론 한 장 요약
병목은 정답 정의와 게이트의 불일치다(표현 6가설 탈락, 임계 보정 비채택). 문턱 A(확대 없음) AI 판정자 파일럿 alpha 0.666→0.680이지만 가장자리 경계 모호성 때문에 통과 선언 없음. 탐색 160곳(파일럿 40 포함, 독립 아님): 칸별 합의 결함 TN 0%, FP 12%, FN 19%, TP 46%, 가중 9.6%, 저장 점수 vs 합의 가중 AUC 0.943(0.897~0.975). 사람 검증은 하나도 없다. 가장자리 갤러리 실험은 사전 등록 후 중단(사람 근거 예시 0건, 독립 40구역 없음).

## 4. 열린 항목과 점유 파일
- 열린 계약·검토·통합 대기: 없음(task 계약을 새로 만들지 않음). 다음 후보는 `NEXT_DEV_DIRECTION_20261113.md` P0(순위·예산 지표 분석), P1(스케일·FP 칸 진단·소음 강건 학습).
- 점유 파일: 없음. 새 스크립트는 `tools/diagnostics/independent-judgment-20261112/`에 있으며 Claude가 소유했던 파일이다.
- **알려진 결함(미수정)**: `build_pilot.py`의 파일럿·본 표본 중복 제거 버그(`z in pilot`이 항상 거짓)와 그룹 상한이 칸 안에서만 적용되는 문제. 본 판정(0.667)을 다시 하려면 수정 후 표본 재생성이 필요하다. `errata`는 `reports/independent-judgment-pilot-result-20261113.md` 하단.
- `build_instructions.py`: v1 파일이 있으면 v2 생성 블록에 도달하지 않는다(v2는 일회성 import로 생성됨). 재생성 시 순서 주의.

## 5. 증거·산출물 위치(Git 제외, 이 checkout `artifacts/independent-judgment-20261112/`)
`sample.json`(파일럿·본·갤러리·시드), `crops/`, `pilot_responses/`·`pilot2_responses/`·`main_responses/`(AI 판정 원응답), `pilot_results.json`·`pilot2_results.json`·`main_explore_results.json`, `rater_instructions_v2.txt`, `instructions*.html`, `report.html`. 원본 사진·응답은 Git에 없다. 이 디렉터리는 이 checkout에만 있으니 다른 worktree로 옮기려면 복사·SHA-256 검증 후 지운다.

## 6. 실행한 검사와 하지 않은 검사
실행: 합성 시뮬레이션(`sim_alpha.py`), 파일럿·탐색 분석 스크립트, 저장 점수 vs 합의 AUC 계산(이 세션 일회성 코드, 스크립트 미저장), HTML 열기 요청(`open` 성공, 렌더 미확인), push 후 원격 SHA 일치. **하지 않음**: 새 학습·사진 추론, 단위 테스트 스위트, 사람 판정, 실제 외부 판정자 모집, `./experiment`·`./review` 실행.
⚠ AUC 0.943 계산 코드는 저장소에 없다. 인용하려면 재현 스크립트를 먼저 추가해야 한다.

## 7. 인수 체크리스트 (Codex)
1. `git fetch origin main`; HEAD와 `9c1e69d` 일치 확인, 이후 커밋이 있으면 먼저 검토.
2. `git status`, 진행 중 Git 작업, `./develop --check` 상태·잠금(`flock`) 확인.
3. 이 문서와 `NEXT_DEV_DIRECTION_20261113.md`, `independent-judgment-decisions-20261113.md`, `PROGRESS_CRITERIA.md`/`development-progress.json`(v1.13, 78/100)를 읽고 사용자 결정 대기 3개를 사용자에게 확인.
4. 승인된 다음 행동만 수행(결정 전에는 P0 분석까지). 새 학습·추론은 기본 checkout 단일 담당, `./experiment --plan`으로만.
5. 인수 기록을 `docs/collaboration/` 인계 문서에 남기고, 그 뒤에야 "이양 완료"라고 쓴다.

## 8. 롤백
이 세션 커밋은 모두 문서·진단 스크립트 추가뿐. `git revert <SHA>`로 개별 되돌림. 모델·라벨·게이트·`development-review.json` 변경 0.

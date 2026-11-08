# 다른 구현 세션에 전달할 프롬프트 — α=0 / 합성 검사만

사용자가 별도로 전달한 신규 worktree를 작업 폴더로 열고 아래를 수행해라. 기본 checkout에서 구현하지 마라. 작업은 사용자가 이 프롬프트를 전달한 뒤에만 시작한다.

1. `git status --short`, `git branch --show-current`, `git rev-parse HEAD`와 AGENTS.md·PAIR_CODING.md를 먼저 읽어라. 브랜치는 `codex/surface-global-lme-only-20261109`여야 한다. source 기준은 `e52e4e7d669d553b549daef7b94e8226ed142cfa`다. 최초 checkout HEAD는 사용자에게 전달된 배정 커밋이며, 이 전달 프롬프트의 최종 커밋(`git log -1 --format=%H -- docs/collaboration/prompts/surface-global-lme-only-20261109.md`)과 같아야 한다. 이 파일은 구현 세션에서 수정하지 않는다. 이미 미커밋/진행 작업이 있거나 기준이 다르면 reset/stash/강제 checkout하지 말고 확인 결과를 보고해라.
2. `docs/collaboration/tasks/surface-global-lme-only-20261109.md`를 **작업 계약**으로 읽고 소유 파일·금지 범위·합성 검사·handoff를 따라라. 메인 통합과 실제 실험 담당은 이 작업을 배정한 원래 Codex 대화다. 너는 구현 담당이며 메인 역할을 인수하지 않는다.
3. 자기 `.venv`와 기존 고정 의존성을 준비하고 `card_condition.__file__`이 자기 worktree를 가리키는지 확인해라. 다른 checkout의 환경·data·artifacts·모델·비밀 설정을 복사/연결하지 마라. 모델 다운로드나 provider 초기화도 하지 마라. 모델·worker 수정은 자기 checkout의 `./develop -- <수정 명령>` 안에서만 수행해라.

Git이 추적하는 일부 과거 artifacts는 checkout에 이미 존재할 수 있다. 그대로 보존하고 학습/합성 fixture의 입력으로 쓰지 마라. 다른 checkout의 ignored 실자료를 추가로 복사·연결하지 말고, 계약의 자기 신규 합성 산출물만 작성해라.

**구현 목표는 변수 하나다.** 기준 `tools/experiments/surface-globalmix-gradient-recording-20261108/`를 읽고 계약의 신규 `tools/experiments/surface-global-lme-only-20261109/`에만 구현해라.

```text
기존: B + 0.5*M + 0.5*G
수정: B + alpha*M + (1-alpha)*G, alpha=0.0 고정
B = 기존 정상/결함 bag + L2
M = 모든 학습쌍 softplus 손실의 산술평균
G = 모든 학습쌍 전체 flatten log-mean-exp (결함별 row-LME 평균이 아님)
```

총 순위계수1이며 α 외 변수는 바꾸지 마라. 일반 alpha 설정기/CLI/탐색 옵션은 만들지 마라. 최적화 총loss와 성분기록 계수를 함께 맞춰 `arithmetic_rank`의 값/gradient가0, `global_pair_lme`가전체G가 되게 해라. 산술0은 graph에 연결된 tensor로 남겨 기존5성분 autograd/합 검증이 동작하게 해라. zero-gradient cosine을 임의 숫자로 채우지 마라.

출력 maskedmax→sigmoid·threshold0.5·사람라벨·mask·분할·mass·정상tau0.1·결함max·L2=1·seed/초기화/백본·optimizer·수렴/예산·평가기준을 유지해라. `metrics.py`와 `armijo_direction.py`는 바이트 동일하게 복사하고 worker는 계약의 가설ID 외 학습/평가 블록을 바꾸지 마라.

합성 검사는 계약 항목을 실제로 수행해라. 특히 전체G 단독의 독립 수식/autograd/유한차분, row-LME와 구분되는 fixture, 0산술성분/5성분합/최종theta, 초기수렴/거절trial/덮어쓰기 방지, Armijo/중복trial/1250평가/함수수·호출4전이를 검증해라. α=0에는 이전 산술혼합의 gradient floor가 없어지므로 그 기대값을 억지로 유지하려고 ε항 등을 추가하지 마라. 새 목적함수의 학습계수·점수·trace가 이전50:50과 같아야 한다고 요구하지 마라. 같은 입력/같은 파라미터에서의 bag/L2와 출력 **식/API** 보존을 검사해라.

실제 학습·모델 비교·사진추론·라벨수정·캐시 replay·`./experiment`·실제 worker·`./review --auto`·외부AI/하위CLI 호출·탐색은 금지다. main 통합/checkout/push·다른 작업 정리도 하지 마라. 실자료가 없다고 정답·점수·검사 결과를 만들지 마라.

허용파일 목록은 task에 적힌 신규6개 Python·신규보고서·task status/checks/handoff만이다. 필수 결과는 자기 worktree의 합성 로그/검증JSON/HTML과 추적 보고서다. 열기 성공/렌더 확인/차단을 구분하고 보안정책 우회나 외부 업로드는 하지 마라. 전체 진척78/100 유지, 정확도 개선은 미평가라고 적어라.

완료하면 허용파일만 작업 브랜치에 commit하고 status=ready_for_review로 바꿔라. 전체 tip SHA·base/checkout SHA·변경파일·핵심diff·실제검사 명령/결과·함수수/호출경로·HTML/로그경로·미검증·리스크·롤백을 사용자에게 전달해라. branch push/PR/main 통합/실험은 하지 마라. 전달 후 같은 브랜치에 추가 변경하거나 worktree를 지우지 마라. 원래 Codex 대화에서 결과를 받아 검토·통합한다.

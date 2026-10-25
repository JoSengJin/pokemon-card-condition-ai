# Codex 복귀 인계 프롬프트 (Claude가 임시로 메인 역할을 맡은 기간)

AGENTS.md, PAIR_CODING.md와 이 문서를 읽고, 아래 확인을 마친 뒤에만 통합·실험을 재개하세요. 이 문서는 새 개발·학습·외부 AI 호출을 승인하지 않습니다.

## 1. 이 기간 동안 한 일과 하지 않은 일

- 한 일: 별도 worktree에서 오프라인 소프트웨어 검증만 했다. 신규 브랜치 `claude/metrics-neighbors-contract-20261025`(base `21809d5`)에 테스트 2개와 문서를 커밋했다. 소스 변경 0.
- 하지 않은 일: main 수정·통합·push, 실제 학습·추론·모델 비교, 라벨·사진 요청, 외부 AI·`./review --auto` 실행, cross-review 계열 파일 수정(Codex 진행 범위), 진척 기준·점수 변경, 관제(`claude/pair-control`) 조작.
- 진척 점수는 30/100 그대로다. 남은 마일스톤(A3, C1–C5, D1–D3, E2, F1–F2)은 모두 사람 라벨이나 실제 학습·독립 시험이 필요해, 사람 입력 없이 할 수 있는 개발은 사실상 소진됐다.

## 2. 복귀 직후 확인 (순서대로)

```sh
git -C <기본 checkout> status --short          # 미커밋 변경 없음
git worktree list                              # Claude/Codex worktree 목록 대조
git log --oneline -8 main                      # 기준 SHA 확인(시작 시 21809d5)
cat artifacts/development-cycle/workspace.lock # 남은 잠금이면 소유 프로세스 확인 후에만 해제 판단
cat artifacts/development-cycle/latest.json   # 최신 handoff와 실제 실험 기록을 대조
```

- Claude 브랜치 중 `claude/pair-control`만 main에 미반영이다(나머지 8개는 `git cherry`로 모두 반영 확인). 이 브랜치는 이번 기간에 건드리지 않았다.
- main이 위 SHA보다 앞서 있으면 그 사이 변경을 먼저 읽는다. 제 브랜치는 rebase하지 않았다.

## 3. 통합 방법

```sh
./develop -- git cherry-pick -x 21809d54cf4d0f7d24ddcec1566ef48a407412cb..claude/metrics-neighbors-contract-20261025   # 브랜치 전체, 순서 유지
PYTHONPATH=tests .venv/bin/python -m unittest test_threshold_contract test_paired_miss_contract test_region_thresholds test_defect_regressions -v
git diff --check
```

정확한 커밋 순서와 SHA는 `docs/collaboration/reports/metrics-neighbors-contract-20261025.md`에 있다. 원격 반영은 별도 승인된 작업만 일반 push한다.

## 4. Codex가 결정해야 할 열린 항목

- 평가 보고서 새 파일 권한 0644→0600 변경 유지 여부(`evaluation_output.write_new_report`, `data_coverage`와 같은 방식).
- A→B→A처럼 읽는 순간에만 바뀌는 입력을 막을 snapshot 구조를 둘지(범용 체계는 계약상 만들지 않음).
- side-evidence sidecar의 저장 위치·작성자·버전 정책, 충돌 진술을 경고로 둘지 A3 차단으로 둘지.
- `listing_readiness` 계약 검증은 torch가 있는 환경에서만 가능하다(이 기간 미검증).

## 5. 재개 시 주의

- 실제 학습·모델 비교는 기본 checkout에서 `./experiment --plan <계획.json> -- <명령>`으로 한 번에 하나만 실행한다. 사전 가설·수치 기준을 먼저 확정한다.
- 휴먼인루프는 사용자 요청으로 일시 중지된 상태다. 재개 여부는 사용자가 정한다. 이미 답한 라벨은 다시 묻지 않는다.
- Claude 쪽 주장(검사 통과·미결함)은 통합 후 Codex가 다시 실행해 확인한 것만 최종 기록으로 삼는다.

## 6. 휴먼인루프 재개와 새 개발 manifest (기본 checkout의 Git 제외 artifacts)

- 2026-10-25 사용자가 라벨 검토 화면에서 카드 h를 정정했다: 뒷면 표면 정답 0→1과 결함점 2개, 앞면 box_reviewed. 29개 요청 구역의 정답은 저장되지 않아 미확인으로 남았다(재질문 금지).
- 사용자가 이 정정을 **새 개발 manifest로 채택**했다. 새 파일: `artifacts/development-manifest-20261025/combined-reviewed.jsonl`(SHA `5b2f3f9e…`), 채택 기록 `ADOPTION.json`. 원본 `artifacts/gengar-edge-learning-20261017/combined-reviewed.jsonl`은 SHA `d971dbca…` 그대로다.
- 이전 manifest 기준 실험·수치와 이 manifest 기준 수치는 h의 정답이 달라 개선으로 비교하지 않는다. 새 실험은 새 manifest를 쓴다고 계획에 명시한다.
- 데이터 부족표 변화는 train 뒷면 표면 하나뿐이다(양성 43/17→44/18). A3 미충족, 진척 점수 30/100 그대로. 검토 서버는 종료했고 모델·학습·외부 AI는 쓰지 않았다.
- `trusted-experiment.json`과 `development-progress.json`은 변경하지 않았다. 기존 경로를 참조하는 곳이 있으면 Codex가 판단한다.

### 6-1. 갱신: 현재 채택된 개발 manifest (2026-10-25 두 번째 검토 반영)

- 현재 채택본: `artifacts/development-manifest-20261025b/combined-reviewed.jsonl`(SHA `4604d1ef…`), 기록 `ADOPTION.json`. 앞서 채택한 `development-manifest-20261025/`(SHA `5b2f3f9e…`)와 원본 `gengar-edge-learning-20261017/combined-reviewed.jsonl`(SHA `d971dbca…`)은 변경하지 않았다. 위 6절의 "새 파일"은 이 문서로 대체한다.
- 변경(채택본 대비 직전 채택본): f 앞뒤 표면 결함(점 2+2), z 뒷면 카드 영역 재지정·표면 결함점 12개·영역 확인 체크, z 뒷면 왼쪽 가운데 엣지 결함 구역 정답(영역 재지정으로 지워진 것을 사용자 승인으로 복원).
- 부족표: 뒷면 표면 양성 44/18 → 52/20, 앞면 표면 51/12 → 52/13, 뒷면 엣지 72/30 유지. 수량 충족 셀은 20개 중 2개로 A3 미충족. 정상 쪽과 뒷면 모서리 정상 부족은 그대로다.
- 구역 정상 판단 28개는 저장되지 않아 미확인이다(재질문하지 않음). 진척 점수 30/100과 모델 성능은 바뀌지 않았고 추론·학습·외부 AI 호출은 없었다.
- 이전 manifest 기준 수치와는 정답이 달라 개선으로 비교하지 않는다. 새 실험은 이 manifest를 계획에 명시한다.

### 6-2. 갱신: 세 번째 검토(구역 정상 판단) 결과와 대기 중인 결정

- 25개 구역 정상 판단은 사용자가 저장하지 않아 모두 미확인이다. 저장된 것은 영역 확인(f 앞뒤, h 뒷면, z 앞면)뿐이다.
- z 앞면 영역 재지정으로 기존 표면 결함 구역 정답 9개(전 구역 1)가 지워졌다. 후보 두 개가 `artifacts/development-manifest-20261025b/`에 있다: `candidate3-restored.jsonl`(복원, 구역 정답 수치가 현재 채택본과 동일하고 영역 미확인 단위만 감소), `candidate3-no-restore.jsonl`(저장 그대로, 앞면 표면 양성 52/13 → 43/12). 설명은 `CANDIDATE3-NOTES.md`.
- **사용자의 복원·채택 결정이 아직 없다.** 현재 채택본은 6-1의 `4604d1ef…` 그대로다. 이 후보를 임의로 채택하지 않는다. 권고는 복원본이지만 결정은 사용자 몫이다.
- 검토 서버(8766)는 종료했다. 이후 검토 화면을 열 때는 서버만 켜지 말고 화면을 실제로 보이게 띄운다(앱 패널이 보이지 않으면 기본 브라우저로 연다).

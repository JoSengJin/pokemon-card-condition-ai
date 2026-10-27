# 기존 다중 표면 클릭 활용: 실제 비교 결과 — 2026-10-28 KST

**개발 진척률 30/100(+0%p). 누락은 4개 줄었지만 새 오탐 2개가 생겨 후보 미채택.** 클로드의 최신 수집·검토 상태를 읽기 전용으로 확인하고, 새 val 자료와 분리해 기존 학습 정답에서 버려지던 클릭만 활용하는 단일 실험을 완료했다.

## 클로드 데이터 보완 현황

아래는 이번 점검 시각의 실제 `review/labels-review.jsonl` 집계다. 제외된 c 실물 1개(점61개)는 점·정상·면 집계에서 뺐다. 정상 수는 질문별 구역 라벨 수이며 사진/독립실물 수가 아니다.

| 묶음 | 레코드 | 제외 실물 | 확인된 영역/면 | 기존 결함점 | 명시적 정상 구역 라벨 |
|---|---:|---:|---:|---:|---:|
| 26-a | 14 | 0 | 25/27 | 152 | 23 |
| 26-b | 19 | 0 | 37/38 | 10 | 634 |
| 27-c | 25 | 1 | 48/48 | 500 | 575 |
| 27-d | 9 | 0 | 16/18 | 174 | 0 |
| 27-e | 19 | 0 | 0/38 | 0 | 0 |

- a~d의 저장 점은 총836개, 정상 구역 라벨은1,232개다. 사람 답이 없다고 모두 미확인인 것은 아니며, 새 e 묶음만 점0·영역확인0이다. 같은 점을 다른 종류로 재해석하거나 완료 라벨을 재요청하지 않았다.
- 모든 입력은 split=val이며 학습·D1 사용 금지다. a~d의 파싱/현재 annotation 구조 검사는 오류0이었지만 이는 사람 정답의 출처 감사나 정식 채택을 대신하지 않는다. b의1면, a의2면, d의2면은 영역 미확인이고, d의 점 없는 면 단위 표면 양성 등 미해결 인계도 남아 있다.
- 최신 ADOPTION은 development-manifest-20261025d다. 새 a~e의 정식 채택·출처/좌표 감사·분모 동결은 확인되지 않았다. 수량만 보고 A3나 학습 준비 완료로 승격하지 않았다. 클로드의 작업 파일·검토 화면·라벨·사진은 수정하지 않았다.
- 근거: 각 묶음 `INTAKE_NOTE.md`, `review/labels-review.jsonl`; 읽기 전용 스냅샷·SHA·구조 검사 `artifacts/surface-all-human-points-20261028/intake-readiness.json`.

## 실제 성능 비교와 판정

대조는 고정 `20261025T122011-647b0e9c`의 같은147구역이다. threshold0.5, 정답·분모·기존 실제점51개 및11cohort 기준을 보존했다.

| 항목 | 기존 | 이번 후보 | 이전 대비 |
|---|---:|---:|---:|
| 결함 누락 |16/94 (17.02%)|12/94 (12.77%)|-4.26%p|
| 정상 오탐 |18/53 (33.96%)|20/53 (37.74%)|+3.77%p|
| 기존 올바른 종류 실제점 누락 |21/51 (41.18%)|21/51 (41.18%)|0.00%p|

새 누락0·새 오탐2·기존 누락4복구. primary_acceptance_passed=false, acceptance_passed=false다. 일부 누락 감소를 전체 성능 개선으로 보고하지 않는다. 독립 시험/일반화 개선은 미확인, 운영 채택0이다. 보류를 분모에서 빼거나 평가 정답을 바꾸지 않았다.

| 변화 | 고정 ID | 사람 정답 | 기존 점수 | 후보 점수 |
|---|---|---:|---:|---:|
| 새 오탐 9 | b/front/normal/upper_left | 0 | 0.482266 | 0.617509 |
| 새 오탐 21 | c/front/normal/upper_right | 0 | 0.483492 | 0.510938 |
| 기존 누락 복구 42 | u/front/normal/middle_right | 1 | 0.489727 | 0.613023 |
| 기존 누락 복구 46 | v/front/normal/upper_left | 1 | 0.477395 | 0.603941 |
| 기존 누락 복구 60 | x/front/normal/lower_left | 1 | 0.492039 | 0.528980 |
| 기존 누락 복구 69 | z/front/normal/middle_right | 1 | 0.477962 | 0.701566 |

## 단일 변경과 모델 원인에 주는 근거

`point_dataset.py`의 fixed grid 경로는 같은 종류·구역의 첫 클릭만 유지한다. 고정 원본에는 기존147구역에 표면83점/51구역이 있다. 앞면은37점/18구역이며, 현재 학습에 쓰지 않던19개 토큰은3실물·9구역에 몰려 있다. 별도 확정 실제점2개를 합치면 앞면20구역/39토큰이다. 이번에는 원래의 첫 점이 포함됐는지 확인하고, 같은 양성 구역 안에서 기존 고유 표면 토큰의 softplus(-logit)를 평균했다.

class/group/bag mass, 기존 첫 점으로 구한 center, zero 초기값, L2=1, max_bound 정상 손실, LBFGS100, gradient<=1e-5, RGB/cache/224,4개 front fold를 그대로 뒀다. ranking 항을 추가하지 않았다. 뒷면13개 추가 토큰은 인덱싱만 확인했으며 학습하지 않았고, 뒷면56개 map은 원본과 byte 동일하다. 각 held 실물의 클릭은 해당 fold 학습에서 제외됐다.

새 오탐은 이전 ranking 후보에서도 흔들렸던 b/upper_left와 c/upper_right다. 다중 클릭 활용으로도 이 정상 구역 오탐을 해결하지 못했다. 특정 무늬/촬영조건/학습 실물이 원인이라는 인과 결론은 내리지 않는다. 이미 확정한 클릭을 더 쓰는 것만으로 기존 실제점51개의 누락은 줄지 않았다.

## 변경 파일과 핵심 diff

- `tools/experiments/surface-all-human-points-20261028/objective.py`: 원본 좌표에서 같은 종류의 고유 토큰을 복원하고, 양성 점 손실만 단일 토큰에서 토큰 평균으로 변경. 기존 fit 설정과 center 보존.
- 같은 폴더 `worker.py`: 기존 고정 기준선을 재생한 뒤 같은4fold에서 한 번 비교, 기존11cohort와147/51 출력 및 사진 보고.
- 같은 폴더 `plan.json`: 가설·성공/실패 기준·입력SHA·신규 source baseline=null을 결과 전에 동결.
- `tests/test_surface_all_human_points.py`: 단일점/약한양성에서 원래 fit과 정확히 같음, 중복 토큰 평균·기울기, mask 밖 토큰/최초점 누락 거절.
- task 문서와 이 MD/HTML: 사전 계약, 실제 결과, 최신 데이터 상태·리스크·롤백.

## 실행 검증·기록

- 구현 source: **70dda822802f543b80a4c6749ae0ee59952a6898**. 격리 브랜치 source5142f4e, 계약6c96d37→main af5e43a. 실제 실행은 기본 checkout에서만 수행했다.
- `PYTHONPATH=tests .venv/bin/python -m unittest test_surface_all_human_points test_ranking_warm_start test_ranking_regression_cause test_same_photo_surface_ranking`: 격리14개 OK(0.971초), main14개 OK(0.971초). 단위 검사는 모델 품질 점수에 반영하지 않았다.
- `git diff --check` 통과. 함수 수 objective4/worker2/test3, 주요 fit→closure→all_point_loss→detail_bag_loss→point_bag_loss 최대4전이.
- 실제 명령: `./experiment --plan tools/experiments/surface-all-human-points-20261028/plan.json -- .venv/bin/python artifacts/surface-all-human-points-20261028/worker.py`.
- 실제 record: **artifacts/experiments/20261027T222515-1d33d82d/record.json**, status=completed,4fit 모두수렴(최대gradient2.91e-6). UTC 폴더명이며 KST 실행은2026-10-28 07:25다. 실패·중단 실행을 성공 수치로 대체한 것은 아니다.
- 저장 map에서147점수 재계산 차이0, 뒷면 map 변경0, 원본 manifest/cache/사진·새 검토파일·record.files의 SHA 보존. post-checks는 저장 map readout만 했으며 추가 fit/head forward0이다.
- 새 backbone forward0, 외부 Gemini/Codex 호출0, 새라벨0, 새 val의 학습0. 모델·worker 수정은 ./develop, 실제 학습은 ./experiment로 직렬 실행했다.
- development-review.json의 session_id가 현재 세션과 달라 이번 자동 handoff/next_steps/token_report는 생성되지 않았다. development-cycle/latest.json의 이전 ai_calls_forbidden 기록을 이번 실험 결과로 바꾸지 않았다.

## 사진·HTML·리스크·롤백

- 모든 앞면91구역: `artifacts/experiments/20261027T222515-1d33d82d/index.html`.
- 새 오탐2/누락복구4 비교: 같은 폴더 `comparison.html`. 기존 첫 점은 빨강, 추가 기존 점은 초록, 모델 최대반응은 파랑이다. 파랑은 위치 정답이 아니다. 사진 위 정답·출력과 전체147/51 분모를 함께 표시했다.
- 공통 기록·입력SHA·수치·MD/HTML 본문 대조 완료. 사진 비교와 이 보고서의 HTML 열기를 요청했고 도구는 모두 queued를 반환했다. 추가 클릭이 표시된 구역 PNG 1개를 직접 확인했으며, HTML 실제 렌더는 미확인이다.
- 위험: 추가 클릭은3실물에 집중돼 실물 다양성을 늘리지 않는다. 새 오탐이 생겨 연구 후보로만 보존한다. 현재 사진의 사용 권한과 의미상 원인·새 val 출처 감사·독립 일반화는 미확인이다.
- 롤백: `./develop -- git revert 70dda82` 후 위 관련검사와 일반 push. 운영 모델·원본 정답은 바꾸지 않았으므로 모델/라벨 복구는 필요 없다. 실험·스냅샷은 실패/미채택 이력으로 보존한다.

## 다음 근거와 에튜 포인트

새 val은 계속 평가 전용으로 보존해야 한다. 다음 학습은 다양한 **새 training 실물**에서 확인한 같은 사진의 결함점–정상 대조가 필요하다. val을 train으로 옮기거나 기존 정답·임계값·평가 기준을 맞춰 바꾸지 않는다. 클로드 수집을 중복 실행하거나 완료 라벨을 다시 요구하지 않았다.

점별 손실을 합하면 클릭이 많은 구역이 과도하게 커진다. 이번에는 구역 안에서 평균하고 기존 실물 가중치를 유지했다. 예를 들어 한 구역에 점이8개여도 총가중치는 그대로다. 그래도 사진 다양성이 늘어나는 것은 아니므로 누락 감소와 오탐 증가를 분리해 판정했다.


## 원격 반영과 checkout 정리

검증 source main/origin70dda822802f543b80a4c6749ae0ee59952a6898 일치를 확인한 뒤 이전 warm-start checkout만 정리했다. 이전 전달2커밋의 main 대응, clean 상태, Git 작업 없음, 비차단 개발 잠금 획득과 고유 lock 증거 SHA 보존을 확인하고 일반 worktree remove를 사용했다. 브랜치/이력은 보존했다. 최신 codex/surface-all-human-points-20261028 checkout(source5142f4e)은 롤백 확인용으로 유지하며 Claude 데이터/미통합/사용 중 checkout은 수정하지 않았다. 감사: artifacts/surface-all-human-points-20261028/worktree-cleanup/audit.json. 이 결과 문서는 별도 커밋으로 일반 push한다. force push/이력 재작성 없음.

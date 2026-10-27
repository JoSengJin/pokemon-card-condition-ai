# 같은 사진 상대순위 감독 후보 — 2026-10-27 실행

개발 진척률 **30/100 (usable-card-analysis-v1.0, +0%p)**. 실제4-fold가 모두 수렴했고, 같은147개 개발 구역에서 **누락16/94→15/94(-1.06%p), 오탐18/53 유지**였다. 하지만 새 누락2·새 오탐2가 생겼고 실제점 누락도21/51로 같아 **미채택**이다.

## 실제 record와 전체 판정

- record: `artifacts/experiments/20261027T145641-21c22382/record.json`
- status=completed, stage=finished, return_code=0.
- primary_acceptance_passed=false, acceptance_passed=false. 새오답0 보호 미통과다.
- 11required_cohort는 모두 미통과다. 기존 기준선도 미통과였으며 기준/정답/분모를 바꾸지 않았다. 새 actual-point guard 위반을 줄였다고 주장하지 않는다.

| 동일 평가 | 기존4-fold | 후보4-fold | 변화 |
|---|---:|---:|---:|
| 전체 구역 누락 |16/94 (17.02%)|15/94 (15.96%)|-1.06%p|
| 전체 구역 오탐 |18/53 (33.96%)|18/53 (33.96%)|0.00%p|
| 앞면 구역 누락 |14/51 (27.45%)|13/51 (25.49%)|-1.96%p|
| 앞면 구역 오탐 |15/40 (37.50%)|15/40 (37.50%)|0.00%p|
| 같은 종류 실제점 누락 |21/51 (41.18%)|21/51 (41.18%)|0.00%p|

구역 복구5개와 새오류4개가 서로 바뀌었다. 실제점51개는 새누락/복구가 각각0이다. 구역 누락 감소를 실제 결함점 검출 개선으로 바꾸어 말하지 않는다. 뒷면은 기존 저장map 그대로이며 같은 개발 자료의 반복 평가다. 독립 일반화 개선은 미확인이다.

## 구현 근거와 감독 범위

기존061542/062258은 같은사진의 실제점과 정상 최대반응 사이 순위 위반을 읽기만 했다. 이번에는 고정 캐시에서 확인한 직접 사람점–명시적 정상3쌍/2실물을 학습에 사용했다. ff69 정상행의reason은 과거 미확인 설명을 유지하지만, 별도 저장된 direct human evidence의 정상0·정확box·photo SHA가 같은지 확인했다. 원문/라벨은 수정하거나 재요청하지 않았다.

기존 전체 손실에 각 실제점의 원래mass × mean(softplus(1 + 정상T.1 logsumexp상한 - 실제점logit))만 추가했다. 계수1/margin1/T.1은 사전고정이며 탐색하지 않았다. 같은 사진/같은 실물의 명시적 정상만 쓰고, 실제점이 정상box안이면 충돌로 중단한다. weak-positive hard-max·기존 정확점/정상 손실·class/group mass·L2=1·LBFGS100·gradient<=1e-5·RGB153·고정4fold·.5임계·뒷면maps는 보존했다. 실패한 smooth-presence와 결합하지 않았다.

각 fold의 training 안에서만 쌍을 만들었다. 쌍의 수는2/3/3/3이며 유일한 원본 감독은3쌍/2실물이다. 합계11을11개 독립표본으로 부풀리지 않는다. held실물·원본/decoded사진은 이전 고정검증대로 학습에서 제외했다.

## 변경 파일·핵심 diff

- `tools/experiments/surface-same-photo-ranking-20261027/objective.py`: 직접 같은사진/종류/정상/기하 검증과 상대순위 손실 추가, 기존 fitter는 base loss와 mass를 보존한다.
- 같은 폴더 `worker.py`: 기존 입력재생/fold검증 재사용, 원래 사용자 정상근거와cache행 일치 검사, training 쌍구성/학습,147/11cohort score/사진 출력.
- 같은 폴더 `plan.json`: 별도 고유가설·사전 수치조건·11cohort·정답/사진/source SHA·code_changes 신규2파일 baseline=null.
- `tests/test_same_photo_surface_ranking.py`: 명시적 같은종류·같은사진만쌍구성/held제외/모순거절,point상승/정상하강 gradient 및bias상쇄,쌍없는fit동치,합성수렴.
- `docs/collaboration/tasks/surface-same-photo-ranking-20261027.md`, 이MD와 동명HTML: 고정범위/실행·미채택·리스크·롤백.

기존 model/학습/추론/라벨링 source는 수정하지 않았다. 이 코드는 명시적 연구 경로이며 운영 API나 Gemini routing에 연결하지 않았다.

## 실행 검증

명령: `./experiment --plan tools/experiments/surface-same-photo-ranking-20261027/plan.json -- .venv/bin/python artifacts/surface-same-photo-ranking-20261027/worker.py`

격리 관련13검사OK(1.099초), main에서 두후보와기존worker관련17검사OK(1.399초). source 함수수 objective4/worker2/test5(합성fixture포함), 주요학습경로 최대3전이. 쌍이 없으면 기존fit coef/bias2e-6·목적값1e-8 이내 동치, rank gradient의전체logit합0(1e-12)을 확인했다.

실제4fit max_gradient는1.1012e-6,8.3035e-7,7.3289e-7,1.0016e-6으로 모두1e-5이하다. 입력/정답/원본사진 SHA와 기준선147구역/11cohort 재생을 확인했다. 저장된4head/maps의147개 최대점수와 observations도 최대차0으로 일치했다(추가fit/모델forward없음, post-checks.json). 검증 sourceSHA: f75c0c57421aa5d6473da966af2a8ee1919262e4.

## 실제 사진·정답·전후 오류

- 전체91앞면구역: `artifacts/experiments/20261027T145641-21c22382/index.html`
- 바뀐9구역(새누락2/새오탐2/복구5): `artifacts/experiments/20261027T145641-21c22382/changes.html`
- 기존 사람점이 있는 경우에만 빨강으로 표시하고 파랑은 모델최대반응이며 위치정답으로 쓰지 않는다. 각 사진의 실제 target/전후 score/.5판정과 위 전체 분모/%p를 표시했다.
- 실행 후 result.json의 확정 수치만 HTML 요약/변경구역 페이지로 정리했다. source·record·score·snapshot을 고치지 않았으며 추가학습/추론이 아니다.
- 사진 HTML의 open 도구는 queued를 반환했다. 로컬PNG1개는 이미지뷰어로 확인했지만 HTML렌더 검증으로 대체하지 않는다. 실제렌더는 미확인이다.

## 리스크·롤백

원본대조3쌍/2실물뿐이며 각 crop맥락도 다르다. 순위 손실을 추가해 수렴했어도 새실물의 실제점 일반화를 보장하지 않는다. 지역지표가1개 좋아져도 새오류4개를 감수할 수 없어 미채택이다. margin/계수 sweep과 같은후보 재시도는 하지 않는다.

코드 제거는 `./develop -- git revert f75c0c5` 후 관련검사와일반push. 운영source/모델/정답이 그대로라 모델snapshot복구 불필요. 새head는 해당 실험폴더에 미채택 상태로 보존하고 record/snapshot/사진은 삭제하지 않는다.

## 에튜 포인트

순위 손실은 두logit의 차이를 쓰므로 bias가 상쇄된다. 예를들어 점과정상logit을 둘다+1 해도 차이는같아서, 전체확신만올리는식으로이감독을만족시킬수없다. 이번에는 그성질을gradient합0으로확인하고 실제누락/오탐으로효과를따로판정했다.

## 보존·호출·원격·정리

Claude의 데이터 보완 checkout·새 사진·정답·manifest·공용 학습/추론 source·운영 Gemini fallback·PokeCollector는 수정하지 않았다. 기존 모델 파일·캐시·사람 응답의 실행 전후 SHA가 같았다. 모든 source 변경은 자기 worktree의 ./develop 잠금 안에서 했고, 실제 학습은 기본 checkout의 ./experiment로 직렬 실행했다. 외부 Gemini/Codex 모델 호출0·새 backbone forward0·새 라벨0·운영채택0이다.

개발 자동검토 policy의 session_id가 현재 세션과 달라 자동 handoff/next_steps/token_report는 생성되지 않았다. artifacts/development-cycle/latest.json은 과거 세션 기록이므로 이번 실행의 대체 근거로 사용하지 않는다. 각 실제 record.json의 status/판정을 사용한다.

최종 관련17검사(main,1.399초)가 통과했다. 합성/계약 검사는 모델 성능이 아니다. source별 AST·호출 깊이는 아래 인계와 task에 명시했다. git diff --check 통과. 실행 record.files의 모든 SHA와 원본 input_sha256을 최종 대조했다.

코드 main/origin f75c0c57421aa5d6473da966af2a8ee1919262e4 일치 확인 후 이 결과 문서를 별도 커밋·일반 push한다. force push/이력 재작성 없음.

이전 Codex coverage·smooth-presence checkout은 전달 커밋의 main 대응·clean·Git 작업 없음·개발 잠금 비차단 획득·고유 lock 증거 SHA 보존을 확인한 뒤 일반 worktree remove로 정리했다. 브랜치/이력은 보존하고 같은사진 ranking checkout을 최신 롤백용으로 유지했다. Claude 데이터/작성 중/미통합/부분통합과 다른 Codex checkout은 보존했다. 감사: artifacts/surface-same-photo-ranking-20261027/worktree-cleanup/audit.json.

## 실제 성능과 진척의 경계

고정 진척은 PROGRESS_CRITERIA.md와 development-progress.json의 usable-card-analysis-v1.0 기준30/100(+0%p)을 유지했다. 같은 개발 자료의 작은 부분 개선은 전 범위 품질·독립시험·실사용 완료가 아니다. 기존11cohort의 기준을 지우거나 완화하지 않았다. 새로운 실제점·정상/독립 정답을 만들지 않았고, 검증 사진을 새 학습에 편입하지 않았다.

같은 loss의 계수·margin·온도·수렴 허용치 탐색을 더 하지 않는다. 신규 정상 실물 다양성과 독립 정답은 Claude 데이터 보완 작업의 의존으로 남는다. 이번 결과로 새 오류를 감수한 운영 채택이나 모델 완성도를 주장하지 않는다.

## 최종 HTML 열기 상태

실제 사진 index/바뀐9구역 changes 페이지, 미채택 결과 요약, 수렴 실패 HTML 모두 Codex 브라우저 도구가 queued를 반환했다. 열기 요청은 전달됐고 실제 HTML 렌더는 미확인이다. 정적 본문/수치/파일 존재 대조와 PNG1개 직접 확인만 수행했다.

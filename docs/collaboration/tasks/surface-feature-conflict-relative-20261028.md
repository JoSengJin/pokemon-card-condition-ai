# 특징 혼동·손실 충돌·crop 상대 입력의 세 작업

- task_id: surface-feature-conflict-relative-20261028
- owner: Codex
- status: implementing
- base_sha: 9a4f63821a31bcadb8099dab78df55c37358b59a
- branch: codex/surface-feature-conflict-relative-20261028
- worktree: 로컬 전용
- goal: 반복 오탐9/21의 특징 혼동과 추가 클릭 학습의 네 손실 gradient를 정량 진단하고, 근거를 남긴 crop-relative 입력 하나를 기존 고정 기준으로 비교한다.

## allowed_files

- tools/experiments/surface-feature-conflict-relative-20261028/analysis.py
- tools/experiments/surface-feature-conflict-relative-20261028/transform.py
- tools/experiments/surface-feature-conflict-relative-20261028/worker.py
- tools/experiments/surface-feature-conflict-relative-20261028/plan-diagnostic.json
- tools/experiments/surface-feature-conflict-relative-20261028/plan-relative.json
- tests/test_surface_feature_conflict_relative.py
- docs/collaboration/tasks/surface-feature-conflict-relative-20261028.md
- docs/collaboration/reports/surface-feature-conflict-relative-20261028.md
- docs/collaboration/reports/surface-feature-conflict-relative-20261028.html

ignored: artifacts/surface-feature-conflict-relative-20261028/ 의고정mirror/사전SHA, 공통실험의새디렉터리 record/diagnostics/head/사진HTML. 다른 파일은 읽기 전용이다. Claude 수집/검토/모든checkout/사진·정답·manifest·cache·과거실험·운영 모델/PokeCollector/Gemini fallback/진척점수·기준은 수정하지 않는다. 외부AI·새라벨·backbone추론0.

## 1. 특징 혼동 진단 (학습0)

기존153cache의384차원 DINO token, 원래4foldhead와 다중점 후보22515-head를 고정한다. 앞면91구역 전체의 logit을 crop평균+peak잔차로 분해하고 기존→다중점 변화의 가산성을1e-8내검산한다. 오탐9/21과 복구4개에서 query peak의 최근접 특징을 해당fold training의 올바른종류 실제점·명시적정상 token에서 찾는다. raw와 crop-relative cosine·pool 크기·실물/구역/토큰을 기록한다. 정상pool이 더 크므로 최근접 유사도를 분류정확도나 특정사진의 인과효과로 해석하지 않는다. held사진/그룹은 neighbor pool에서 제외한다.

## 3. 손실 충돌 진단 (학습0)

각fold의 기존·다중점 저장head에서 고정training mass/center로 exact point·weak presence·normal·L2의 loss/gradient norm/cosine을 분해한다. gradient합과 전체autograd 오차<=1e-10을 확인한다. baseline에서 point-all minus point-first의 변화와 query peak방향도 계산한다. 이는국소미분이며 최종재학습의인과효과/영향함수로확정하지않는다. total은같은loss에서만비교한다.

두진단은 같은공통 ./experiment --plan plan-diagnostic.json -- worker.py 안에서1회직렬실행한다. 저장147점수/11cohort를checkpoint/cache로재생해보존하고, 진단완료를품질개선으로세지않는다.

## 2. 상대 입력 구현과 단일 비교

x_relative[i,k]=x[i,k]-mean(x[i,valid[i]])로각앞면crop내공통특징을제거한다. 사진전체조명분리나raw색보정을증명하는것은아니다. 각crop자신의valid token만읽으므로held/training/다른사진/정답을참조하지않는다. 모양/마스크·기존point·153행·L2=1·max_bound·class/group mass·zero init·LBFGS100·gradient<=1e-5·4fold·뒷면map·threshold.5·기존147/51/11cohort를보존한다. 상대입력만바꾸고다중점loss/ranking/feature concat·새정규화·하이퍼파라미터탐색은없다.

진단 결과에 의미있는 공통성분 변화가 없으면 실험 강행 대신근거부족을기록한다. 실제모델비교를한다면성공조건은원래147 FN<=16/94,FP<=18/53,새오답0,최소1기존복구,typed51새누락0및기존11cohort전체수용이다. 실패/불변/수렴미달시미채택, 기준변경·자동재실행0. 진단결과뒤실험전 plan-relative를고정하고고유ID로실행한다.

## 구조·검사·보고

analysis.py 최대7함수, transform1, worker최대4, 검사최대4. 주요진단gradient→loss helper→detail_bag_loss→point_bag_loss 최대3전이. 실험worker는기존fit_detail_head를직접호출한다. ./develop 안에서소스편집, 구현worktree는합성검사만하며 실제진단/학습은main만 ./experiment로직렬실행한다.

수식가산성·gradient합/국소기울기·최근접held분리·상대입력valid평균0/상수shift불변/패딩불변·출처보존을소수검사로검산한다. MD와HTML에sourceSHA·30/100·같은분모FN/FP/%p·실제record상태/판정·사진 위 사람정답/모델출력·열기도구응답/렌더검증한계를기록한다. 사진/원문응답/홈경로는Git제외HTML에만둔다.

롤백: 통합구현SHA를 ./develop -- git revert 후검사/일반push. 연구전용후보는미채택이면운영변경0, 기존데이터/모델복구불필요. 기록은보존하고최신완료checkout1개만유지한다. 이전checkout의unique snapshot/lock증거는main artifacts로SHA검산보존후일반remove,Claude·미통합checkout은보존한다.

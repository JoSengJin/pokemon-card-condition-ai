task_id: surface-ranking-regression-cause-20261028
owner: Codex
status: integrated
base_sha: 2db0cbe805ed0713ff487dd553813e31ed4dfbed
branch: codex/surface-ranking-regression-cause-20261028

goal: ranking후새FN2/FP2를고정head/cache로분해하여추가성능변경의근거를확정한다. 정답/기준/threshold변경과재학습없음.
allowed_files:
- tools/experiments/surface-ranking-regression-cause-20261028/worker.py
- tools/experiments/surface-ranking-regression-cause-20261028/plan.json
- tests/test_ranking_regression_cause.py
- docs/collaboration/tasks/surface-ranking-regression-cause-20261028.md
- docs/collaboration/reports/surface-ranking-regression-cause-20261028.md
- docs/collaboration/reports/surface-ranking-regression-cause-20261028.html
ignored: artifacts/surface-ranking-regression-cause-20261028/미러·검사,새실험폴더diagnostics/사진HTML/observations만.
forbidden: card_condition/*,이전worker/실험/head/cache/사진·사람정답·평가기준·진척JSON,Claude모든checkout/데이터보완,PokeCollector,운영routing,외부AI. fit/optimizer0.새실험은canonical ./experiment만사용.

입력: 122011/145641의저장4-foldhead와maps,고정153RGBcache/마스크/정확점token,기존4fold제안,145641의147행/11cohort/사진. 모든입력SHA사전고정. source/사진그룹·raw/decoded분리와head.train_ids를기존fold와대조.

분석대상: 147전체와91앞면전체를재생해변경9개를보호대조. 집중4개는기존result가명시한새FN[58,72]/새FP[9,21] 그대로. 경계점점수/실제점존재여부/peak이동을표시하며원래label/분모유지.

사전분해: 공통training center로rawbias복원을구분. Δmaxlogit = Δcentered_bias + (old_peak_feature-center)·Δcoef + (new_peak_feature-old_peak_feature)·newcoef. 가산오차<=1e-8. saved전체maps/147score재생차<=2e-5. fixedcenter의절편만/방향만고정counterfactual이.5경계를넘는지계산하되그출력으로모델/threshold를선택하지않는다.

학습항방향: 같은training쌍3개/2실물에서baseline/candidate점-정상상한margin과rankinggradient를계산. 분석식/autograd최대차<=1e-8,biasgradient<=1e-10. 같은사진쌍의각gradient가4case의centered feature에미치는first-order방향은전체최적화변화의원인확정이아닌국소증거로표시. margin충족여부와softplus항이남는지를사전정의대로보고한다. 새로운label/최적계수탐색없음.

실행판정: 진단검증통과면completed이며학습/모델채택아님.146등분모변경금지.주평가는145641결과를그대로재생(FN15/94·FP18/53·typed21/51),기존11cohort보존. diagnostic_evidence<=4000byte. 실패면해석/자동재시도금지.

구조: worker<=7함수;모듈guard에서원본검증/순차분석실행,새모델계층없음. decompose/gradient계산경로<=4전이. 검사<=7함수. source실측과주요경로를인계.
checks: synthetic가산분해·center좌표이동불변·gradient검산·같은bias이동상쇄. main통합후1회공통진단. 실제성능/독립검증개선으로보고하지않는다.
HTML: 실험index.html에4오류/5복구사진·사람정답/전후점수/분모/%p·가산원인·확정/미확정한계. 추적reports공개집계와30/100·sourceSHA/검사/변경/위험/롤백. 열기요청/렌더구분.
rollback: 통합SHA를 ./develop -- git revert 후검사/일반push. 기존모델/정답미변경으로복구불필요,진단/이전실험은보존. 근거가나오기전새훈련후보는확정하지않는다.

## 구현 인계

worker5/검사3함수(AST실측),모듈guard직접순차호출. 모델학습/optimizer호출없고저장head의cache투영·autograd검산만있다. components는공통center의가산합/peak이동/counterfactual, pair_readout는분석식과기존rankloss autograd를대조한다. source경로 pair_readout→same_photo_ranking_loss 최대1전이이며새계층없음.

격리합성3+기존rank4검사합계7검사OK(3.803초),diff검사통과. peak변경의가산식·center변환시총logit불변·gradient검산/동일bias상쇄를확인했다. 진단성공은모델품질통과가아니다. main재검사와고정모델의실측분해는후속이다.


## Codex 최종실행 인계

record20261027T211902-7ae1cc41/statuscompleted/fit0/91앞면과147점수재생오차0/가산·gradient검산통과/단일쌍인과미확정。원래정답/기준/운영모델/Claude데이터변경0。source·검사·실측·HTML·위험·롤백은동명reports참조。코드main/origin aedfd16일치후문서일반push。기존rank/진단checkout정리·최신warmcheckout롤백용보존·다른Claude/미통합checkout보존감사기록확인。

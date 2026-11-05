# A3 표면 후보 검증 — 실행 2026-10-29, 재개 검산 2026-10-30

**개발 진척35/100 유지. 확인된719구역·643실제점의 평가를 완료했고, 새오탐5건 때문에 후보를 채택하지 않았다.** 새학습0·외부AI0. 새val backbone719회·재생대조2회. 독립시험이 아닌 개발val/모델선택 결과다.

## 변경·검증

- main source dcd39d16fe9b32aeb9d5c30eb6979dfd33171946, 격리 source7be376eb72c2e701983a48475e64ada99ee7bdd7. 일반push완료.
- tools/experiments/a3-surface-transfer-20261029/{data,readout,worker,report}.py와plan.json: 확인된geometry만선택,종류별실제점연결,raw/decoded·실물누수검사,기존head재생,head별sigmoid평균후physical-token최대,사진보고.
- tests/test_a3_surface_transfer.py 신규6검사. task·이보고서·HTML 추가. 함수4/4/3/2,테스트6,최대4전이내.
- 격리71검사OK(6.017초), main동일71검사OK(5.002초): test_a3_surface_transfer test_prepare_a3_evaluation test_data_coverage test_data_coverage_provenance test_local_wear_cnn test_surface_all_human_points test_surface_preserved_heads test_experiment_record. 최초합성검사의float정확일치/임시경로기대만수정. diff검사통과.
- 공통실험 artifacts/experiments/20261028T203138-7d30f998/record.json: completed, acceptance_passed=false. 46head trainID미해결/실물·사진중복0. 기존147/11평가군재생오차0, 앞뒤cache특징대조오차0. 2026-10-30 입력/사진360SHA와record무결성재검산통과.

## 같은 새val 분모의 결과

|면/지표|기존→후보|비율 변화|
|---|---|---|
|앞 구역 누락|36/85→36/85|42.35%→42.35%,0.00%p|
|앞 구역 오탐|148/317→148/317|46.69%→46.69%,0.00%p|
|앞 실제점 누락|186/227→186/227|81.94%→81.94%,0.00%p|
|뒤 구역 누락|5/142→5/142|3.52%→3.52%,0.00%p|
|뒤 구역 오탐|133/175→138/175|76.00%→78.86%,+2.86%p|
|뒤 실제점 누락|193/416→181/416|46.39%→43.51%,-2.88%p|

앞면head는동일하다. 뒤새구역오탐5·새실제점누락0. 일부점복구가전체개선을뜻하지않는다. 기존147구역도FN16/94·FP18/53,legacy51점FN20/51,typed51점FN19/51로필수11평가군미통과. 새val과기존147/51의분모를서로개선비교하지않는다. 관찰제한탐지·E2비보류율은이번에미측정.

## 후속 검증·의존

원래표면758구역/648점중39구역/5점(5실물7면)은box_reviewed미확인이라미지원목록에보존했다. 점수산출된719구역은모두eBay자료다. 새val정상오탐은앞148·뒤138이며,그중physical-token경계최대반응은20/148·32/138이다. 단순경계제거의근거로삼지않았고mask/threshold변경0이다.

기존대조점수를그대로보존한새회귀4묶음(앞/뒤구역·실제점)을 regression-guards/REGRESSION_GUARDS.json에준비하고기존freeze_required_cohorts로4묶음모두검증했다. 기존11묶음도유지한다. 준비이며새실험실행/성능완료가아니다. 평가JSON SHA658fd9d2d1625ee518a0936699ec85c98b57d0c8482bf7269d80fae4d2509d44. 원래record/result는원래147/51회귀를검산하고새val은evaluation.json에서별도검산했다. 이구분을생략하고공통acceptance만새val성공으로해석하면안된다.

사용자는2026-10-30 카드영역7면확인질문에“정상”으로응답했다. 질문범위는파란카드영역이며정상/손상재라벨이아니다. 다음별도task에서geometry확인만새버전에반영한다. 이실험과기존동결본은그대로보존한다.

## HTML·리스크·롤백

실자료 HTML: artifacts/experiments/20261028T203138-7d30f998/index.html. 719패널/719PNG/643점수문구와평가JSON대조완료. 생성crop2개이미지확인. 파일보기요청queued, 전체브라우저렌더미확인. 기존file:보안차단우회0. 신규geometry전용검토화면도queued. C3/E2/D1완료·정확도일반화개선은주장하지않는다. 새ensemble readout은이번개발평가정책이며과거held-fold정책과구분한다.

롤백: ./develop -- git revert dcd39d16fe9b32aeb9d5c30eb6979dfd33171946 후남아있는관련회귀검사·일반push. 라벨/운영모델/소비코드변경0,실험증거보존. DATA_INVENTORY는Git이력/작성자근거를확인할수없고내용도과거A3pending이어서변경·커밋하지않았다.

재개시이전두임시checkout의경로가이미없고Git등록만남아있었다(삭제원인미확인). 통합cherry-pick대응을확인하고일반worktree remove로등록을정리한뒤최신codex/a3-surface-transfer-20261029(7be376e)를동일경로에정상복원했다. 브랜치/커밋·기본checkout산출물은보존했다. 다른작업checkout은건드리지않았다.

에튜 포인트: 회귀보호는평균개선에가려지는새오류를찾는다. 이번에는12점이복구됐지만정상5구역이새오탐으로바뀌어no_new_errors조건이채택을막았다.

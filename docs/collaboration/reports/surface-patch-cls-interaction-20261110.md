# 패치×CLS 단일 표현 결과 — 2026-11-10

개발 진척 **78/100(usable-card-analysis-v1.13) 유지**. 패치×CLS768D는 **AUC 하락·누락/오탐 증가로 가설 미지지, 운영 미채택**이다. 합성 동치·메모리 경로는 검증됐지만 성능 개선은 없었다. PROGRESS_CRITERIA.md/development-progress.json의 점수·조건을 바꾸지 않았다.

## 고정 계획과 실행

- 가설 ID: `surface-patch-cls-interaction-20261110`.
- 실행 소스 SHA `03e722141fc8fd8fdf3d258d7577015b53bc2532`, 계약 `3c34087`. 실행 계획 `artifacts/surface-patch-cls-interaction-20261110/plan.json`, SHA256 `04386b6bed651b2f37f98d205f8f3bc3a7469f450d7b3653096aed7b320826f5`.
- 공통 기록: `artifacts/experiments/20261109T221044-f3b30c8f/record.json`, **completed/exit0**, 5fold 완료. KST2026-11-10 07:10:44→08:09:44. worker 경과3537.432735초(58.957분); 순수 학습 시간·통제된 속도 비교 아님.
- 실제 명령: `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-patch-cls-interaction-20261110/plan.json -- .venv/bin/python artifacts/surface-patch-cls-interaction-20261110/worker.py`.
- 최초 명령은 `code_changes`에 tools/경로를 넣어 prepare가 worker 시작/폴더 생성 전 거절했다. `launch-configuration-rejected.log`, `launch-preflight.json` 보존. 기존 실행기 계약대로7개 runtime .py만 snapshot 등록하고5개 tracked source는 input_sha256/byte-equality로 연결했다. 실제 worker 실행1회·fold학습5회이며, 실패/중단된 모델 실행 재시도0. 기록을 만들려고 실행기를 변경하지 않았다.
- 유일 과학 변수: raw x384D→`[x,x⊙c]`768D. c는 같은448px crop·같은 frozen CPU ViT-S14 forward의 최종LN CLS384D. 별도 CLS단독 block/스케일/정규화/위치항 없음. 원본384D 보존, invalid 추가 성분0, 공유scalar bias. float32 곱 후 float64 손실·center·gradient.
- 직접α0 대조: `20261108T215307-941b3aaa`, 원래 품질 reference: `20261106T210640-0eb1bdc0`. 이전 위치 후보를 대조군으로 바꾸지 않았다.
- N+D+G+L2,α0,정상/결함bag1,L2=1,normal upperLSE tau0.1,출력max/sigmoid,threshold0.5,1776행/370결함1406정상/204사진group,5fold/seed20261031,zero-init,group-classmass,1000iterations/1250evaluations,최종gradient1e-5/내부1e-7 고정. 기존 center는 각 학습fold의 x/CLS/mass로만 계산; 새 정상분포 통계는 없음. 오류ID로 학습 선별·가중·라벨 수정0. 독립 시험셋 사용0.

## 동일 자료 결과와 사전 AND 기준

|대조/후보|AUC|FN/370(누락률)|FP/1406(오탐률)|
|---|---:|---:|---:|
|직접α0|0.931924955|57(15.4054%)|167(11.8777%)|
|패치×CLS|0.898043136|96(25.9459%)|177(12.5889%)|
|원래 품질 reference|0.916650648|67(18.1081%)|201(14.2959%)|

직접α0 대비 **AUC−0.033881819**, paired photo-group bootstrap95% **[-0.047067227,-0.021648807]**(2000회/seed20261107). **누락+39/+10.5405%p,오탐+10/+0.7112%p**. 신규누락50/회복11,신규오탐68/회복58. 정상–결함520220쌍의 역전35414→53040,새역전29079/회복11453. 전체ID는 analysis.json,행별점수는 comparison.csv.

원래 reference 대비 AUC−0.018607512,95%[-0.032396070,-0.004901354],FN+29/+7.8378%p,FP−24/−1.7070%p. 직접α0보다 FP가 증가했으며 원래 reference의 FP감소를 현재 개선으로 바꾸어 주장하지 않는다.

|고정 기준|실측|판정|
|---|---|---|
|직접α0 AUC차>0 및 paired하한>0|−0.033881819/−0.047067227|표현 개선 미달|
|FN≤67/370|96|미달|
|FP≤112/1406|177|미달|
|원래 reference AUC차≥0.03|−0.018607512|미달|
|원래 reference paired95%하한>0|−0.032396070|미달|
|5fold 수렴·분리·근거 유효|모두 통과|통과|

공통 result.acceptance_passed=false,worker criterion_met=false,representation_gate=false. 완료 상태는 실행 완료이며 채택을 뜻하지 않는다. 관찰 제한 누락·오탐은 미평가. 원래179/1597 보조라벨 평가는 evaluation.json에 별도 보존하며 확정정답370/1406과 혼합하지 않는다. 반복 모델선택 개발CV이며 독립 일반화 개선 미확인. 이 실패가 모든 문맥 표현의 실패나 과적합 원인을 입증하지는 않는다.

## 합성 검증과 실제 무결성

`tools/experiments/surface-patch-cls-interaction-20261110/checks.py` 통과(checks.log):

- 기존 추출기와 같은 crop448·physicalmask,동일rawpatch,한crop 한forward·같은forward CLS,정답/score/area불변을 합성 출력으로 확인. 실제 사진 추론은 합성검사에 사용하지 않았다.
- dense768D vs8bag청크: n=1/8/9/19,출력 최대차4.440892098500626e-16/gradient차4.263256414560601e-14. 출력1e-12/gradient1e-10 허용오차 통과.
- 전체 및5성분 loss/gradient,상호작용계수0에서384D 복원,원래float32 채점2e-6 이내,synthetic768D fit/성분감사,9×1024토큰 경계 smoke 통과. 초깃값·수렴예산과 손실 수식 변경0.
- AST 함수 수 features3/cls_linear2/objective3/worker0/checks1(각≤7). bag경로 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4전이; customautograd 내부추가projecthelper0; 추출 worker→backbone_features→view_tensors→prepared_image3전이,기존라이브러리백본경로 불변. 재귀0.
- bag-loss AST 및 loss/gradient 산술이 투영 입력 외 기존 위치 worker와 동일함을 확인했다.

실제 postflight.json 통과: 공통record snapshot/source SHA,동결입력242개,사진204장 SHA,같은1776행·정답·5fold 학습행/mass/target/mask가α0와 정확일치. 5fold group/photo overlap0,유한768계수+bias 모델5개,769차원 성분gradient·최종thetaSHA·성분합 일치,arithmetic term/gradient0. 실제 과거rawfeature hash는 보존되지 않아 과거raw배열과의 직접byte비교는 하지 않았으며 합성추출동치와 고정백본/전처리근거를 구분한다.

|fold|iterations|evaluations|최종gradient|
|---|---:|---:|---:|
|0|230|251|9.394719e-8|
|1|249|269|7.734906e-8|
|2|236|251|6.516579e-8|
|3|235|243|9.853288e-8|
|4|212|223|8.573999e-8|

공통실행기 반환 후 development-cycle/latest.json을 확인했다. 별도20261024 ai_calls_forbidden pointer는 그대로이며 이번run에는 development_handoff/next_steps/token_report가 없다. 과거pointer를 이번실험 근거로 바꾸지 않았다. 자동review·외부Gemini/Codex·추가학습/추론0.

## 768D 메모리

원본패치float32와 crop별CLS만 저장하며 청크에서float32곱 후float64 내적·custombackward를 계산한다. 원래center 정의도 학습bag별로768D를 임시확장해 계산한다. 전체768D training tensor/float64 clone은 생성하지 않았다.

|대상|크기|측정 구분|
|---|---:|---|
|전체768D float32|5.203125GiB|산술 크기,전체 미생성|
|전체768D float64|10.406250GiB|산술 크기,전체 미생성|
|raw384D float32|2.6015625GiB|저장 배열|
|crop CLS float32|2.6015625MiB|저장 배열|
|학습8bag 기본float64 청크|24MiB|raw 변환|
|학습8bag 곱float32/float64 청크|12/24MiB|추가 임시배열|
|채점8bag dense768D float32|24MiB|추가 임시배열|
|worker resident high-water|4957569024bytes=4.617095947GiB|resource.getrusage,worker만|

마지막 RSS표본은 metrics/bootstrap 완료 후 포함. 특징준비3883466752bytes(약3.62GiB),5fold 및metrics 이후4957569024bytes. 물리RAM16GiB. 이는 tensor합계·가상메모리·system전체peak·통제된실측절감률이 아니다. 메모리 압박이 없었다고 주장하지 않는다.

시스템 swap은 사전5022.12MiB→사후7822.94MiB(+2800.82MiB). 타프로세스 미통제·worker별swap 미측정이므로 worker에 귀속하지 않는다. memory-preflight.json/memory-audit.json/analysis.json/postflight.json에 범위·원값 보존. 사전 sysctl sandbox거절 후 읽기전용 권한으로 측정했고 학습 조건은 바꾸지 않았다.

## 변경·사진 HTML·위험·롤백

변경파일7개: 신규tools/experiments/surface-patch-cls-interaction-20261110/{features.py,cls_linear.py,objective.py,worker.py,checks.py}5개와 task/이결과MD. 핵심diff=같은forward CLS 추출·[x,x⊙CLS]768D·8bag custom투영/gradient·같은center/score·RSS단계측정. 기존 손실/optimizer/helper는복사후필요한입력부분만변경,원본소스/라벨/운영/fallback 불변. 사전snapshot7개는신규runtime만baseline=null,tracked5개는동결SHA와byte동치로연결. 새로운라이브러리/모델다운로드0.

사진별 HTML `artifacts/surface-patch-cls-interaction-20261110/report.html`:204사진/1776구역의사람정답·α0/후보저장점수·출력·FNFP·분모/%p/AUC/CI·메모리범위. HTML파싱/204img/1776overlay+정답+정확한저장점수/사진경로/CSV1776/외부script0 통과. macOS open은exit1,NSOSStatusErrorDomain−10661(kLSExecutableIncorrectFormat:No compatible executable was found)로실패,실제렌더미확인. 이전file콘텐츠관찰보안정책차단을존중하고다른browser/서버/터널로우회하지않았다. opening-status.txt에원문보존.

리스크: 반복개발평가의선택편향,CLS의촬영환경의존,추가차원의L2기하변화. 어느것도이번실패의확정원인으로단정하지않는다. 실패한단일조건을스케일/규제/threshold조정으로재실행하지않는다.

후보는신규격리경로이며운영에적용하지않아기존모델복구가필요없다. 구현을제거하려면실행종료/후속의존확인후`./develop -- git revert 03e722141fc8fd8fdf3d258d7577015b53bc2532`의일반revert를사용하고실험snapshot/결과는보존한다. 원격동기화는일반push후remoteSHA를확인한다. 다른worktree/.claude/와기존의도적보존checkout은변경하지않았다. 독립시험·실제HTML렌더·worker별swap 검증은미실행.

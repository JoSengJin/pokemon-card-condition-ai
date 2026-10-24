# T 미확인 보존과 국소 특징 대비 실험 — 2026-10-18

## 직접 결과

T=사용자 ‘사진으로 판단 어려움’. edge=null·기존surface1그대로·학습0·정상/손상변환0·재질문금지. T를관찰제한/평가불가정답으로자동변환하지도않음. 기존표면6점·영역·R/S라벨은그대로.

새라벨없이입력별평균특징을빼는가설을검증했지만기존최선대비악화해미채택.

| 같은26개개발평가 | 전 | 후 | 변화 |
|---|---:|---:|---:|
| 손상구간누락/4 |0|0|0%p|
| 정상오탐/22 |5(22.73%)|8(36.36%)|+13.64%p|
| 실제사람점누락/4 |0|1|+25%p|

새오탐index6/7/12·복구0. 실제B점새누락. 구간경고는남아도정확한손상점검출성과로보고하지않음. R/S미학습사후회귀는R검출/S오탐그대로. 독립일반화개선없음·운영미채택·Gemini절감0.

## 실험 가설과 범위

각crop의사진영역패치특징평균을빼사진전체에공통된featureoffset을제거하는가설. `z_i - mean(z_valid)`이며RGB밝기정규화라고주장하지않음. 같은56crop/33사람점/23정상crop·고정448최종DINO특징·동일fold/원본해시/그룹가중치·L2=1·기준.5 유지. padding은평균계산제외. 양성은실제사람점만, 미확인나머지양성픽셀은음성으로채우지않음. 모델추출기자체새학습은없고기존특징을정규화한뒤head만학습.

사진안평균만쓰고타사진·held정답통계는쓰지않음. 같은crop안패치차이는수학적으로유지되므로새미세디테일이생긴것이아님. 이번실패가공통촬영특징이모든오류원인이라는뜻은아니며,도움되는문맥도제거했을가능성을남김.

첫float32평균잔차검사가2.5034e-6으로허용2e-6을넘어학습전에중단. float64평균/빼기후float32변환으로계산정밀도를보완,잔차7.1526e-7로검사통과. 데이터를바꾸거나성능검사를우회하지않음. `numerical-check.json`참고.

## 변경 파일과 핵심 diff

독립 프로젝트 `.`:
- `artifacts/surface-edge-confusion-20261018/pikachu-T-review/{human-review-20261018.json,index.html}`: T의미확인답변·기존표면라벨보존·재요청문구제거. 원래proposal불변.
- `artifacts/edge-local-feature-contrast-20261018/{plan.json,run.py,result.json,features.pt,fold-*.pt,verification.json,verify.py,RS-post-label-regression.json,numerical-check.json}`: 입력별국소특징정규화연구후보/재추론/실패기록. 기존모델덮어쓰기0.
- `artifacts/local-contrast-review-20261018/{build_report.py,index.html,summary.json,verification.json,check_evidence.py,52개표시PNG}`: 모든26구간의사람정답/최고반응/실제점전후위치와오탐분모.
- 같은폴더 `new-meowth-review/{proposal.json,prepare.py,index.html,card-box.jpg,8개구역PNG}`: 기존eBay CLI확보사진중케이스없이끝선이보이는새나옹만검토후보선정. 앞뒤동일실물미확인·한장뒷면만다룸. 판매자NearMint는정답이아님. 제안box미승인,엣지8구역null·표면/모서리/센터링미추정,학습/추론0. 다음인간입력은새사진영역/실제끝선진실만.
- `LOCAL_CONTRAST_VALIDATION_20261018.md`: 이검증기록.
- 소비프로젝트 `CONDITION_ANALYSIS_TODO.md`: 체크포인트추가. 소비런타임미변경.

## 실행 검증

- 저장head3개를원본26개입력으로실제재추론,출력26/사람점4점수최대차0. R/S2개추가추론은사후회귀만(학습/독립시험아님).
- 전체56feature 정규화재계산일치·패치간차이보존·그룹/원본해시제외·train-only수렴·source SHA불변.
- 관련unittest27개통과(regression_audit,dino_wear_lora,local_wear_cnn,point_patch_head).
- T원제안SHA불변·surface1/edgeunknown보존·R/S사전예측SHA불변·원본183SHA `23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a` 유지.
- HTML모든로컬참조존재·모델성능페이지/새나옹제안페이지생성. 앱열기요청은queued. 이후CUA의file: 직접열기는브라우저정책으로차단돼중단했고HTTP우회/다른브라우저우회는시도하지않음. 파일링크와기존생성사진의네이티브표시로제공했으며실제E2E렌더통과를주장하지않음.

## 리스크와 롤백

같은개발평가반복·소수출처·실물독립미확인이남음. 이번후보미채택이므로운영롤백불필요. 기존고정448모델경로유지로기존동작그대로. 새연구artifact를소비하지않음. T와R/S확인기록은보존하며unknown을임의정상으로만들지않음. OpenCV·Gemini·API·소비런타임변경0.

## 다음 사람 개입

T/기존완료라벨재요청없음. 새나옹사진의제안영역이맞는지와8끝선정상/손상/미확인범위를한번에답변받는다. 이정상확인은엣지에만적용하고surface/corner0으로확대하지않음. 승인전학습/prepare없음. 사진상애매하면unknown유지.

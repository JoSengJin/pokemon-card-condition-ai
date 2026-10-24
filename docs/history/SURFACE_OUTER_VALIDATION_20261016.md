# 2026-10-16 · 표면 승인2구역 보강 및 특징 교체 검증

## 저장 확인과 적용
8793의 망나뇽 좌상단·우하단 표면 정상2승인과 원본SHA·box·검토자를 확인해 기존train레코드만 갱신. 이전 중앙·좌측중간 표면, 엣지, 결함점, 검증정답 보존. prepare.py가 val point rows 및 다른train라벨 불변 검산. 정상뒷면 표면11→13구역,실물6유지. OpenCV 사용0. 패키지소스·버전변경없음(0.4.99).

## 동일val38구역(손상19/정상19·4실물)
|seed|보강전 FN/FP|두 구역 보강후 FN/FP|ResNet18 FN/FP|
|---|---|---|---|
|42|8/3|8/3|6/15|
|7|1/12|1/12|16/10|
|19|5/13|6/13|14/5|

두 구역보강seed19 누락+5.26%p, 다른경우변화0%p. ResNet18은 같은최신자료MobileNet대비seed42 누락-10.53%p·오탐+63.16%p,seed7 누락+78.95%p·오탐-10.53%p,seed19 누락+42.11%p·오탐-42.11%p. 모두 연구채택기준미달. 오류를 이유로 사람정답을 되돌리지 않는다.

추가균등평균은 기존세seed점수에1/3씩 고정평균·임계값0.5. 직전배치누락5/19·오탐13/19,이번누락6/19·오탐13/19로개선없음. 가중치/임계값탐색안함. 모델간판정불일치26→25/38이나 불일치감소가정확도개선은아님. mean-probe.json에38구역전체점수보존. 이진판정평균과확률평균을혼동하지않는다.

## 실행·증거
prepare.py실행 통과,세seed실제학습,실제API MobileNet3×38구역차이0,ResNet3×38구역검산은각api-verification.json. 관련10회귀(surface_logistic,surface_tiles,point_final_evaluation,region_api)통과. 이전0.4.99의18관련회귀와wheel검산완료기록은SURFACE_BATCH_VALIDATION_20261015.md. HTML생성시정답·사진SHA·박스·분모·metrics검산,브라우저렌더시각QA미수행. file정책우회안함.

## 변경파일·영향·롤백
새 artifacts/outer-surface-approved-20261016/의prepare/run/verify/make_review/mean_probe스크립트·정답snapshot·모델·report·HTML,artifacts/surface-resnet-20261016/의연구스크립트·동일snapshot·모델·report·HTML,본보고서,소비CONDITION_ANALYSIS_TODO.md. 기존API·운영모델·Gemini경로변경0. 모델후보를사용하지않으면운영영향없음. 연구출력디렉토리를제거하면롤백되지만사람승인원본은보존한다.

## 남은조건
직전6구역보강은세seed누락1~2감소·오탐유지로연구개선했으나이번두구역과특징교체는추가개선없음. val4실물을반복탐색했으므로독립일반화미확인. 개발단계4/6약67%·실제Gemini절감0. 독립성능을입증하려면학습/선택에쓰지않은실물이필요하다. 사용자가추가사진없음을이미답했으므로완료라벨/기존사진을재요청하거나시험사진을학습에편입하지않는다. 다음데이터확보전동일가설반복학습은보류한다.

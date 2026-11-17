# 마모 주변범위·원본 클릭 허용 대조 · 2026-10-18

## 성과와 한계
- I/J 모두 엣지 마모라는 사용자 확인을 저장하고 정상 제안 철회. 아직 학습에 추가하지 않았음. 정상 라벨 새로 생성0, 완료G/H/I/J 재요청0.
- 동일26국소구간(손상4/정상22), 동일3fold실물분리·817파라미터·224입력·200step상한·학습loss기준선택·0.5기준. 공통3픽셀 마스크를 쓰는 대조군/후보에서 두 번째conv의 dilation1→2만 변경: RF5×5→7×7.
- 주변범위 대조 FN3/4→3/4(75% 유지), FP11/22→8/22(50%→36.36%, −13.64%p), 새오류0/정상복구3. 반복 개발 평가에서의 조건부 개선이며 독립 일반화나 실제 마모 위치 검출 개선은 아님. 기존2픽셀마스크 모델의 FN2/4와 비교하면 누락이 많아 운영 미채택.
- 별도 가설: 원본1픽셀 클릭오차를 입력배율에 맞게 ceil로 환산. B/D1, C/F3입력픽셀. 기존마스크2모델과 비교해 FN2→3/4(+25%p), FP11→9/22(−9.09%p), C새누락으로 미채택. 이 실험은 기존 마스크2·dilation1 설정에서 허용범위만 바꿨음. 주변범위 실험과 섞지 않음.

## 코드·핵심 diff
- card_condition/local_wear_cnn.py: dilation1/2 선택으로 해상도와817파라미터 유지. physical_pixel_mask의halo를 명시할 수 있게 해 비교군 동일유효영역 보장. sparse_wear_loss는 radius옵션으로 원본허용범위 실험 지원, native_click_radius는 Pillow 실제resize와원본crop크기로 환산. 기본값 dilation1/halo2/radius1은 기존 동작 유지.
- tests/test_local_wear_cnn.py: impulse로RF확장·파라미터동일/해상도유지 검증, 확대 후 원본1픽셀환산·확인범위밖unknown보존 검증 추가.
- artifacts/local-wear-context-d1-20261018 및 d2: 실행 전plan·실행원본·3fold체크포인트·원래26구간 점수. checkpoint의dilation/mask_halo를 읽어 같은구조로 재추론해야 함.
- artifacts/local-wear-native-click-20261018: 원본클릭허용범위·실제4점별radius·3개저장모델·결과/사진HTML. 원본plan supervision의radius1설명은변경요약/radii.json/실행코드 기준으로 보충하며 기존point 외에는 정상/결함정답을 만들지 않음.
- artifacts/wear-context-comparison-20261018: 동일분모 전후·사람점/모델최대값 사진·최고값동률진단·실행스크립트.
- artifacts/wear-feature-learning-20261017/abra-normal-review: 사용자I/J 정답과철회기록. 학습미사용 유지.
- 소비프로젝트 CONDITION_ANALYSIS_TODO.md는 결과 추적만 갱신. 운영/기존모델/Gemini변경0.

## 검증
각fold학습/평가실물·이미지SHA분리 assert, 평가26rows동일, 사람점/원본SHA불변. 저장재추론값차1e-6미만을각실험에서확인. 추가CPU 재추론으로context양성4개 점수차1e-5미만 확인. highest logit1e-6내동률픽셀을집계해빨간점하나를정확한위치로오해하지않도록표시. 좌표주변점수가최고값과같아도넓은평탄출력이면위치검출입증이아님.

## 리스크·롤백
양성4구간/3실물, 촬영/케이스/스캔분포차이, 반복개발평가선택편향이남음. 3픽셀마스크대조를2픽셀마스크모델과순수알고리즘효과로비교하지않는다. 운영모델은그대로이며연구실험을사용중단하면기존경로유지. 기존동작은 LocalWearCNN()·physical_pixel_mask(...,halo=2)·sparse_wear_loss(...,radius=1). 원본/완료라벨/결과보존.

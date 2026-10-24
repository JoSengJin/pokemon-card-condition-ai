# 정상 최대반응 손실 — 2026-10-19

## 성과 / 범위
같은 개발 평가26구간(손상4·정상22)에서 정상 오탐5→3/22(22.73→13.64%, −9.09%p), 구간 결함 누락0/4 유지, 실제 사람점 누락0/4 유지. 정답률80.77→88.46%(+7.69%p). 새 오류0, 복구 row4·24. 반복 개발 자료이며 독립 일반화·운영 품질은 미확인이다.

학습·검증 도구 구현 상태이며 전체 제품 완료율은 산정하지 않는다. 이번 단일 가설의 계획·학습·연구용 연결·원본 재현 검증4단계 완료. 운영 모델 채택은 하지 않았다.

## 원인 가설 / 대조
최대 패치로 경고하는 추론과 평균 정상 손실의 목표 차이를 대조했다. 57crop, frozen DINO448, 실제 사람점, split/group, 가중치, L2=1, threshold=.5 고정. 정상 손실만 softplus(0.1*logsumexp(valid_logits/0.1))로 바꿨다. 부드러운 최대값 상한이며 확률 교정 온도나 평가 기준 변경이 아니다. 동일 mean-odds 대조군3fold를 실제로 적합해도 FN0/FP5, 후보 FN0/FP3이다. 최신 logistic 기준과 비교해도 같은2정상 복구, 실제점 누락 추가없음.

과거 corner smoothmax 대조는 정상 geometry 승인 누락으로 품질 근거가 무효였다. 이번은 다른 엣지 pool의 감독/양음성 자료이며, corner 모델 학습이나 과거 정상 corner 복원은 하지 않았다. edge 구간 정답 범위의 한계가 일반화 검증을 대신하지 않는다.

## 변경 파일 / 핵심 diff
- card_condition/point_patch_head.py: normal_reduction='max_bound' 연구용 선택. 기본 mean_odds, 실제점 loss, 기존 반환 형식 유지. 후보 실패 시 다른 코드로 자동 fallback하지 않는다.
- tests/test_point_patch_head.py: 최대상한/여백제외/실제점 gradient/default유지/알수없는 옵션 거부 검사2개.
- artifacts/edge-normal-objective-20261019/: plan/run/candidate snapshot·6checkpoint·result·검증·사진 HTML·원본구간·표시 이미지. 실행된 plan/snapshot은 보존한다. 공용 source SHA는 후보 실행 전 값이며 이후 옵션 연결이력과 구분한다.
- 본 문서·소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 결과와 다음 의존 기록.

## 실제 검증
- 기존 저장26출력 재실행 차이0 후 가설 변경.
- 관련 unittest30개 통과(tests.log).
- 6fold fitting 수렴. 동일 group·원본 decoded SHA split 겹침0.
- 공유 fitter의 default와 새옵션 fold0 가중치/절편이 각각 고립 snapshot과 차이0.
- 원본 사진26forward·기준/대조/후보78출력·실제점12점수 차이0, photo mask26/26 일치(verification.json).
- 초기 검증에서 historical image_sha256을 파일 SHA로 잘못 해석해 중단했다. 실제26행은 모두 decoded 픽셀 SHA와 일치했다. 검증을 올바른 해시 계약으로 수정하고 원본 재현을 완료했다. 원본 라벨/해시는 수정하지 않았다.
- MPS는 sandbox에서 지원불가 오류가 나서 승인된 외부 실행으로 검증했다. xFormers 미설치 경고가 있었지만 연산·결과 일치검사를 통과했다.

## 남은 오류 / 다음 작업
오탐3곳 row9(ㅂ-new-back 좌중간),15(psa10-1 좌하단),25(꼬렛 좌중간). HTML의 빨강은 최고반응 패치이며 하자 정답이 아니다. row25 최고반응은 카드 바깥 배경 위에 보인다. 픽셀 여백 mask는 인공 패딩만 빼고 실제 사진 배경은 포함한다. source에서 승인된 카드 외곽을 활용하는 별도 입력/평가 가설이 필요하며, 미확인 geometry를 임의 승인하지 않는다.

새 후보는 같은26개를 반복한 연구 개선이므로 새 실물의 정상/마모 엣지를 함께 확인한 독립 자료로 재검증해야 한다. 이미 학습/모델선택한 사진을 독립 시험으로 돌리지 않는다. 정상 corner0으로 별도 모서리 head는 여전히 대기.

## 리스크 / 롤백
정상 최대상한은 정상 구간에 강한 gradient를 주므로 다른 자료의 실제 결함 누락을 악화시킬 수 있다. 이번4개 실제점 유지가 모든 마모 보존을 보장하지 않는다. 기본값·운영 모델·Gemini fallback·수집/OpenCV 변경없음. 롤백은 max_bound 인자를 사용하지 않으면 기존동작 유지. 옵션 자체를 제거하려면 위 point_patch_head의 normal_reduction 인자/분기/전달과 해당2테스트만 되돌린다. 기존 라벨·실험 기록·원본 사진은 삭제하지 않는다.

## 외곽 범위 후속 진단

geometry_diagnostic.py는 canonical에서 box_reviewed=true인 원본만 골라 condition label과 무관하게 카드 외곽 mask를 계산했다. 해당26행 중 승인 geometry가 있는 것은 꼬렛 정상2행뿐이며 손상 평가행에는 없다. 패치가 카드 bbox와 일부라도 겹치면 보존했다. row25의 배경 최고반응 패치는 제외됐지만 score .9610→.9494로 경고가 남아 전체FN0/FP3 동일, 추가 개선0%p. 전체 문맥이 특징에 섞이거나 카드 경계의 다른 패치가 반응할 가능성은 있으나 인과 확정은 아니다. 양성에서 geometry 효과를 검증하지 못했으므로 이 필터를 공용 API에 연결하거나 채택하지 않았다. geometry-plan.json/geometry-diagnostic.json 참조.

## 새 사진 체크포인트
기존 collection_only CLI로 새3매물19사진/Gemini0 확보. 액자/복수전시 사진은 제외하고 단일카드 front1/back6인 피카츄와 리자드 back6 적합성을 직접 확인했다(상태정답 아님). 피카츄의 새 짧은 엣지 U/V2곳을 선별하고 전체57학습과 매물group 및 실제decoded사진 중복없음 확인. 상태null/실제점null, 학습추가0. 동일3fold 평균 집계를 질문 전에 고정하고 모델6개SHA/plan SHA 검사, 새2forward 후 예측을 immutable predictions-before-human.json에 저장했다. 사람화면에는 점수를 숨겼다. 매물이 다르다는 것만으로 실물 독립성을 확정하지 않으며 이후 결과도 새 사진 보조평가로 표시한다. 사진 전체·모서리·표면 정상으로 확대하지 않는다.

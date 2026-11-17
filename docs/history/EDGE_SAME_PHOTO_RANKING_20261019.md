# U/V 정답 확인 및 같은 사진 비교손실 검증 — 2026-10-19

## 결과
사용자 ‘U 손상 V 정상’을 별도 human-observation.json에 저장했다. 답변 전 고정 예측 null/파일 SHA·6모델 SHA는 유지했다. 고정 기준과 최대반응 후보 모두 U 손상 검출1/1, V 정상 오탐1/1이다. 새 사진에서 추가 개선0%p이며 기존26개발구간 성과와 합산하지 않는다. 실제점 좌표가 없어 U의 정확한 위치 검출률은 계산할 수 없다.

다음 단일 가설은 기존57학습crop에서 같은 원본에 실제 사람점과 정상 끝선이 함께 있는 경우만 상대 비교하는 것이다. frozen DINO448/max_bound/L2=1/threshold=.5/입력/라벨 고정. 꼬렛의 사람점42 대 정상24·25와 기존 피카츄55 대 정상54를 각fold train에 있을 때만 사용했다. 각원본 group의 정규화 학습 mass를 짝에 균등분배하고 softplus(smoothmax(normal_logits)-actual_point_logit+1)을 추가했다. 양성의 다른 토큰에는 정답을 만들지 않았다. 기존 LoRA 비교손실 실패와 달리 이번은 최근 최대반응 정상 손실을 유지한 frozen linear convex head 대조다.

결과: 같은26구간 FN0/4→0/4, FP3/22→3/22(13.64%, 0%p), 실제점 누락0/4→0/4, 새 오류0/복구0. U/V 추가 진단도 U검출1/1·V오탐1/1 그대로다. 추가 향상이 없어 후보를 채택하지 않고 공용 API에 비교손실을 추가하지 않았다. 정상 V 점수 .8012→.8144로 낮아지지도 않았다. 합의나 구현 자체를 성과로 바꾸지 않는다.

## 변경 파일 / 핵심 diff
- artifacts/edge-normal-objective-20261019/new-photo-review/human-observation.json, confirmed-evaluation.json, index.html: U/V 사람정답·질문전 고정 예측 대조. 원시 predictions-before-human.json의 null은 불변.
- artifacts/edge-normal-objective-20261019/index.html: 새 사진 결과를 기존26개와 분리하여 연결.
- artifacts/edge-same-photo-ranking-20261019/: 사전plan·격리 candidate.py·train-only 짝·3fold checkpoint·result.json·UV 고정계획/원본 재추론/특징 캐시·검증·사진 전후 HTML·tests.log.
- artifacts/edge-normal-variety-intake-20261019/: 기존CLI collection_only로 새2매물6사진/Gemini0 확보. 이브이 단일front1/back2 및 온전한로고/네변을Codex확인(상태 정답 아님).
- 새 new-training-review/: 이브이 W엣지와 X모서리 원본1:1/정확crop context·정답null·train용 계획. 기존57학습과group/decoded사진겹침0. 새이브이는 추론/학습0.
- 본 문서 및 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 최신 결과/의존 기록.
공용 model 코드·운영·기본값·Gemini fallback·OpenCV는 변경하지 않았다.

## 검증
- 질문 전6모델 파일 SHA·예측파일 SHA 대조 성공. 원시 U/V 파일 null 유지.
- train fold별같은사진 짝3/1/3개, held group·사진해시 겹침0, optimizer3fold 수렴.
- 비교항 gradient는 양성 실제점에만 전달, unknown positive 토큰/normal padding gradient0 자체검사.
- 저장된3checkpoint를 기존26feature와4사람점에 재실행한 출력차0.
- U/V 원본2회 MPSforward로 질문전 최대반응 후보6fold출력재현 차이0. 새 후보2구간점수 저장. 원본26forward는 이전턴검증이고 이번에는26개 캐시로 체크포인트 출력재검사했다.
- 관련 regression_audit / point_patch_head / detail_data / detail_bag unittest30개 통과(tests.log).
- HTML local image/문서 링크 존재 검사.

## 해석 / 다음 사람 의존
U/V는 처음 답변을 받기 전 기존모델 비교를 고정했으므로 당시 새 사진 보조평가다. 이후 가설 설계에 결과를 참고했으므로 새 후보의 독립 최종시험으로 세지 않는다. 학습에는 넣지 않았고 val/test를 train으로 이동하지 않았다. 매물차이만으로 다른 실물임을 확정하지 않는다.

새 이브이 W(좌측중간 짧은 끝선)와 X(좌하단 둥근 모서리)의 상태만 확인하면 해당 학습 자료를 준비할 수 있다. 확인 전 정상0/손상1을 만들지 않는다. X가 정상이어도 카드 전체/엣지/표면 정상으로 확대하지 않는다. 정상 모서리 부족 학습은 사람의 해당종류 정상 확인이 있어야 진전할 수 있다. 완료U/V·과거판독불가구간은 다시 묻지 않는다.

## 리스크 / 롤백
이번 비교손실은 효과없음. 기존26개와 U/V는 개발에서 거듭 본 자료로 일반화근거가 아니다. source pair중 정상 구간이 부족한 상태에서 상대항만 더해도 새로운 시각근거가 생기지 않는다. 원인확정이 아니라 이번고정가설 실패다. 롤백은 격리후보 checkpoint를사용하지 않고 기존 최대반응 연구후보를 유지하면 된다. 원래사람정답·예측원본·운영파일은 되돌리거나 삭제하지 않는다.

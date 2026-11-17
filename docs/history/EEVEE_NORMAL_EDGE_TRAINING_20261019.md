# 이브이 정상 엣지 W 보강 — 2026-10-19

## 현재 상태 정정 — W 미확인·X/Y 모서리 손상으로 확정

최신 사용자 답변은 “w는 구분인 안되고 x는 손상이 맞아”다. 후속 직접답변 “w는 판단 어렵고 Y는 모서리 결함”으로 W 미확인·Y corner1을 확정했다. W 현재정답은 null/학습평가제외, X=corner1 유지, Y=corner1이다. 후보는 hold가 아니라 사용제외로 확정했으며 현재근거는 LABEL_CORRECTION_WY_20261019.md를 따른다. W보강 후보의 accepted 상태는 label-clarification-pending.json에서 false/hold로 표시했다. 아래 수치는 이전 W=edge0 답변을 조건으로 실행한 역사적 결과이며 현재 유효한 품질 개선 근거로 채택하지 않는다. 원래 답변/실행 계획/result/체크포인트는 그대로 보존했다. current-effective-detail-rows.jsonl은 W를 제외한 corner1 상세4행만 포함한다. 학습·운영 변경0.

## 성과와 단계
실험 계획·학습·재현 검증·사진보고4/4 완료. 전체 제품 완료율은 미산정, 연구·운영 품질을 섞지 않는다.

같은 개발26구간(손상4/정상22)에서 정상 오탐3→2/22(13.64→9.09%, −4.55%p), 결함 구간 누락0/4 유지, 사람 실제점 패치 누락0/4 유지. 정답률88.46→92.31%(+3.85%p). 새 오류0·row9(ㅂ-new-back 좌측중간) 정상1곳 복구. 기존26은 반복 개발 평가이며 독립 일반화 미확인.

학습 제외 U/V는 손상 검출1/1·정상 오탐1/1 그대로(0%p). 해당 정답/분모를 기존26개와 합산하지 않는다. U 실제점은 제공되지 않아 정확한 위치 검출 주장을 하지 않는다. 후보는 다음 연구에 사용할 수 있지만 운영 모델 교체는 하지 않았다.

## 정답과 변경 가설
직접답변 ‘w정상으로 보이고 x는 비정상’을 W=edge_defect0, X=corner_defect1로 국소만 저장했다. 둘 다 exact point 없음. W를 corner0으로 복사하지 않았고 X를 edge1/실제점으로 바꾸지 않았다. 전체back anchor/사진SHA/decoded SHA/매물group/split을 기존 detail_data로 검증했다.

기존57학습crop에 W 정상 엣지1개를 추가해58개로 대조했다. frozen DINO448, max_bound, L2=1, threshold=.5, group/class mass 정책과 held26은 유지했다. 새 그룹 때문에 class내 자료 구성·가중치 분포는 바뀌며 이것도 데이터 보강 효과에 포함된다. 각fold train에만 W를 추가, held그룹·사진과 겹침0. UV를 train으로 이동하지 않았다. 고정피쳐로 정상 지도자료를 보강한 것이며 백본 표현력을 새로 학습한 것이 아니다.

W 자체 학습반응.056~.074는 성공률/일반화 근거에 포함하지 않는다. 같은 사진 비교손실을 늘린 직전 실험은 추가개선0이었고, 이번 정상지도추가는 제한된 개발 평가에서1오탐을 복구했다. 이것으로 정상자료 부족이 모든 오류의 유일한 원인이라고 단정하지 않는다.

## 모서리 자료
이전 검증된 사람 실제점14 + 상세 모서리존재4 = 모서리 양성18/정상0이다. X는 별도 보존했고 정상 모서리가 없어 해당 head 학습은 시작하지 않았다. 아직 확인하지 않은 이브이 우측상단 Y 한곳을 원본1:1로 제시했다. 완료W/X·U/V·과거불명확구간은 재질문하지 않는다. Y는 상태null·추론/학습0, 정상으로 간주하지 않는다.

## 변경 파일 / 핵심 diff
- artifacts/eevee-normal-edge-training-20261019/prepare.py, human-observations.json, proposals.json, detail-rows.jsonl, detail-readiness.json, new-edge-row.json: 직접답변 종류별 보존·새국소5행(이전3+WX2) 검증. 기존 실행 결과는 덮어쓰지 않음.
- 같은 디렉토리 run.py, plan-before-features.json, patches.pt, fold-0/1/2.pt, result.json, training-use-event.json: train-only W normal 추가 및 고정3fold 비교. X는 이 엣지 학습 입력이 아님.
- verify.py, verification.json, tests.log, build_report.py, index.html, 26-after 이미지: 원본검증·사진위정답/반응·실제점 검증·같은분모 전후.
- corner-review/pending-proposal.json, Y 원본/context, index.html: 새로운 모서리 한곳 미확인 검토.
- 본 문서 및 소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 체크포인트와 다음 사람의존.
공용Python모델/기본값/운영PokeCollector/Gemini/OpenCV는 변경하지 않았다.

## 실행 검증
- detail_data는 새응답과 source/file SHA·decoded사진·fullback anchor·group/split을 확인했다. W=edge0만, X=corner1만. 기존70행canonical SHA 23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a 불변.
- 3fold 실제학습 수렴 및 원본26개와 W의 group/decoded사진 겹침0, UV group 학습편입0. 학습 전plan·tracked SHA불변.
- W 원본특징1회 추출 후 검증에서 원본29forward(기존26+UV2+W1)를 다시 수행. held52출력·실제점8점수·UV6fold·W학습반응3을 대조하여 모두 차이0. mask26/26 일치.
- 관련 unittest34개 통과: regression_audit, point_patch_head, detail_data, detail_bag, region_review(tests.log).
- HTML local사진·문서링크 존재검사. 브라우저렌더검증은 수행하지 않았으며 사진은 별도로 로컬 뷰어로 확인했다.

## 리스크 / 롤백
작은 반복개발평가이므로 연구 개선이 실물 전체나 신규사진으로 일반화됐다고 할 수 없다. UV의 정상오탐은 아직 남는다. 새W/이브이는 학습사용이력이 있어 이후 독립시험으로 다시 세지 않는다. 같은매물의 다른사진도 같은group으로 묶는다. 모서리 정상확인은 독립적인종류·구간정답이다.

롤백은 W보강 checkpoint 대신 기존 artifacts/edge-normal-objective-20261019/candidate-{0,1,2}.pt를 사용하면 된다. 공용기본/운영은 원래 유지되어 운영롤백은 필요없다. 사람W/X정답은 롤백대상이 아니며 삭제하거나 반대로 바꾸지 않는다.

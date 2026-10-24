# 마지막 검토 후보 반영과 신규 자료 필요

ebay-099acfa6824377/front/middle_right 엣지1 저장 확인. 앞면 면 엣지도1, 모서리/표면 구역은 null 유지, 좌표 지점은 추가되지 않았다. 원본은 수정하지 않았다. 다른36항목·분할·이미지·카드 영역과 기존 val50구역/8실물은 동일 단언 통과.

round15 snapshot은 train104→105구역. 고정 MobileNetV3 Small ImageNet 특징+head,seed42,224px,MPS,20epochs,threshold0.5로 기본·클래스 보정 두 모델을 학습했다. 같은 val 입력을 검산한 결과 round14와 혼동행렬이 모두 동일했다. 확률이 동일하다는 뜻은 아니다.

|종류|기본 FP/FN 전→후|보정 FP/FN 전→후|
|---|---|---|
|모서리|6/0→6/0|2/1→2/1|
|엣지|12/0→12/0|5/5→5/5|
|표면|19/0→19/0|11/9→11/9|

모델 교체·Gemini 생략은 보류. 실제 절감0건. 개발 검증 결과이며 최종시험이 아니다. 정상 뒷면 엣지 구역 실물0, 뒷면 정상 모서리1·표면1, 앞면 정상 모서리4·엣지4·표면5다.

## 다음 사람 자료

완료 카드를 제외한 현재 region-review-plan의 candidate_targets=0, selected=[] 확인. 이는 제한된 후보 정책과 완료 제외 조건에서0이라는 뜻이며, 전체 사진에 다른 가능한 관찰이 없다는 주장은 아니다. learn 미등록 폴더2개는 이미지0개로 새 학습 사진이 없었다. 완료한 자료를 반복 요청하지 않는다.

learn에 서로 다른 실물의 새 뒷면 사진 최대3장을 실물별 새 폴더로 추가하는 것이 다음 단계다. 정상 엣지 구역을 충분히 볼 수 있도록 테두리 초점과 조명/반사를 확인한다. 카드 전체가 정상일 필요는 없다. 다른 곳에 손상이 있어도 해당 구역을 충분히 관찰한 정상 정답은 가능하며, 보이지 않는 구역은 null 유지한다. 앞면은 이번 뒷면 구역 학습의 필수 조건이 아니고 같은 실물이면 함께 보존할 수 있다. 추가 후 기존 실물/사진 중복과 분할 이력을 확인하고 사람이 선택한 구역 정답만 반영한다.

## 산출물·검증·롤백

- artifacts/point-evidence-20261010-round15.jsonl, point-evidence-round15-receipt.json.
- artifacts/point-grid-augmented-20261010-round15-epochs20/, point-grid-balanced-20261010-round15-epochs20/.
- artifacts/point-grid-augmented-round15-comparison-20261010.json, point-grid-balanced-round15-comparison-20261010.json.
- artifacts/region-review-plan-20261010-round15-fresh.json.
- 마스터 CONDITION_ANALYSIS_TODO.md, 이 기록. 제품 코드·버전 변경 없음.

학습 로그 /private/tmp/condition-round15-train.log, /private/tmp/condition-round15-balanced.log. 실제 비교 검산 로그 /private/tmp/condition-round15-augmented-comparison.log, /private/tmp/condition-round15-balanced-comparison.log. 원본 SHA256 dd991f257e9ce39aff689e4e779860e110c3103c74901b7c330327e072a849be. 원본/검증 입력 불변 및 혼동행렬 재계산 통과. 코드 변경 없어 전체 테스트·패키지 빌드는 반복하지 않았다.

리스크: 결함 양성 추가만으로 정상 뒷면 자료 부족을 해결하지 못한다. 새 프레임워크나 같은 실험 반복이 개선을 보장하지 않는다. 최종시험·소비 앱 통합 미실행. 롤백은 이번 기록과 TODO를 되돌리는 것으로 충분하며, 기존 원본/모델은 덮어쓰지 않았다. 별도 실험 산출물은 보존한다.

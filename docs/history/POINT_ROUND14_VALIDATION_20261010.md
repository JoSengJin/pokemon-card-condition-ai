# 새 엣지 결함 학습·동일 검증 비교

사용자 저장에서 ebay-86a98a94850103 앞면 우측 상단은 엣지 결함1·좌표1개이며 모서리 구역 정답은 null이다. 사람 선택을 유지했다. 대상 앞면 면 엣지도1로 저장됐으며 뒷면·다른36항목·기존 분할·이미지·카드 영역은 그대로다. 원본은 수정하지 않았다.

round14 snapshot, 영수증, 기본/보정 모델, 검증 비교를 별도 artifacts 경로에 생성했다. train103→104구역, 기존 대상 외 입력과 val50구역/8실물의 이미지 해시·영역·정답 전부 동일 단언 통과. round12/13은 입력 불변이라 실제 직전 학습 round11과 비교했다.

|종류|기본 FP/FN 전→후|클래스 보정 FP/FN 전→후|
|---|---|---|
|모서리|6/0→6/0|2/1→2/1|
|엣지|12/0→12/0|6/4→5/5|
|표면|19/0→19/0|11/9→11/9|

고정 MobileNetV3 Small ImageNet 특징+head, seed42,224px,20epochs,MPS,threshold0.5. 선택 epoch 기본11/보정8. 보정 엣지 오탐1개 감소와 결함 누락1개 증가가 함께 나타나 채택 보류한다. 정상 뒷면 엣지 학습0실물 부족은 그대로다. 최종시험·운영 연동·Gemini 생략 미실행, 실제 절감0건.

## 파일과 검증 근거

- artifacts/point-evidence-20261010-round14.jsonl, point-evidence-round14-receipt.json: 사람 저장 변경·분할/검증 불변 동결.
- artifacts/point-grid-augmented-20261010-round14-epochs20/, point-grid-balanced-20261010-round14-epochs20/: 각각 실제 학습 모델·입력·보고서.
- artifacts/point-grid-round14-comparison-20261010.json, point-grid-balanced-round14-comparison-20261010.json: 동일 검증 입력 및 혼동행렬 재계산.
- artifacts/region-review-plan-20261010-round14-fresh.json: 완료 카드 제외, 현재 후보 ebay-099acfa6824377/front/middle_right/edge_defect 하나만 남음.
- 마스터 CONDITION_ANALYSIS_TODO.md, 이 기록. 제품 코드·패키지 버전 변경 없음.

실제 학습 로그 /private/tmp/condition-round14-train.log, /private/tmp/condition-round14-balanced.log. 비교 검산 성공 로그 /private/tmp/condition-round14-comparison.log, /private/tmp/condition-round14-balanced-comparison.log. 원본 SHA256 4172bf06850791147c2cb6aa731f0e58da93fe72ad5e37b5b86498187c4696f1. 코드 변경이 없어 전체 단위 테스트·빌드는 반복하지 않았다.

## 다음 진행·리스크·롤백

남은 후보1개 확인 뒤 완료 카드를 반복 요청하지 않는다. 부족한 정상 뒷면 엣지 자료는 서로 다른 새 실물의 선명한 뒷면 사진 최대3장과 사람 정답으로 확보한다. 정상 후보 선택은 정상 정답을 보장하지 않으며, 안 보이면 null 완료로 유지한다.

개발에 사용한 val 결과이며 최종 성능이 아니다. 사진 수·구역 수를 독립 실물 수로 해석하지 않는다. 기존 모델·원본을 덮어쓰지 않아 모델 롤백 불필요. 이번 문서/TODO만 되돌리면 진행 기록을 롤백할 수 있고 실험 산출물은 보존한다.

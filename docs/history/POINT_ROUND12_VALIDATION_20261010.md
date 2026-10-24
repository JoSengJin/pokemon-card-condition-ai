# 미확인 검토 완료 보존

사용자 저장 후 ebay-2c6e507b3fdc0d 뒷면 lower_center의 edge_defect는 null 그대로이며 region_reviews에 완료만 추가됐음을 확인했다. 다른36개 항목·대상 앞면·뒷면의 기존 라벨/영역은 불변이다. 정상0을 대신 채우지 않았다.

artifacts/point-evidence-20261010-round12.jsonl로 별도 동결하고 point_rows(grid=True) 결과를 round11과 전체 비교했다. train103/val50구역의 이미지 해시·영역·정답 모두 동일하다. 새 학습 신호가 없으므로 학습과 동일 모델 비교는 반복하지 않았다. 기존 모델과 판단 기준은 유지한다.

artifacts/point-evidence-round12-receipt.json에 변경 ID, 원본 SHA256, 입력 불변, 재학습 생략 근거 기록. 원본 SHA256 15af318404f83a6f3b68f8ea7281d6bdb23fc30523d31f402b3e8b0828964be6. 원본 수정 없음.

다음 후보 artifacts/region-review-plan-20261010-round12-fresh.json에는 완료한 기존 알파벳·ㄱ·ㄴ·최근 두 eBay 매물을 제외했다. 첫 후보 ebay-b128e5b4bbd4d9/front/upper_center/edge_defect 한 곳만 검토 요청한다. 후보는 정답이 아니며 미확인 완료도 허용한다. 정상 뒷면 엣지 학습0실물은 그대로이며 완료 카드 재요청 대신 새 선명한 뒷면 사진이 필요하다.

## 변경·검증·롤백

- tests/test_point_dataset.py: 기존 지역 증거 테스트에 region_reviews 미확인 완료 추가 전후 patch 동등성, 엣지 정답 null 유지 단언 추가.
- 마스터 CONDITION_ANALYSIS_TODO.md: 완료와 다음 사람 확인 갱신.
- 이 문서 및 별도 snapshot/영수증/계획 JSON. 제품 코드·패키지 버전 변경 없음.

위치 데이터 회귀6개 통과(/private/tmp/condition-round12-tests.log). 실제 원본/두 snapshot 입력 동등성 단언 통과. 변경이 테스트·실험 기록뿐이므로 새 패키지 빌드는 하지 않았다. 최종시험·운영 연동·Gemini 절감은 미실행이다.

리스크: 검토 완료는 상태 정상이나 학습 정답을 뜻하지 않는다. 현재 정상 자료 부족·오탐/누락 때문에 운영 성능을 주장할 수 없다. 롤백은 추가 테스트 단언과 이번 문서/TODO 변경만 되돌린다. 원본 라벨과 기존 모델을 복원할 필요는 없다.

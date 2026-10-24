# 검토 완료와 학습 정답 구분

ebay-b128e5b4bbd4d9/front/upper_center 엣지 null+region_reviews 완료 저장 확인. 저장 시 추가된 빈 visibility_issues/glare_areas/region_labels는 의미상 불변으로 검사했고, 다른 라벨·좌표·사진·분할과 다른36항목은 바뀌지 않았다. null을 정상0으로 변환하지 않았다.

round13 snapshot을 동결해 point_rows(grid=True) 전체 입력을 round12와 비교했다. train103/val50구역 입력과 정답이 전부 동일하여 재학습하지 않는다. 기존 round11 모델·판정 기준 유지, 운영 채택·Gemini 절감 없음.

산출물: artifacts/point-evidence-20261010-round13.jsonl, point-evidence-round13-receipt.json, region-review-plan-20261010-round13-fresh.json. 원본 SHA256 ff067cb05e595ad766b096e78dfbe9801d36f04fa179b636361400b0c14c197b. 이번 코드에서 원본은 수정하지 않음.

변경: card_condition/review.html의 완료 체크박스 안내에 정상·결함 선택과 완료의 차이를 명시. 저장/학습 동작 변경 없음. pyproject.toml0.4.20, 마스터 TODO, 이 문서. 새 사람이 확인할 대상은 ebay-86a98a94850103/front/upper_right 모서리1곳만이며, 나머지 후보는 지금 요청하지 않는다. 정상 뒷면 엣지0실물 부족은 남아 있다.

검증: 실제 원본 변경 검산과 train/val 전체 입력 동등성 assert 통과. JS 회귀와 wheel 빌드 결과는 /private/tmp/condition-round13-ui-tests.log, /private/tmp/condition-round13-wheel.log에 보존. 문구 변경으로 Python 전체 학습 테스트를 반복하지 않음. 미사용 최종시험·소비 앱 통합은 미실행.

리스크: 미확인 완료는 학습 신호를 추가하지 않는다. 정상 선택을 강요하지 않으며 사진으로 확인할 수 없는 손상을 정상으로 단정하지 않는다. 롤백은 안내 문구와 버전/문서/TODO만 되돌린다. 원본 라벨·기존 모델 복원 불필요.

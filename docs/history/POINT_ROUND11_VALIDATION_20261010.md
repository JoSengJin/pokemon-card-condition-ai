# 엣지 위치 저장 반영과 반복 검토 방지

사용자 저장 완료 후 ebay-50f5e8124d55bb 뒷면 우측 상단 엣지1과 사람 좌표1개를 확인했다. 기존 면 엣지0도 사용자 저장으로1이 됐다. 정상 사례로 채우지 않았다. 원본은 수정하지 않고 round10의 다른36항목과 대상 앞면을 보존한 round11 snapshot을 생성했다. val50구역/8실물 및 대상 외 입력 전체 동일 단언 통과. train 구역 수103은 그대로이며 기존 모서리 양성 구역에 엣지 양성 정답이 추가됐다.

## 같은 조건 학습 결과

고정 MobileNetV3 Small ImageNet 특징, head,224px,seed42,MPS,20epochs. 기본/클래스 보정 각1회, threshold0.5. 기존 round10 보고서와 동일 검증 입력을 검산했다.

|종류|기본 FP/FN 전→후|보정 FP/FN 전→후|
|---|---|---|
|모서리|6/0→6/0|2/1→2/1|
|엣지|12/0→12/0|5/5→6/4|
|표면|19/0→19/0|11/9→11/9|

보정 엣지 누락1개 감소와 정상 오탐1개 증가가 함께 발생했다. 운영 후보 채택이나 정확도 향상으로 해석하지 않는다. 실제 Gemini 절감0, 기존 운영 모델 변경 없음. test 미사용. 정상 뒷면 엣지 구역 학습 실물0은 그대로다.

## 파일·핵심 변경

- card_condition/region_review_plan.py: 선택적 skip_cards, 동일 실물 그룹도 후보에서 제외. 부족 자료 통계에는 기존 라벨을 유지. 출력에 제외 ID/그룹 기록.
- card_condition/cli.py: 반복 가능한 --skip-card. 기본 동작 유지.
- card_condition/review.html: 다음 미완료 결함 위치 탐색에서 같은 종류의 카드 영역 내부 사람 좌표를 완료 근거로 인정. 다른 종류·영역 밖 점은 완료로 보지 않음. 구역 정답 생성 없음.
- tests/test_region_review_plan.py: ID/동일 그룹 제외·자료 통계 불변 검증.
- tests/review_validation.test.cjs: 유효 좌표 완료·다른 종류 미완료·영역 밖 점 미완료 회귀.
- pyproject.toml0.4.19, README.md, 마스터 CONDITION_ANALYSIS_TODO.md, 이 문서.

산출물: artifacts/point-evidence-20261010-round11.jsonl, point-evidence-round11-receipt.json, point-grid-augmented-20261010-round11-epochs20/, point-grid-balanced-20261010-round11-epochs20/, point-grid-round11-comparison-20261010.json, point-grid-balanced-round11-comparison-20261010.json.

후보 계획 artifacts/region-review-plan-20261010-round11-fresh.json에는 기존 알파벳/ㄱ/ㄴ과 방금 완료한 매물을 제외한 목록을 저장했다. 다음 사람 확인은 첫 후보 ebay-2c6e507b3fdc0d/back/lower_center/edge_defect 한 곳만 요청한다. 다른 두 후보는 지금 작업 요구가 아니다. 계획 선택은 정상 정답을 의미하지 않는다.

## 검증·리스크·롤백

전체 Python57개 통과(/private/tmp/condition-round11-tests.log), JS UI 회귀 통과(/private/tmp/condition-round11-ui-tests.log), 0.4.19 wheel 빌드 성공(/private/tmp/condition-round11-wheel.log). 실제 학습 로그 /private/tmp/condition-round11-train.log, /private/tmp/condition-round11-balanced.log, 비교 로그 /private/tmp/condition-round11-comparison.log, /private/tmp/condition-round11-balanced-comparison.log.

원본 SHA256 e8ecace9070c94e73ab3d1bed3b6977831ef6fcd7078496967e817970e6a1982. 제외 옵션은 호출자가 완료 ID를 지정해야 하며 영구 전체 카드 차단 정책이 아니다. 새 구역 실물 다양성 부족·검증셋 개발 노출 때문에 최종 성능을 보장하지 않는다.

후속 검산: 원본 SHA256 불변, wheel 내부 cli.py/region_review_plan.py/review.html과 현재 소스 일치. 실행 중 서버는 매 요청 review.html을 읽으므로 재시작 없이 새 화면에 적용됐다. 브라우저의 뒷면 하단 중앙 확대·엣지 미확인 항목·검토 완료 체크박스 포커스 확인. 화면 증거 /private/tmp/condition-round11-next-human-edge.png.

롤백: skip_cards/CLI 옵션과 UI 좌표 완료 조건, 해당 테스트/버전/문서 변경만 되돌린다. 기존 원본 라벨·모델은 변경하지 않아 데이터 복원 불필요. 새 실험 산출물은 별도 경로로 보존하며 기본 모델로 배포하지 않는다.

# 평가 실물/학습 이력 계약 일치 — 0.4.72

개발 기반4/6=67% 유지. 새 카드 진단에서 동일 픽셀의 다른 인코딩 사진을 서로 다른 실물로 집계하던 오류, 관찰 모델 독립 평가가 공백 ID·잘못된 hash를 허용하던 오류를 수정했다. 모델 정확도 상승 실험은 아니다.

## 변경 파일·핵심 diff
- card_condition/point_probe.py: 선택 카드에 기존 reject_copied_test_groups 적용. 동일 실물의 여러 사진은 허용하며 다른 실물명으로 복제 픽셀을 세는 경우만 거부한다.
- card_condition/observation_heldout.py: 수동 이력 검사 대신 기존 development_sets 재사용. 잘못된 이력은 추론 전에 거부한다.
- tests/test_point_probe.py, tests/test_observation_heldout.py: 인코딩이 다른 동일 픽셀 거부·동일 실물 허용·이력17종 회귀.
- pyproject.toml·README.md·소비 프로젝트 CONDITION_ANALYSIS_TODO.md: 버전과 실행 근거. 소비 운영 코드 변경 없음.

## 검증
artifacts/evaluation-group-contract-20261011/reproduce.py 실행: 실제 합성 추론에서 이전 복제 입력은2실물2구역 성공, 수정 후 거부. 기존 관찰 평가의 비정상 이력5종은 이전 성공→수정 후 보고서 미저장. 깨끗한 동일 입력 관찰 보고서는 전후 정확 동일. 실제 선택 관찰 체크포인트의 이력 호환/SHA 불변 확인.

전체148테스트48.381초·저장소 밖 설치본19테스트3.665초 통과. wheel52개Python/HTML파일 소스 일치. checks.json에 원본/live/두 모델 SHA 보존 기록.

정확도 새 측정 없음·운영 절감0건. 기존 정답/개발 분할/모델/임계값을 바꾸지 않았다. 합성 재현은 독립 일반화 성능 근거가 아니다.

## 리스크·롤백
서로 다른 실물이라고 기록했어도 사진 픽셀이 같으면 이제 진단을 거부한다. 자동으로 실물명을 합치거나 정답을 수정하지 않는다. 사용자 판단으로 실물 그룹의 실제 의미를 확인해야 한다. 공백/형식 오류의 과거 수동 모델은 거부된다. 정상 저장 모델은 유지된다.

.backups/probe-groups-0472/의 point_probe.py·observation_heldout.py는card_condition/, test_파일은tests/, pyproject.toml·README.md는루트로 복원하면0.4.71로 복귀한다. 진단 artifacts와 문서는 별도 보관 가능. 실제 모델/라벨 롤백 불필요.

에튜: 파일 SHA는 인코딩이 달라도 달라지지만 decoded-pixel SHA는 같은 그림이면 같다. 그래서 ‘다른 파일’과 ‘다른 실물 표본’을 구별해야 검증 실물 수를 부풀리지 않는다.

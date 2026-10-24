# DINOv2 별도 관찰 제한 실험 비교 계획

사전 고정: 0.4.42, DINOv2 ViT-S/14 CLS384, 공식 코드 revision7764ea0f912e53c92e82eb78a2a1631e92725fc8. 기존 MobileNet 기본값 유지. 종합 관찰 제한 타깃, train46면/25실물, val24면/14실물, 사람 확인 box, 224px 동일. 클래스/실물 가중 centroid와 /D 거리식 유지. 추가 정규화·온도·멀티태스크·SPP·검증 임계값 선택 금지. 비교 source=artifacts/observation-geometry-20261011-source.jsonl, reference=artifacts/observation-geometry-20261011/report.json. test 미사용.

연구 후보 진입 조건: AUROC와AP 모두 reference보다 개선, 균등BCE<ln2, FP<=7 및 FN<=4이며 적어도 한 오류 수 감소. 비교기 일반 research_candidate_only보다 보수적인 이번 조건을 우선한다. 통과해도 운영 승인/독립 성능 입증이 아니다. 미달은 이 설정에서 가설 미지원이며 조언 전체가 틀렸다는 의미가 아니다.

복귀: 기존 source·report·model.pt, OBSERVATION_CONSENSUS_20261011.md는 불변 보존한다. 실험 옵션을 선택하지 않으면 기존 MobileNet 경로다. 미달 시 마스터 TODO의 현재 실행 순서를 OBSERVATION_CONSENSUS의 종류별 입력 근거 진단으로 돌린다. 완료 라벨 재요청·반복 학습·없는 원본/비교 사진 재요청 금지. 운영 fallback 유지.

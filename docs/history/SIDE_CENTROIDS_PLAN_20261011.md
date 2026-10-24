# 앞뒤 대표 기준 분리 — 사전 계획0.4.46

표준화 후보의 오탐7개가 전부 back, 누락4개가 전부 front였다. 가설: 서로 다른 앞뒤 무늬가 섞인 단일 대표 특징 대신 면별 train 대표 특징을 사용하면 관찰 제한을 더 잘 구별한다. 상관관계 진단이며 앞뒤 혼합이 원인이라는 확정 아님.

단일 변경: 같은576차원 frozen MobileNet/context/224px/box/사람 정답에서 centroid만 front/back 각각 fit. 각 면 안에서 기존 클래스→실물 균등 train 가중치 사용, 거리 /576·판정0.5 유지. local-signals/standardize/tiles/interior/DINO 혼합 금지. train 각 면에 제한/비제한이 모두 있어야 하며 부족하면 출력 전에 거절한다. val로 대표값/임계값 선택하지 않는다. 추론 시 면을 명시하지 않으면 추측하지 않고 오류/fallback을 요청한다.

고정 source observation-geometry-20261011-source.jsonl, train46/25실물·val24/14실물. train front20clear/5limited·back12clear/9limited, val front9clear/4limited·back8clear/3limited. test 사용 금지, 완료 라벨 재요청 없음.

비교 기준 geometry 모델: AUROC/AP 둘 다 증가, BCE<ln2, FP<=7/FN<=4 중 하나 감소해야 연구 채택. 앞뒤별 FP/FN·순위·실물 수 및 전체를 따로 공개하며 면별 기준 분리에 따른 서로 다른 score 척도 가능성에 주의한다. 검증 재사용이며 독립 일반화/운영 승인 아님. 미달이면 보류.

# 엣지 마지막 특징 블록 적응 실험 · 2026-10-17

## 결론
현재 outer-strip 입력과 평균 pooling을 그대로 두고 MobileNet 마지막 inverted residual block만 실제 학습했다. 고정 특징 대조군과 같은 183구역/45실물 그룹 3-fold 개발 비교에서 FN33→34/84, FP38→37/99. 정확도112/183=61.20%로 동일하지만 누락이 증가해 미채택. 새누락3, 새오탐2, 복구5. 독립 정확도 개선 미확인, 운영 교체0, Gemini호출0. 기반 진척4/6 유지.

## 비교 계약
- 사람 승인 train manifest gengar-normal-edge-20261017/combined-reviewed.jsonl만 사용. 기존 frozen test2사진과 새 수집 사진은 미사용.
- group SHA 정렬 후 3-fold round robin. 앞뒤별 분류기. 같은 실물 그룹과 동일 decoded image hash가 train/held에 겹치지 않는 assert.
- 두 모델 모두 RGB224 / 전체구역+외곽띠 / 공간평균+띠평균 / 동일 실물-클래스 가중치 / 수렴 logistic L2=1 / threshold0.5.
- baseline classifier를 고정한 채 마지막 공간 block을 AdamW lr0.0001, weight_decay0.01, 10step 학습한 뒤 같은 logistic을 재적합. 검증 epoch 선택이나 threshold 탐색 없음.
- 6fold 모두 학습 loss 감소. held front FN10→11/12, FP18→15/33; back FN23→23/72, FP20→22/66. 학습 loss 감소가 카드 간 일반화를 보장하지 않는 사례. 모든 fine-tuning 방식이 무효라는 결론은 아님.
- 기존 과거 DINOv2 실험은 관찰 제한/CLS/centroid였으므로 이번 엣지 실험과 동일시하지 않음.

## 변경 파일 / 검증
- artifacts/edge-last-block-adaptation-20261017/run.py: 고정 계획·cached prefix·마지막 블록 적응·그룹 분리 비교·사진 HTML 생성.
- 같은 디렉토리 export_verify.py, fold-*-api.pt: 독립 RegionAnalyzer용 연구 export, 183구역 API 재추론 최대차2.3841858e-7.
- plan.json, result.json, decision.json, api-verification.json, index.html: 실험 근거. cache feature와 기존 입력함수 최대차1.9073486e-6.
- source hash와 plan hash 불변 assert. 마지막 출력 layer와 BatchNorm running stats 불변, 마지막 공간 block 실제 parameter 변화 확인.
- PYTHONPATH=.:tests .venv/bin/python -m unittest test_edge_views test_point_spatial test_regression_audit: 11 tests OK.
- 기존 운영/library 소스 변경 없음. 새 구현은 재현 가능한 연구 스크립트에 한정.

## 새 eBay 자료 선별 / 사람 입력
- 기존 collect_ebay_dataset.py collection-only 실행: 첫 검색1매물2사진은 선택형 제목으로 후보 제외. 추가검색5매물25사진 확보. Gemini0.
- Codex 원본 시각 검사로 ebay-pair-1aac7e5cf19355 스라크 뒷면 선택. 로고와 네 변 보임. 우측 약1/3 끝선 흰 마모 A, 좌측 중간 매끈한 끝선 B 비교 후보.
- candidate/proposals.json은 AI 출처의 제안만 저장. human_truth_assigned=false, used_for_training=false. A는 손상으로 보이는 AI 관찰, B는 가는 밝은 경계가 있어 사람에게 정상/마모/판독불가 확인 요청. 답변 전 학습편입0.
- 나머지 매물은 비교 정상 구역이 약하거나 슬리브/반사/촬영 각도 등으로 이번 소량 검토에서 보류. 매물 제목은 상태 정답으로 쓰지 않음.

## 리스크 / 롤백
작은 기존 개발 자료를 반복 사용한 탐색 결과라 독립 성능으로 해석하지 않는다. 3fold 구성은 과거 leave-one-out 결과와 분모가 비슷해도 직접 비교하지 않는다. 미세조정은 과적합 가능하며 이 후보는 미채택. 신규 연구 artifact만 사용을 중단하면 복귀되며 기존 라벨·기준모델은 변경되지 않았다. 새 수집 원본은 보존하고 잘못된 후보는 proposals만 제외한다.

다음: 사람 답변으로 새 스라크의 비교 가능 범위를 확정한 후, 출처가 분리된 검토 자료를 준비한다. 완료 라벨 재요청하지 않는다.

후속: 스라크B는 사용자 확인 엣지 마모로 정상제안 철회. 이후 피죤투C/D도 모두손상. 추가대안과 검토 API 결과는 EDGE_HYBRID_REVIEW_VALIDATION_20261017.md 참조.

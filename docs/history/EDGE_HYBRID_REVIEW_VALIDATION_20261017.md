# 특징 추출 대안 및 선택형 추가 검토 · 2026-10-17

같은183구역/45그룹 3fold 개발 평가. MobileNet 고정 FN33/84 FP38/99, 마지막 block 학습34/37, 같은사진 pairwise35/36, DINO patch mean29/48, patch max28/46, MobileNet+DINO concat26/45. 결합 후보 recall은60.71→69.05%(+8.33pp), 정상 오탐률38.38→45.45%(+7.07pp). 전체 정확도61.20% 동일. 새 누락3·새오탐13·복구16이라 자동 교체 안 함.

기존판정 OR 결합후보는 연구용 검토신호다. 기존의심은 지우지 않고 신규23구역을 추가: 실제손상10·정상13. 검토 미포착손상33→23/84. 결함 정답이나 자동 구매 제외로 사용하지 않음. 현재 운영연결0. 4/6 진척은 독립시험/운영 수용기준 미달로 유지.

## 구현 및 실행
- card_condition/edge_hybrid_review.py: HybridEdgeReview(checkpoint, pinned_local_dino_repository, device). analyze(image, card_box, area, side)로 baseline_score/candidate_score/additional_review/flagged_for_review 반환. production_ready=false, human_review_required=true. 앞뒤checkpoint 선택 불일치 거부. DINO pinned local source만 사용해 예측 중 다운로드/외부AI 호출 없음.
- tests/test_edge_hybrid_review.py: 기존양성보존·새후보검토만표시·0.5경계·비유한값거부.
- artifacts/edge-last-block-adaptation-20261017: 원본고정 특징과 마지막block10step 비교. 입력/평균pooling/정규화계수/분할 유지.
- artifacts/edge-pairwise-adaptation-20261017: 같은사진 양성음성5이미지에서만 softplus(negative-positive), image당평균, 고정가중치0.5. held그룹정보로 쌍 생성 금지. ranking gradient 방향 assert. held 같은사진 순위정확도 image평균62.14→60.48%로 미채택. source/proposals의 C/D 모두 손상 정정.
- artifacts/edge-dino-local-20261017: 공식 cached revision7764ea0… patch tokens(256,384) mean/max descriptor. 과거 관찰제한 CLS 실험과 별개. 차원/스케일 변화도 포함돼 백본만의 인과로 단정하지 않음.
- artifacts/edge-dino-fusion-20261017: concat1920 feature, 동일train-only 수렴 L2=1 head. source rows 완전일치 검증. 앞뒤 full-train 연구checkpoint 및 export_verify.py. held 모델선택 자료를 독립test라고 주장하지 않음.
- artifacts/edge-hybrid-review-20261017: 종합표·모든 추가검토23구역의 원본 위 빨간박스·사람정답·전후점수.

검증: PYTHONPATH=.:tests .venv/bin/python -m unittest test_edge_hybrid_review test_edge_views test_point_spatial test_regression_audit →14 tests OK. HybridEdgeReview 저장후 앞45/뒤138 실제사진 재추론 모두 score차0. 다른면모델사용거부. full-train 재현성 점검이며 heldout 성능검증과 구분. 미세조정6fold API183구역 최대차2.39e-7. source와plan SHA 보존, 그룹·동일이미지train/held 중복없음, 마지막block 외 파라미터/BN통계불변.

## 수집 및 사람 정답
기존 collector collection-only 네실행 합계14매물52사진 확보. 첫 선택형제목 후보 제외, 25사진·16사진·9사진 직접검사. Gemini호출0. 스라크B는 마모, 새피죤투C/D 모두 마모로 사용자정정 보존. 정상으로 학습하지 않았고 정상제안 철회. 아직 같은사진의 신규 정상/손상 쌍 확정0. 기존승인5사진으로 알고리즘비교 진행. eBay사진은 실물 독립성을 보증하지 않음.

## 리스크 / 롤백
추가검토 오경보13구역과 더 큰 DINO모델의 메모리/추론비용. 여러후보를 같은개발분할로 비교해 선택편향 가능; 성과는 연구수치. 독립 성능/실제사용속도/배포효과 미검증. 기존 API/consumer/default모델 변경0. 새 HybridEdgeReview 호출을 중단하면 기존경로로 복귀. 신규 module/test 제거 또는 보존만 하면 되며 기존 라벨·사진·모델 복원은 필요 없음.

후속 사람 확인 대기: 추가 수집 라이츄 ebay-pair-9744bf49d0c025의 F 짧은 상단 끝선만 확인 요청. 국소crop 확인을 전체3x3정상으로 확대하지 않는다. proposals는 학습 미사용. README에 선택형 연구 API 사용법 추가.

F 확인 완료: 사용자 답변을 근거로 해당 국소crop만 edge_defect=1 확인 기록. 제조 과정 발생 가능성은 사용자 의견으로 별도 보존하고 cause=unknown. 기존 normal 제안0은 감사 이력으로 남기되 rejected 표시. 정상 학습편입0, 원인별 학습0, 좌표·E 제안 보존. 후보 데이터·HTML만 갱신, 새 모델 추론/정확도 변화 없음. 롤백은 candidate/proposals-before-F-confirmation.json에 이전 제안 기록이 있으나 사용자 정답은 별도 보존해야 함.

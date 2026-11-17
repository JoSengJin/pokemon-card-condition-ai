# 실제 결함점 패치 입력 대조 · 2026-10-18

## 진척·성과
연구 경로 구현/개발 대조 완료, 독립 일반화 미확인, 운영 미적용. 가중된 완료율 정의가 없어 전체67% 대신 단계로 보고한다.
같은26구간(손상4·정상22, 손상 실물3장)의3fold 실물/사진분리 대조. 원본 사진·라벨·group/class질량·정규화L2=1·임계값.5 불변. 기본224→선택448 입력만 변경.
- 구간누락0/4→0/4, 변화0%p.
- 정상오탐9/22(40.91%)→5/22(22.73%), −18.18%p.
- 실제 사람점 패치 누락1/4(25%)→0/4, −25%p. B의 실제 점 복구.
- 구간정답률17/26(65.38%)→21/26(80.77%), +15.38%p. 전체AI정확도아님.
- 새오류0, 정상복구 row index[5, 6, 12, 17]. 운영자동교체없음.
- 별도 정상 손실 대조: 평균패치BCE 대신softplus(logmeanexp(logit))로 높은 오탐에 집중. 동일224에서 FN0/FP9·사람점FN1로 변화0. 448과동시에바꾸지않음.

## M/N 사람 정답
직접답변“M 손상 N 정상”을별도human-review파일에저장. 입력·추론전예측파일의null은불변. 두사전고정모델 모두TP1/TN1/FN0/FP0로추가개선0. 한사진두짧은구간, 전체면/테두리정상으로확대하지않음. M/N은새손실/448학습에미사용. 실물독립성은매물사진만으로확정하지않음. 이답변은다시요청하지않음.

## 변경 파일·핵심 diff
- card_condition/point_patch_head.py: 연구전용점/사진패치bag손실과train-only수렴head. 양성사람점이외unknown, 정상crop질량패치수에무관, 높은정상오탐강조, 운영연결없음.
- card_condition/dino_wear_lora.py: point_token_index에선택image_size224/448,32grid좌표변환. 기본224/16grid동작유지.
- card_condition/local_wear_cnn.py: physical_pixel_mask만선택image_size지원. 원래CNN·기본224/halo2불변.
- tests/test_point_patch_head.py: unknown양성gradient0,정상high-tail집중/패딩무시,패치반복질량불변,수렴/export/정답검증5테스트.
- tests/test_dino_wear_lora.py: Pillow실제렌더링흰점이224/448의해당토큰에들어가는지와사진마스크일치검사추가.
- artifacts/local-wear-dino-point-bag-20261018:손실한가설계획·실행원본·학습수렴·결과·3fold모델.
- artifacts/local-wear-dino-point-448-20261018:입력한가설계획·실행원본·모든패치특징·결과·3fold모델.
- artifacts/point-grid-improvement-20261018:단계/분모별전후HTML·원본입력·사람점/최대패치표시·고정후보·재추론증거.
- artifacts/wear-pooling-audit-20261018/new-pikachu-review:human-review·confirmed-evaluation·확인완료HTML. M/N이전계획/예측은수정없음.
- DINO_POOLING_VALIDATION_20261018.md 및기존HTML생성기:완료상태정정. 소비CONDITION_ANALYSIS_TODO.md:추적결과만갱신, 운영PokeCollector동작변경0.

## 실행 검증
관련33테스트통과. 테스트의Pillow렌더픽셀읽기정정후좌표/LoRA5테스트재통과.
- 32개원래사람점이448실사진패치에남음, 매fold실물그룹/decoded사진SHA학습·평가교집합0, 같은26rows/정답불변, 학습수렴 및계획/소스SHA불변 assert.
- 원본사진52회forward, 저장경로3개 출력78개검증 최대차0; 사람점점수12개 최대차1.1920929e-07.
- canonical183행manifest SHA23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a불변.
- 448후보3fold체크포인트/입력/임계값/고정평균정책은다음새사진선별전frozen-candidate.json으로고정. 기록된검증결과가운영속도측정을뜻하지않음.

## 리스크·롤백
반복개발자료와양성4구간/3실물의소수표본이다. 새로운실물일반화/전체카드위치검출은미확인. 입력448은원본에없는정보를복원하지않으며추론비용을늘릴수있다. 오탐5개남음. 고정후보의새사진정상/손상검증전운영교체하지않는다.
기존호출은기본224로그대로동작한다. image_size=448을쓰지않고새연구체크포인트를사용하지않으면기존경로유지. point_patch_head는연구실행/테스트에서만사용된다. 이전연구/완료라벨/원본사진/고정예측을삭제하거나변경하지않는다.


## 다음 사람 확인 체크포인트
모델고정후eBay CLI collection_only로3매물7사진(Gemini0). 앞선파이리2매물은케이스/하단반사로미선택. 추가캥카(e1effcdf6d59a6)raw뒷면은한카드/로고/네변/모서리가완전히보여선별. O하단흰끝선·P우측파란끝선의입력과224/448예측은답변전에SHA고정. 두구간정답null·metricsnull·학습0. decoded사진hash는54학습사진/MN사진과겹치지않음,이전catalog/proposals에서같은ID검색중복없음. 실물독립성확정아님. 점수는정답화면에서숨기며사람답변범위만후속평가. M/N재확인없음.


## O/P 완료 및후속
O심한엣지1, P엣지1+오염확정. 두고정모델모두누락0/2·정상0으로오탐률정의불가. M/N사후448회귀도TP1/TN1·새오류0. 추가448QKV LoRA는같은26구간FN0/FP5·사람점FN0유지로추가성과없어미채택. OP_FINE_GRID_VALIDATION_20261018.md와새성과HTML참고. 완료M/N/O/P재요청금지. 다음Q는같은사진상단의미확인짧은끝선하나이며새독립사진으로세지않음.

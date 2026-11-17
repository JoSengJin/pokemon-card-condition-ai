# 기존 결함점 활용·특징 학습·기울기 감사 · 2026-10-18

## 결론과 성과
최근 국소CNN은 새로운4점/3실물에 집중했고, 기존 라벨 중 같은4방향·뒷면·영역확인이 명시된28점/11실물을 활용하지 않았다. 이 자료를 train-only로 추가하되 평가26구간과 정답은 고정했다. 평가와 동일 실물·동일 decoded사진SHA의 추가점은 해당fold의 학습에서 제외했다.

같은 DINO 고정특징·patch-max·수렴logisticL2=1·기준0.5에서 기존4점→기존28점 추가: FN4/4→1/4(100%→25%, −75%p), FP6/22→9/22(27.27%→40.91%, +13.64%p). 자료 활용 효과는 확인했으나 오탐 증가와 작은 반복 개발 평가 때문에 운영 채택하지 않았다. ‘고정 특징 추출기만이 문제’라는 단일 원인 설명은 부족하다.

같은28점 자료로 DINO 마지막QKV rank4 실제 특징학습(6144파라미터,10step고정,사람점토큰 보조loss0.5): FN1/FP9 유지. 정상오탐1/복구1 교체로 새오류가 남았다. QKV 실제 변경·loss감소는 검증됐지만 특징학습의 추가 성능 이득은 미입증이다.

## CNN의 구체적 실패
기존28점을 추가한817파라미터 CNN 및 LeakyReLU 후보는 평가26구간 전부를 손상으로 출력(FN0/4·FP22/22)했다. 정상 모두 오답이므로 누락0을 성과로 보지 않는다. fold0의 학습 양성31개에서 은닉특징 전체0, 첫conv기울기0, head bias기울기만 유효함을 실제 체크포인트로 확인했다. LeakyReLU는 동일31개에서 첫층기울기0을31→0개로 줄였으나 최종 판정은 개선되지 않았다. 최적화 문제를 보완해도 표현·입력·학습분포 문제가 함께 남는다.

regression_audit는 기존 aggregate_improved(수치 집계) 계약을 보존하고 both_classes_evaluated/constant_prediction/informative_improvement를 추가했다. 양성/음성 미평가나 상수출력은 전체 분류품질 개선 근거로 사용할 수 없다. 이 플래그는 운영 자동교체 기능이 아니다.

## 새 사진 첫 추론과 다음 사람 입력
I/J/K/L은 사용자 확인 엣지 마모4구간/2사진. 어떤 현재모델 학습에도 넣지 않았다. 3fold 확률평균/0.5기준을 추론 전에 고정했고 고정DINO/LoRA 모두4/4 손상으로 출력했다. 정상0이라 오탐을 평가할 수 없고, 매물사진만으로 실제실물 독립성은 확인 불가다. 따라서 독립 정확도100%라고 주장하지 않는다. G/H는 이전 별도연구에서 학습했으므로 신규시험에 재사용하지 않았다.

K/L을 제외한 같은 잉어킹의 다른6짧은 끝선은 아직 미확인이다. 사람에게 모델점수를 숨기고 정상으로 충분히 판단한 번호만 받는다. 미응답은 미확인 유지. 모델/사진/제안SHA·평균방식·기준을 먼저고정하고6예측을 저장했다. 이는 이미본2사진 평가코호트의확장이며 새로운독립카드평가가아니다. 완료G/H/I/J/K/L을다시묻지않는다.

## 변경 파일·핵심 diff
- card_condition/local_wear_cnn.py: dilation/leaky 연구옵션·유효사진 halo·원본클릭허용범위. 기본 dilation1/leakyFalse/halo2/radius1은 기존출력 유지. 단순 모델이 실제 특징을 학습하지 못하는지 검사하기 위한 선택형 연구경로다.
- card_condition/regression_audit.py: 상수출력/양쪽클래스지원 경고. 기존counts/aggregate/no_new_errors는보존.
- tests/test_local_wear_cnn.py: 해상도/817파라미터동일·RF확장·원본허용환산·unknown보존·음수특징기울기 검증.
- tests/test_regression_audit.py: 전부양성인모델의겉보기수치개선과양성만평가한경우를전체품질개선과구분하는검증.
- artifacts/local-wear-existing-points-20261018: 사람점28개/11실물 출처·새행·원본실행·CNN체크포인트·기울기감사.
- artifacts/local-wear-existing-points-leaky-20261018: 동일자료 활성함수만변경·기울기복구와성능실패분리.
- artifacts/local-wear-existing-points-dino-20261018: 같은자료 고정DINO 대조·분류기수렴·fold별train/heldIDs.
- artifacts/local-wear-existing-points-lora-20261018: 실제QKV특징학습·병합·통계·저장모델.
- artifacts/wear-unused-region-probe-20261018: I/J/K/L추론전계획·사진·4구간첫점수. 정상라벨0.
- artifacts/wear-existing-point-review-20261018: 같은26구간 전후사진·모든새오류·상수모델실패·검증·블라인드6구간확인화면.
- artifacts/wear-feature-learning-20261017/abra-normal-review/proposals.json 및 artifacts/wear-context-comparison-20261018/normal-review/proposals.json: I/J/K/L사용자정답1·정상초안철회·정확점추정0·학습미사용. 변경전사본보존.
- 소비프로젝트 CONDITION_ANALYSIS_TODO.md: 결과추적만갱신. PokeCollector운영코드·Gemini fallback·운영모델변경0.

## 실행 검증
`PYTHONPATH=.:tests .venv/bin/python -m unittest test_dino_wear_lora test_local_wear_cnn test_edge_hybrid_review test_edge_views test_regression_audit`:27테스트통과.

저장된고정DINO/LoRA를실제원본사진26구간씩총52회다시추론해최대차4.76837158e-07. 세fold모두QKV weight만실제변경되고그외DINO마지막블록가중치는불변확인. 보정전고정대조군점수재현·보정/병합출력일치·분류기수렴assert통과. 학습중추적파일SHA불변·새점pool과원본26rows분리·기존183manifestSHA불변.

이검증은기술재현성이며추가독립성능으로중복계수하지않는다. xFormers미설치경고는기본PyTorch경로로실행완료했고새패키지는설치하지않았다.

## 리스크와 롤백
양성평가4구간/3실물이라한곳변화가25%p다. 기존개발자료반복·촬영/케이스/스캔분포차이·새사진실물독립성미확인. 같은사진정상/손상자료는현재학습pool에서기존꼬렛1사진뿐이라배경단서학습을배제할수없다. 공장/사용중손상원인은단정하지않는다.

운영모델은미교체라운영롤백필요없다. 연구옵션사용을멈추고 LocalWearCNN() / halo2 / radius1을쓰면기존기본경로다. DINO새연구체크포인트를사용하지않으면기존동작유지. 원본사진·완료라벨·실험결과와변경전사본은삭제하지않는다. 진척률은학습도구구현/품질미통과/독립일반화미확인/운영전상태로보고하며전체67%를재사용하지않는다.


## 새6구간 후속 답변 보존
사용자: “6번 우측하단은 하자가 맞는거 같은데 나머진 공정하자인거 같기도해”. 6번손상의심/1~5번제조흔적가능성을별도human-review JSON에저장했다. 정상확정0·새학습정답0. 원인가능성만으로정상/손상확정을만들지않고, 기존K/L정답1은보존한다. 추론전에고정한proposals/예측파일은수정하지않았다. 흔적이손상이라는판단은확실하고원인만모르는지, 손상여부자체도불확실한지확인이필요하다. 사진전체/완료K/L재확인은요청하지않는다.


## 1~5번 제조 원인 확인 후 정정
사용자 추가 답변 “제조 때 생겼는지 모르겠다는거야”에 따라1~5번은 실제 엣지손상1로 확정하고 원인만unknown으로 저장했다. 6번은 의심null 유지. 추론 전 proposal/예측 원본은 불변이며 별도human-review sidecar와confirmed-evaluation에만 반영했다. 고정DINO/LoRA는확정5구간 모두검토출력(5/5), 정상0이라오탐률은정의불가. 같은기존2사진의추가구간이지새독립실물5장이아니다. 학습편입0·K/L기존정답보존·완료라벨재요청0. 위 ‘확인이 필요’ 기록은 이 답변으로 해소됐다.

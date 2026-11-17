# O/P 복합 손상 확인과448 특징학습 후속 · 2026-10-18

## 성과·진척
사람 복합라벨 반영·고정예측 대조·연구후속 검증 완료. 전체백분율 정의가없어 단계로표시하며 운영미적용·독립일반화미확인.
- 사용자답변 “P오염 O는 하자 심각”, 추가답변 “끝선 손상도 있고 오염도 있어”를근거로O=edge1/심함, P=edge1+오염/surface1로저장. 원인은unknown, 범위는선택된짧은구간. O/P재요청금지.
- O/P 답변전고정예측224/448모두TP2/FN0. 정상0으로FP율계산불가. 추가정답향상0. 엣지경고가P의오염탐지성공이라는뜻은아님. P정상제안은Codex초안으로철회, 실제모델은처음부터경고했다.
- M/N 알려진정답1/0을재요청·학습없이448후보회귀점검:TP1/TN1·새오류0. N점수.4360→.2105는판정향상아님. 이새후보검사는정답을이미아는사후회귀점검이며블라인드/독립테스트로주장하지않음.
- 새로운단일가설:기존448입력/54학습crop/32사람점/동일26평가구간을유지하고마지막QKV rank4 LoRA만학습. 고정10step/lr.001/weight_decay.01/기준.5, train-only수렴L2=1 head재적합, 평가자료로epoch/threshold탐색없음. M/N/O/P전부학습미사용.
- 같은26개발구간 FN0→0/4·FP5→5/22, 새오류0·사람점누락0→0/4. 추가정확도성과0%p로LoRA채택안함. 이전224→448개선(FP9→5/22·사람점FN1→0/4)은유지하며이번추가학습성과와혼동하지않음.

## 변경파일·핵심diff
운영Python/API/모델소스변경0. 연구실행원본·라벨·사진HTML·검증문서만갱신.
- artifacts/point-grid-improvement-20261018/new-kangaskhan-review/human-review-20261018.json, confirmed-evaluation.json, confirm.py,index.html:O/P다중라벨·원인미확인·범위보존, 답변전plan/prediction원본은수정없음.
- artifacts/point-grid-improvement-20261018/mn-regression/run.py,plan.json,result.json:M/N정답사후448회귀,추가학습0.
- artifacts/local-wear-dino-point-448-lora-20261018/run.py,plan.json,prefix448.pt,result.json,fold-0/1/2.pt:실제마지막QKV특징학습, 기존head대조·정규화/질량고정·수렴·병합출력검사·실제QKV만변경assert.
- artifacts/op-confirmed-fine-grid-20261018/build_report.py,index.html,summary.json,verify.py,verification.json:O/P/MN증거와동일26구간의추가학습전후사진.
- artifacts/op-confirmed-fine-grid-20261018/q-review:같은캥카상단Q한구간 입력/기존224·448예측을답변전에고정. 정답null·metricnull·학습0. 같은기존사진의추가구간으로새독립사진/실물로세지않음. O/P다시묻지않음.
- POINT_GRID_VALIDATION_20261018.md,기존성과HTML생성기,소비CONDITION_ANALYSIS_TODO.md:완료상태와최신근거연결.

## 실행검증
이번turn 관련13테스트통과(test_dino_wear_lora, test_regression_audit). 추가학습/라벨스크립트자체assert도실행.
- 실제원본사진26구간의저장LoRA추론 최대차0.0, 실제사람점4점수 최대차0.0. 3fold모두 attn.qkv.weight만실제변경,그외마지막블록가중치불변. 이전블록은freeze/cache하고실제로학습하지않음.
- 매fold학습/평가실물및decoded사진hash교집합0. M/N/O/P학습추가0. 답변전frozen plan/predictions SHA불변.
- canonical183행SHA23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a불변. 고정448후보체크포인트불변.

## 리스크·롤백
양성/음성소수와반복개발평가로일반화미확인. 448기존후보를새사진전에고정했지만실물독립성은매물만으로확정불가. P정답을같은사진모든끝선으로확대하면안됨. 추가LoRA는운영/기존연구모델을덮어쓰지않았으므로사용하지않으면롤백완료. 완료사람라벨/원본/고정예측을삭제/되돌리지않음. 기본224/운영fallback/Gemini호출은변경없음.

# DINO 입력·집계·점 지도 대조 · 2026-10-18

## 성과와 수용 판단
같은 개발26구간(손상4/정상22), 동일3fold 실물·사진SHA 제외, 기준0.5. 기존28점 추가 고정DINO는 FN1/FP9. 아래 실험들은 서로 다른 가설이며 모두 독립 일반화나 운영 성능이 아니다. 하이퍼파라미터/기준점을 평가 자료로 탐색하지 않았으나 반복 사용 선택 편향은 남는다.
- local-wear-dino-padding-20261018: 직접 대조 FN1→1/4, FP9→10/22. 새누락[], 새오탐[7, 15].
- local-wear-dino-photo-mean-20261018: 직접 대조 FN1→1/4, FP10→9/22. 새누락[], 새오탐[11].
- local-wear-dino-pca4-20261018: 직접 대조 FN1→2/4, FP9→8/22. 새누락[3], 새오탐[15, 19].
- local-wear-existing-normal-balance-20261018: 직접 대조 FN1→2/4, FP9→7/22. 새누락[3], 새오탐[].
- local-wear-dino-point-head-20261018: 직접 대조 FN1→0/4, FP10→9/22. 새누락[], 새오탐[12].
- local-wear-dino-point-lora-20261018: 직접 대조 FN0→0/4, FP9→9/22. 새누락[], 새오탐[].

점 패치 분류기는 원래 고정DINO 전체최댓값 기준 FN1→0/4(−25%p)·FP9/22유지지만 새오탐2개로 자동채택 보류. 실제 사람점 패치 기준3/4만 기준을 넘고 B는.3619(LoRA.3671)로 여전히 누락이다. 구간경고4/4와 정확한 위치검출3/4를 구분한다. 같은점목표QKV LoRA는 실제가중치변경됐지만 추가성과0.

## 사용자 정답 보존
잉어킹1~5 실제엣지손상1·제조원인unknown,6번의심null. 기존고정모델은확정5구간5/5경고. 정상0으로오탐률정의불가. 같은기존사진에추가한구간이지새독립실물이아님. 이구간과I/J/K/L은이번학습미사용. proposals·추론전예측파일불변, sidecar에만확인정답기록.

## 원인 진단
- 여백토큰이54×384특징차원중9428개 최댓값을차지했으나제외해도개선실패. 부분사진패치는유지했고실제32사람점토큰모두남음. 여백이오답의유일원인이라고단정하지않음.
- 평균집계추가성과없음. 특징크기단일진단은FN1/FP3, 픽셀없는폭/높이진단은FN3/FP11. 질감방향을뺀대조가더잘맞는단서가있지만지름길학습확정은아님.
- 학습전용weightedPCA4는누락증가. 분산유지와미세손상분리는다름.
- 기존승인망나뇽4방향·팬텀하단중앙5정상입력을재활용했지만F새누락발생. 평가실물/사진은학습에서제외했고새정답추정없음.
- 점패치분류기: 채널마다서로다른위치를섞는max descriptor 대신하나의공유head를각패치에적용. 양성은사람점토큰만, 정상은명시적edge0구간의사진패치이며구간질량을패치수로나누어유지. 양성다른패치는unknown, 음성질량을패치수로부풀리지않음. 마지막QKV실제학습도같은목표를사용해기존crop/point표현분포혼합을피했지만품질추가성과없음.

## 변경 파일·핵심 diff
운영 Python/API는변경하지않음. 연구코드와체크포인트/진단을독립artifacts에추가.
- artifacts/local-wear-dino-padding-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-dino-photo-mean-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-dino-pca4-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-existing-normal-balance-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-dino-point-head-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-dino-point-lora-20261018/run.py, plan.json, result.json, fold별체크포인트: 계획선고정·단일가설대조·group/photo제외·학습적합수렴검사.
- artifacts/local-wear-dino-photo-mean-20261018/norm-diagnostic.py 및geometry-diagnostic.py:단서제거음성대조.
- artifacts/wear-pooling-audit-20261018/build_report.py,index.html,summary.json,verify.py,verification.json:전후전체26구간/원본위치/사람점패치/모델패치/모든새오류표시.
- artifacts/wear-existing-point-review-20261018/remaining-edge-review/human-review-20261018.json 및confirmed-evaluation.json:손상과제조원인분리저장.
- EXISTING_POINT_WEAR_VALIDATION_20261018.md,기존성과HTML생성기2개,소비프로젝트CONDITION_ANALYSIS_TODO.md:확인해소·결과연결.

## 검증
관련Python27테스트통과. 부분사진패치마스크기하자체assert·32사람점유지·각대조군재현·동일rows·실물/사진분리·학습분류기수렴·plan/sourceSHA불변검사. verify.py는실제원본사진에서기본/LoRA각26번총52fullforward,7경로출력182개와사람점8점수를검증한다. 결과수치는verification.json. 3fold모두실제QKV weight변경,기타블록가중치불변. canonical183SHA불변.

## 리스크·롤백
양성4국소구간/3실물의작은반복평가라1곳이25%p. 특징의촬영·배경단서/과적합을배제할수없다. 구간검토신호를실제결함위치또는구매제외로사용하면안된다. 패치14px내정밀위치미확인. 정상라벨은사람의기존구역확인범위만사용했다. 새독립실물정상/손상자료로품질확정필요. 연구체크포인트를사용하지않으면기존모델유지되므로운영롤백불필요. 원본/완료라벨/추론전계획삭제금지.


## 다음 사람 확인 체크포인트
CLI collection_only로2매물12사진 확보·Gemini0. f2e95ff0f362ec의받침대에가린뒷면은제외, a9f2617e297c5f photo6는한카드/로고/네변온전함을Codex선별. M왼쪽흰흔적·N우측파란끝선의두입력과이전/점패치모델3fold평균예측을사람답변전에SHA고정했다. decoded사진SHA는54학습사진과겹치지않음. 매물사진만으로실물독립성확정불가. 정답null·성능지표null·학습추가0. 사람확인전표시화면에는예측점수를숨겨판단유도를줄였다. 완료라벨재요청없음.

HTML3개 로컬참조164개및사람정답/새오류assert검증통과. 운영모델미교체.


## M/N 사람 확인 완료
직접답변 “M 손상 N 정상”을sidecar에만기록. 계획/추론전예측JSON의null은불변. 사전고정두모델모두M손상/N정상으로TP1/TN1/FN0/FP0,추가개선0. 한사진두짧은구간이며실물독립성미확정. M/N학습미편입·판단범위확대없음·완료라벨재요청금지. 새후보를이정답에맞춰선택하지않음.

# 엣지·표면·배경 분리와 정상 학습 진단 — 2026-10-18

## 수용기준과 결과

1. Q 사용자 답변을 그대로 기록: 안쪽 인쇄면 미세 화이트닝=surface1, 바깥 끝선=판단 어려움/null. 엣지 오탐/표면 탐지 성공으로 계산하지 않으며 재확인하지 않음. 기존 사전 계획/예측 SHA 보존.
2. 같은26개 개발 구간(손상4/정상22), 같은 실물그룹/원본사진 해시 제외 유지. 새 사진/독립 성능으로 부풀리지 않음.
3. 지점 검출과 구간 경고를 분리. 실제 사람점4개에서 모델 출력을 직접 확인.
4. 후보 저장 후 원본 재추론·전후 사진 HTML 제공. 운영 모델·API·Gemini·OpenCV 변경0.

| 실험 | 손상 구간 누락/4 | 정상 오탐/22 | 실제 사람점 누락/4 |
|---|---:|---:|---:|
| 기존 고정448 |0|5|0|
| 카드 내부 패치만 집계 |0|5|0|
| 추정 끝선 패치만 집계 |0|5|0|
| 배경 회색으로만 변경, 고정448 |0|9|1|
| 원본/회색 쌍 학습, 원본 입력 |0|5|0|
| 원본/회색 쌍 학습, 회색 입력 |0|7|1|
| 학습 안 강한 정상16패치3회 강조 |0|5|0|
| 확인된 N 정상1구간 추가 |0|6|0|

원본 추가 개선 없음. N 후보 오탐+4.55%p(새오탐 index7), 미채택. 회색 변형에서만9→7(-9.09%p)이며 실제 원본 성능과 합산하지 않음. 배경 변경으로 입력분포·합성경계가 바뀌므로 모든 오류가 배경 때문이라고 단정하지 않음.

## 가설·설계·학습 근거

- `edge-support-diagnostic-20261018`: 동일 RGB/특징/분류기에서 출력 집계 위치만 제한. Q 점수 .718921→.391153. Q 세 head의 최고패치는 카드 안쪽/추정 끝선 밖이지만 외곽 정답null이므로 FP복구0건으로도 계산하지 않고 미정으로 둠.
- `core-edge-support-20261018`: 기존26구간에서는 집계 제한으로 판정 변화0; 사람점4개 모두 경계 마스크에 남음.
- `card-background-neutralization-20261018`: 카드 대략사각형+원본2pixel halo 내부 모든RGB/사람점4pixel 보존, 외부만128회색. 사진 최고경고는 남지만 B 실제점 누락 발생. 대략사각형은 Codex가 잡은 진단용이며 사람 영역승인으로 전파하지 않음.
- `background-pair-training-20261018`: 기존54crop 중 학습에 속한 원래26row만 원본/회색 쌍으로 학습. 한 crop 가중치1/2씩 분배. held 그룹과 원본 해시를 먼저 제외; 학습 밖 변형으로 마이닝하지 않음. 나머지28기존 사람점은원본만.
- `wear-hard-negative-20261018`: 기존54crop 그대로. 정상 crop 가중치 절반은 전체 유효패치, 절반은 학습 안 상위16패치. 기존L2=1·448·임계값.5·고정3refit. 실제 사람점32개는그대로, 나머지 양성crop 픽셀을 음성/양성으로 채우지 않음. 학습 정상구간 오반응 fold0 3/14→0/14, fold1 2/20→2/20, fold2 2/10→0/10이나 held26은동일. 학습오류 개선을 일반화로 보고하지 않음.
- `confirmed-normal-n-training-20261018`: 위실험과합치지않고 기준54crop+사람확정N0 한crop만추가. N의 정상범위는 짧은선택구간만. N학습 후 같은사진 M/N을 독립시험으로 재사용하지 않음. 실제실물독립은판매사진만으로확정되지않으며원본해시/출처그룹분리만주장. M양성crop은정답좌표가없으므로중앙/모델최고패치를사람점으로지어내지않고미학습.

## 변경 파일과 핵심 diff

독립 프로젝트 `.`:
- 위6개 실험 폴더의 `plan.json`, `run.py`, `result.json`, 필요한 `.pt`/마스크/변형입력/검증 JSON: 연구 전용 새 artifact. 기존 모델파일 덮어쓰기0.
- `artifacts/op-confirmed-fine-grid-20261018/q-review/{human-review-20261018.json,outer-edge-review-20261018.json,confirmed-observation.json,confirm.py,index.html}`: Q 확인사실/불확실성 기록. 원래 사전 계획/예측 유지.
- `artifacts/op-confirmed-fine-grid-20261018/{build_report.py,index.html}`: Q를 다시묻는문구를확인종료로정정.
- `artifacts/wear-pooling-audit-20261018/new-pikachu-review/training-use-20261018.json`: 과거 블라인드/확인기록을고치지않고후속N학습사용이벤트추가.
- `artifacts/edge-context-audit-20261018/{build_report.py,index.html,summary.json,52개입력표시PNG}`: 카드/배경/실제점/최고반응 대조.
- `artifacts/wear-normal-learning-20261018/{build_report.py,index.html,summary.json,52개입력표시PNG}`: 두후속후보전후사진. `m-point-review/{serve.py,index.html,labels-review.jsonl}`은 기존ReviewServer에연결한M실제점1개입력UI. 다른라벨/카드영역은재요청0.
- `EDGE_CONTEXT_VALIDATION_20261018.md`: 이검증기록.
- 소비프로젝트 `CONDITION_ANALYSIS_TODO.md`: 최신체크포인트1개추가. 소비런타임미변경.

## 실행 검증

- 배경쌍 모델3개 실제사진52forward/52출력·사람점8점수, 저장결과와최대차0.
- 강조/N 모델 각각26출력, 공통26원본forward 재사용·사람점각4개, 최대차0.
- `test_regression_audit.py`, `test_dino_wear_lora.py`, `test_local_wear_cnn.py`, `test_point_patch_head.py` unittest27개 통과. pytest미설치로첫시도실행불가; unittest로전환. 설치변경없음.
- 원본183라벨 SHA `23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a` 및사전계획/원본입력SHA불변.
- HTML 파일/로컬이미지참조존재검사. 표시PNG 실제시각확인(B 회색에서 실제점과최고반응분리). 앱열기요청은queued; 브라우저완전E2E렌더검증주장없음.

- M 입력 UI 실제 HTTP page/API/image 200, 한 row·기존 M 손상1·빈 좌표 확인, Node JS 구문 검사 통과. 사람 저장을 흉내 내거나 가짜 좌표를 기록하지 않음. `artifacts/wear-normal-learning-20261018/verification.json` 참고.

## 리스크와 롤백

소수개발사진반복·사각형수작업근사·특징공간문맥/무늬혼동·새실물독립미확인·최대집계다중반응이남음. 회색사진을새독립표본으로세지않음. surface1은edge0가아니며normal은선택구간바깥으로확대하지않음. 새후보미채택이므로런타임롤백불필요. 연구후보를읽지않고기존고정448 artifact를쓰면원래비교가유지됨. HTML정정은generator수정으로재생성; 사람확인 sidecar/사용이벤트를삭제해과거시험으로되돌리지않음.

## 다음 사람 입력 의존

M 실제 흰마모대표점1개. 결함여부(M1/N0)는완료이며재질문하지않음. 기존8799 UI에좌표만저장하면같은사진의국소정상/손상특징대조를구성할수있음. Q는판단어려움으로확인종료,재요청없음.

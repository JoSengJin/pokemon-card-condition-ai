# 표면·엣지 혼동 확인과 입력/특징 가설 대조 — 2026-10-18

## 사용자 정답과 성과

- R: ‘엣지 손상 있음’ → edge1, surface미확인.
- S: ‘끝선은 괜찮아 보이는데 안쪽 파란색 테두리에 화이트닝 있네’ → 이짧은선택구간edge0·surface1. 원인/심각도/다른구역은추정하지않음.
- 답변전계획·가중치SHA·예측은불변. 기존448/MN고정특징/MN비교특징모두R검출1/1·S오탐1/1(TP1/FP1). 처음본한사진의두구간이며실물독립미확인,2장으로계산하지않음.
- R/S는유형혼동감사자료로유지하고학습에편입하지않음. 이후새후보추론은정답을안뒤사후회귀로구분. 완료R/S·MN·Q확인재요청0.

| 동일26개개발평가 | 구간손상누락/4 | 정상오탐/22 | 실제사람점누락/4 |
|---|---:|---:|---:|
| 기준MN 고정12층 |0|5|0|
| 중간8층만특징추출 |0|7|2|
| 기존정상/표면결함구역넓은학습뷰 |0|5|0|

8층은오탐+9.09%p·새오탐3(index12/14/16)·복구1(index4), 사람실제점B/D누락이새로생김. 구간은계속경고해도실제손상위치를놓친것이므로채택금지. 넓은뷰는추가성과0%p. R/S사후회귀둘다FN0/1·FP1/1유지. 운영미채택·Gemini절감0.

## 원인 재점검과 근거

`edge-midblock-features-20261018/semantic-coverage.json`은기존56학습crop/23정상을원래사람라벨과대조한감사다. 같은거친구역에edge0/surface1이함께기록된뒷면은ㅂ-새뒷면1개뿐이다. 이것이국소좁은입력에실제표면흔적이포함됐다는뜻은아니다. 해당출처를제외한fold2에는그런구역을가진학습출처가0개다. 대부분정상crop의표면상태는미확인이며surface0으로채우지않음.

S는안쪽화이트닝인데실제넓힌ㅂ입력에는검은점이보인다. 둘다surface1이라는이유로동일시각특징의대조자료가확보됐다고볼수없다. 이런자료공백이모든오탐의유일원인이라고단정하지않음.

## 하나씩 바꾼 두 실험

1. `edge-midblock-features-20261018`: 입력448·384차원·동일56crop/33사람점·같은학습/평가fold·그룹/클래스가중치·L2=1·기준.5 유지. DINO12층대신8층정규화출력만사용. 실제backbone자체새학습은없으며featuredepth만변경. 가설은‘후반의문맥표현이종류혼동을키우는가’이며결과는악화,채택안함.
2. `edge-wide-semantic-negative-20261018`: 원래ㅂ-새뒷면middle_left구역의사람edge0/surface1을사용. train으로이미지정된출처에만기존좁은입력+원래3×3구역전체입력을학습. 한sourcecrop질량을1/2씩분배해자료복제만으로출처가중치가증가하지않도록함. 출처그룹/원본해시가held이면추가뷰도제외. 실제fold2에추가안됨을확인했고해당row9점수차0. 역사적box에box_reviewed체크가없으므로새승인box로추정하지않고연구입력진단에한정,prepare/export우회없음. R/S학습0.

## 변경 파일·핵심 diff

독립프로젝트 `.`:
- `artifacts/mn-point-feature-review-20261018/new-vulpix-review/{human-review-20261018.json,confirmed-evaluation.json,post-label-regression.json}`: 사용자정답/사전고정성과/사후회귀분리. 기존사전계획·예측불변.
- 같은폴더 `build_review.py,index.html`: R/S확인완료로문구정정,재질문없음.
- `artifacts/edge-midblock-features-20261018/{plan.json,run.py,result.json,patches.pt,fold-*.pt,verification.json,semantic-coverage.json}`: 특징층대조·학습범위감사.
- `artifacts/edge-wide-semantic-negative-20261018/{plan.json,run.py,result.json,wide-features.pt,wide-input.png,fold-*.pt,verification.json}`: 기존구역넓은뷰대조. source질량/held분리검사.
- `artifacts/surface-edge-confusion-20261018/{build_report.py,index.html,summary.json,52개위치표시PNG,verification.json,verify.py}`: 실제사진위정답/최고반응/전체26구간·점누락전후.
- 같은폴더 `pikachu-T-review/{proposal.json,prepare.py,index.html,T-native.png,T-guide.png}`: 이미표면6점·영역확인완료한기존train피카츄에서,아직비어있는인접바깥끝선T 한곳만새라벨요청. 이전1번표면점그대로표시. 아직모델추론/학습없음. 완료표면6점/영역/전체정상재질문없음.
- `SURFACE_EDGE_CONFUSION_VALIDATION_20261018.md`: 이검증문서.
- 소비프로젝트 `CONDITION_ANALYSIS_TODO.md`: 실행체크포인트. 소비런타임변경없음.

## 실행 검증

- 후보2개각각원본26출력·실제사람점4점수저장후재추론, 모두최대차0. backbone원본forward는공유26+R/S2로28회,원본평가출력52개확인. R/S각3fold평균후보2개는사후회귀로만기록.
- 학습안수렴·원본해시/그룹분리·원본183 SHA불변·새R/S진실범위·S surface1→edge1로확대하지않음검사.
- 관련unittest27개통과(regression_audit,dino_wear_lora,local_wear_cnn,point_patch_head).
- 원본183 SHA `23fbe9ea6f4be297887c87a32ccc496cc95e08162292cfe711b11ab43b94935a` 유지. 사전고정R/S문서SHA유지. 신규HTML참조존재·표시사진직접시각확인. 앱열기요청과실제E2E렌더확인은구분.

## 리스크·롤백

출처별자료부족·표면결함하위질감다양성·역사적기하미검토·반복개발평가선택편향이남음. 이번두후보미채택이므로런타임롤백불필요; 기존고정448연구경로유지. 연구artifact를사용하지않으면기존동작동일. 사람확인정답·학습사용이력을삭제/변형하지않음. HTML은generator로재생성. OpenCV/Gemini/운영모델/API수정없음.

## 다음 사람 입력이 필요한 이유

기존train피카츄에는직접찍은표면6점과box_reviewed=true가있지만엣지정답은null이다. 그표면점1근처의짧은카드끝선T만확인하면‘안쪽표면흔적을포함하지만바깥끝선은정상’인학습근거인지판단할수있다. 기존표면점·카드영역은완료로그대로두며T외구역으로정상범위를넓히지않는다. R/S는평가용으로보존해학습에쓰지않음.

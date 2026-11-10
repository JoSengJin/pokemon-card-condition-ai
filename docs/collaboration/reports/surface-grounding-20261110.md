# α0 실제 손상 위치 근거 진단 개발 — 2026-11-10

**개발 진척78/100(usable-card-analysis-v1.13) 유지. 전체 오류224개와 정답 대조89개를 연결한313구역 검토 도구를 개발하고, 동결α0 재생·사람 설명 sidecar 검증을 완료했다. 새 사람 답0,모델 개선 미평가,재학습0.** 남은 의존은 기존 구역 정답을 다시 묻는 것이 아니라 실제 손상/정상 설명 위치 또는 사진상 위치 판단 불가라는 새 근거다.

## 실행·범위·판정

- 재생 소스 `4f82bfbf43bcae8dd644b5003cca1ca614f778f4`, 계약 `2b3ad33`. 이후 답 검증/기하 비교 도구 소스 `06f49c6ce32f81b12d54e085c7629de3f4513224`; 재생과 후속 도구 개발의 소스 경계를 구분한다.
- 가설ID `surface-alpha0-grounding-diagnostic-20261110`, **진단 재현 실험**이며 새 성능 가설이 아니다. 계획 `artifacts/surface-grounding-20261110/plan.json`,SHA256 `bf265fa6cd14bb83243027756b585d7433fc6ce3d4a7c1c1e131e85aced2ab54`.
- 공통 기록 `artifacts/experiments/20261109T234706-4aeb730c/record.json`, **completed/exit0**. KST2026-11-10 08:47:06→08:50:36. 동결 재생1회,학습/optimizer/newlabels/외부AI/자동review0. 재생 경과208.152초는 순수 추론·통제된 속도 개선 비교가 아니다.
- 명령: `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-grounding-20261110/plan.json -- .venv/bin/python artifacts/surface-grounding-20261110/worker.py`.
- 참조 `artifacts/experiments/20261108T215307-941b3aaa/result.json`,같은5revised OOF heads,CPU동결DINO ViT-S14/448px/원본crop·physicalmask/float32 affine score/max/sigmoid/threshold0.5. 각사진의원래held-fold head만 재생하고 해당head train group/photoSHA 비중복을 검증했다. 기존손실·계수·라벨·mask·fold·운영/fallback·다른worktree 변경0.
- 공통 acceptance_passed=true는 **재현 판정**이다: score오차≤2e-6·1776행/정답/예측불변·FN57/FP167/no new errors. 기존 모델 품질 FN≤67/370·FP≤112/1406·원래대비AUC차≥0.03·paired하한>0·직접α0차/하한>0 기준은 변경하지 않았고 미달 상태 그대로다. 원래 품질통과로 보고하지 않는다.

|기존 α0와 재생|값|이전 대비|
|---|---:|---:|
|구역/사진group|1776/204|동일|
|결함/정상|370/1406|동일|
|AUC|0.931924954826804|0|
|누락|57/370,15.4054%|0%p|
|오탐|167/1406,11.8777%|0%p|
|최대 저장점수 재생오차|5.960464477539063e-8|허용2e-6 이내|

관찰 제한 누락/오탐 미평가. 반복 개발·오류선택 진단이며 독립 일반화 개선을 증명하지 않는다. 새모델·성능향상 없음.

## 실제 위치 근거 감사

현재 canonical `artifacts/development-manifest-20261031o/combined-reviewed.jsonl`과 현재204사진에 대응하는 intake review labels*.jsonl20개(이전.before 제외),총21개파일을 검사했다. 원본JSON/사진/정답은 읽기만 했다.

- 점 발생1439건: surface853/corner196/edge390. 중복 발생 수이며 독립 점/사진 수로 쓰지 않는다.
- 정확히 재사용 가능한 surface점0·연결구역0. 사유집계: 다른 사진/group/side792,다른/없는종류586,명시적양성surface점조건미충족61. 다른종류점을 표면점으로 바꾸거나 다른사진좌표를 옮기지 않았다.
- 검사한 현재자료 기준370결함구역 모두 정확히매칭되는 재사용점이 없다. 모든과거파일에점이없다는주장이아니다. region presence 정답은 이미있고 위치정답과다르다.
- 재사용조건은 정확한사진SHA+실물group+앞뒷면+명시적surface종류+확정양성+같은단일구역내좌표. 원문/좌표/source/line 보존,동일점중복출처병합,정상구역충돌·경계다중구역·비유한/잘못된좌표 거절. 미클릭영역/판단불가를 정상으로 만들지 않았다.
- 근거 `annotation-sources.json`,`location-audit.json`. 기존 완료구역라벨 재요청0.

## 선택과 검토 화면

전체1776행은 packet.json/patch-logits.pt에보존했다. FN57+FP167=224오류를 모두 포함한다. 각5fold×9area에서TP/TN이있으면각각ID SHA256최솟값1개를대조로선택(점수크기미사용),TP44/TN45=89개. 합계 **313구역/147사진**을화면에표시한다. 없는stratum을임의사례로채우지않는다. 오류선택집합의모집단대표성은주장하지않고,OOF오류를학습선별/가중에사용하지않는다.

- HTML `artifacts/surface-grounding-20261110/report.html`,원재생HTML은공통run/report.html. 이전root표시는report-replay-only.html에보존했다.
- 원본확대/기존구역정답을먼저표시,모델반응은별도펼침. 반응지도32×32/최고노랑/둘째청록/실제사진겹침비율. float32 rawlogits/mask는full1776×1024로보존,시각화점수만소수6자리로표시한다.
- 모델token사각형은lattice의기하학적지원범위이며실제손상정답·원인·제한된ViT수용영역이아니다. rawcrop과responseoverlay는같은원사진좌표를쓴다.
- 기존확정위치가있으면읽기전용재사용하고새위치폼을만들지않는다(합성분기검사통과). 현재새위치/설명대기313개. 구역정답변경입력없음. 기본응답은빈미확인,명시적위치또는cannot_localize만받는다. 정상구역의점은normal_explanation이며음성patch학습정답으로자동해석하지않는다.
- 원본클릭/키보드좌표입력,설명종류·원문메모,가시적인JSON선택/복사,같은packet의기존설명불러오기. 새로고침전복사가필요하며자동서버/외부전송/영구브라우저저장없음. 방금입력한미반영설명은수정가능,불러온기존설명은다시요청하지않는다. 일부응답만제출가능.
- packetID `397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc`;변경된ID/사진SHA/구역정답/좌표범위/다른점종류/중복/unknownID/기존확정위치덮어쓰기/임의라벨필드를거절한다.

## 답 수신과 비교

사람이복사한JSON을별도파일로받은뒤현재추적answers.py를사용한다. 아래의human-evidence.json은**앞으로받을사람답경로**이며이번에만들거나채우지않았다.

```sh
.venv/bin/python tools/diagnostics/surface-grounding-20261110/answers.py \
  --packet artifacts/surface-grounding-20261110/packet.json \
  --answers artifacts/surface-grounding-20261110/human-evidence.json \
  --output artifacts/surface-grounding-20261110/human-evidence-validated-001.json
```

open('x')로신규sidecar만저장하고기존답/원본라벨덮어쓰기를거절한다. 원문note/제출답전체와입력파일SHA를보존한다. 미제출pending_ids와명시적cannot_localize_ids를분리하며,후자는새사진등추가근거가필요한상태다. 사람이제출한점과모델최고token사각형의포함여부를model_support_comparisons에계산하지만**기하비교만이며인과/위치정확도/AUC개선이아니다**. 위치판단불가/지원범위없음은null,causal_attribution_proven=false. annotation_applied_to_training=false/region_truth_changed=false이며자동학습연결없음.

## 검증·소스 경계·메모리

- 합성Python검사와Node검사통과: 종류/같은사진group/side/중복/경계/미확인/정상충돌 감사,전체오류와해시대조선택,기존score API동치,32×32geometry,원문/packet/사진/정답/좌표/점종류/추가입력/파일덮어쓰기거절,HTMLescaping/공백#?경로,JS좌표/정상설명/판단불가/명시적답,기하포함True·판단불가null. checks.log/checks-answer-comparison.log.
- 실제1776packet의빈응답roundtrip은0답/313pending을유지했다. 기존점1개인합성renderer는폼0개/원본+반응지도점2개로재요청하지않음을검증했다. 합성사람답은임시디렉터리에서만사용했고실제사람답0이다.
- Python함수 audit4/answers2/report3/checks2/worker0,JSreview7/JSchecks0. 보고경로worker→render→panel→crop3전이,추출worker→backbone_features→view_tensors→prepared_image3전이,답CLI→ingest→validate→packet_digest3전이. 모두≤7함수/≤4전이,재귀/학습callback없음.
- 공통기록snapshot/runtime source hash와281frozen inputs,204사진SHA,1776행/정답/저장score/OOF분리,313사전선택/pending,rawlogits/mask/id/topindex,packet hash검증통과. EXIF방향196개없음/8개1로회전변환모호성없음. HTML313원본/313모델지도/313미확인폼/내장packet/모든사진경로를검산했다.
- 재생완료뒤위무결성을먼저검증한후,추적answers.py/checks.py만기하비교용으로보완했다(06f49c6). **동결runtime/plan/스냅샷/재생worker/JS/사진/모델은그대로**다.281개입력중현재달라진추적2개는postflight.json에명시하고as-run검증시각/새도구SHA를분리했다. 이보완때실제재생을다시실행하지않았다.
- 한사진최대9구역특징만보유했다. 전체logits7274496bytes+mask를보존하며전체384D사진특징을쌓지않았다. worker resident high-water745766912bytes=0.69454956GiB(보고HTML생성후포함). 메모리계측은동결진단worker범위이며이전학습과의실측절감률/시스템전체/가상메모리/swap측정은아니다.
- 공통실행기반환뒤latest.json과지정된old20261024 ai_calls_forbidden handoff를구분했다. 이번run에새development_handoff/next_steps/token_report없음. 자동review/Gemini/Codex/추가학습호출0.

## 변경 파일·열기·위험·롤백·남은 의존

신규소스7개: tools/diagnostics/surface-grounding-20261110/{audit.py,answers.py,report.py,review.js,checks.py,review_checks.cjs,worker.py}. 문서2개:같은ID의task와이report. 핵심diff는정확한기존위치연결·동결α0스트리밍재생·원본/반응분리화면·명시적사람설명수집/검증/기하비교다. 기존patch_evidence.py/patch_geometry.py는동결복사재사용하고원본을수정하지않았다. 운영모델/손실/학습라벨/품질기준/진척률 변경0.

기본sandbox OSopen은−10661로실패했지만,동일OSopen을host권한으로실행해exit0·열기요청성공을확인했다. **실제렌더·모바일조작은미확인**이다. file콘텐츠관찰보안정책은유지했으며다른browser/서버/터널/CDP로우회하지않았다. opening-status.txt에양쪽결과보존.

남은의존은313개중선택할새사람설명이며현재수신0. 기존정상/결함재판정을요청하지않는다. 실제손상위치/정상혼동설명/사진판단불가를사람이입력해야원인별분석을이어갈수있다. 일부응답부터검증가능하며불명확한그림을자동으로분류하지않는다. 독립일반화·AUC향상·인과원인·실제브라우저동작·실사용성은검증하지않았다.

리스크: 오류선택편향,사람설명의주관성,모델지도를본뒤의확인편향,메모리상답의복사전유실,기하지원범위를실제근거로오해할위험. 원본먼저/반응별도펼침·명시적미확인·정답고정·복사안내·sidecar분리로범위를제한했다.

롤백:진행중실험/후속의존확인후`./develop -- git revert 06f49c6ce32f81b12d54e085c7629de3f4513224 4f82bfbf43bcae8dd644b5003cca1ca614f778f4`로새도구변경을역순취소한다. 원본모델/라벨복구는필요없고공통기록/packet/사람답은보존한다. force/reset/증거삭제없음. 원격main은일반push후SHA일치를확인하며remote-sync.json에남긴다. 기존.claude/와다른worktree/보존checkout은변경하지않았다.

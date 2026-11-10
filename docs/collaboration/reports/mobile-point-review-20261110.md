# 모바일 원격 정적 위치 판정 방식 적용 — 2026-11-10

**개발 진척78/100(usable-card-analysis-v1.13) 유지. 요청한 단일파일/일반내장이미지/작은묶음/3가지판정/execCommand·textareaJSON전달을 구현·검증했다. 모델학습·추론·새사람답0이며모델성능개선이아니다.**

## 범위와 라벨 의미

- 검증소스SHA `2be357ce584c159f55c88d731f4bdd881600a567`,계약4cb9c42. 기존위치검토/worker/packet/regionlabel/fallback/품질기준/개발점수 변경0.
- 현재313구역의정상/결함은이미확정돼있다. 이를다시묻지않고화면에읽기전용으로표시한다. 새3가지선택은**사용자가원본에서새로찍은위치**의normal/defect/unknown이다. 모델후보는정답이아니라미확인표시의도움정보다.
- 정상·결함은명시적선택+원본내위치+「기록」이있어야응답이된다. 미기록은배열에없으며모르겠음은point=null,별도unknown으로보존하고binary정답목록에서제외한다. 모델좌표를사람좌표로자동복사하지않는다.
- 이미확정된구역/위치/불러온답을자동재판정하지않는다. 기존knownpoint가있는항목은폼을생성하지않고기존위치를재사용한다. 현재입력은매칭knownpoints0/완료구역판정313개인것을구분한다. 실제새사람답수신0.
- 기존정상구역에서사용자가새결함점을명시하면답원문을보존하고conflicts_with_existing_normal_region에표시한다. 기존구역정답을덮어쓰거나학습에자동편입하지않는다. 정상점은결함구역내다른정상위치일수있으므로구역전체정상으로확대하지않는다.

## HTML·터치·후보·JSON

신규 `artifacts/mobile-point-review-20261110/review-01.html`~`review-63.html`,전체313위치확인항목을최대5개씩보존(마지막3). 먼저연파일review-02.html은이전원본묶음02와같은5구역이다.

- 일반img+dataURI만사용,SVG/외부사진경로/서버/터널/localStorage/외부CDN없음. 검증된nativecrop renderer를재사용하고pixel보정/리사이즈/AI복원없이원본crop먼저,전체사진접어서펼침.
- font18px·버튼최소높이44px/너비72px·checkbox20px. 원본클릭/수동좌표지원,정수cropbounds역산과원구역범위검증유지. 새점은자주색,기존점파랑.
- 「미확인 모델 후보 겹쳐 보기」는기본꺼짐. 켜면별도CSS사각형에미확인표시,모델지도도별도펼침이다. 후보/점수가실제정답이나인과·한정수용영역을증명하지않는다.
- 정상/결함/모르겠음버튼에기본선택없음. 기록후답에포함되며「JSON복사」는usergesture에서execCommand('copy')를시도한다. 실패하면항상보이는readonly/선택가능textarea를길게눌러복사할수있다. navigator.clipboard는사용하지않는다. nativeBlobJSON저장·동일묶음답불러오기·부분제출도지원한다.
- 구역완료정답과새위치정답의의미가달라기존location-explanationJSON을자동으로binarypointlabel로재해석하지않았다. 옛HTML/옛JSON은그대로보존하고새kind는surface_point_review_answers다. 새파일에서불러올답은이새kind파일이어야한다.
- 새pointpacket `8cca9f9bd206ac1ad04fe0ad395a71cfca47c43db3695ebbddf202979a1fad96`,원본sourcepacket `397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc`에연결된다. HTML에는313행의id/readonlyregion_target/imageSHA/box/completed만투영하고동일packetID를유지한다.

## 답 검증과 저장

사용자가확인해만든JSON만새도구로수신한다. 아래human-answers.json은미래답경로이며이번에작성하거나임의로채우지않았다.

```sh
.venv/bin/python tools/diagnostics/mobile-point-review-20261110/review.py --packet artifacts/mobile-point-review-20261110/packet.json --answers artifacts/mobile-point-review-20261110/human-answers.json --output artifacts/mobile-point-review-20261110/validated-001.json
```

packet/image/기존region_target/새id/정답종류/위치범위/비유한값/bool좌표/중복/완료항목/추가라벨필드를검증한다. 원문note/응답전체와입력파일SHA를보존하고open('x')로기존답덮어쓰기를거절한다. human_point_labels에는명시적normal/defect만,unknown_ids와미기록pending_ids는분리한다. region_labels_changed=false/training_applied=false/causal_attribution_proven=false. 모델지원내위치여부는기하정보일뿐위치정확도나원인정답으로쓰지않는다.

## 실행 검증·변경·위험·롤백

합성Python/Node체크통과(checks.log):직접3가지선택/미기록없음/unknown정답제외,구역진실readonly·완료항목거절,정상구역새결함점충돌보존,정확한사진/packet/범위/중복/nooverwrite/원문보존,completed폼0,원본PNGpixel일치,일반img3개/건과후보미확인,18px/44px,실제NodeBlobUTF-8JSONpayload,execCommand실패시보이는JSONfallback. NodeDOM부분fixture검사이며실제폰브라우저검사가아니다. 최초합성fixtureROOT경로오류는새사진/모델작업없이수정했다.

실제63파일/313사례검산:전체ID한번씩/3~5건,각파일3종일반img/건전부dataURI,SVG0/외부사진0,313rawPNG RGBbytes가원본crop와정확일치. fullphotoSHA·모든projection필드·기본선택없음·미확인후보별도·canonical구역packet/oldHTML/frozenruntime불변. 실제packet빈답roundtrip0labels/313pending,새실제사람답0. 첫파일4.3035MiB/최대8.7795MiB. 이는폰메모리절감률이아니며새학습/성능평가없음.

함수수 review.py5/checks.py3/build.py0/productionJS7/Nodechecks7,각≤7. build→render→기존crop_view2전이,CLI→ingest→validate→digest3전이,JS handleClick→refreshExport→validateAnswers→exactKeys3전이(이벤트경계포함≤4). 재귀/모델callback없음.

변경7파일: 신규tools/diagnostics/mobile-point-review-20261110/{review.py,review.js,build.py,checks.py,checks.cjs},새task/이report. 핵심diff는명시적새위치3분류/완료라벨보호·미확인후보overlay·execCommand복사·확인답만저장/충돌분리이며이전도구소스를수정하지않았다. 새dependencies/외부AI없음. 기존α0성능수치/정답분모는그대로이며개선이나독립일반화는미확인이다.

hostOSopen review-02.html exit0,열기요청성공. 실제새화면폰터치/복사/다운로드는미확인이고사용자기존확인은이전native표시점검에한한다. file콘텐츠관찰정책우회/다른browser/서버/터널없음.

리스크: 새로고침전저장안한답유실,브라우저별copy/save차이,구역정답과새위치정답혼동,사진자체판단한계,기존구역과새점판정충돌. 미확인/모르겠음보존·명시적위치선택·readonly구역·충돌분리·보이는textarea로범위를제한했다. 옛JSON을새형식으로자동변환하지않는다. 실제새위치근거가아직없어모델가설선택/학습은진행하지않았다.

롤백은후속의존확인후`./develop -- git revert 2be357ce584c159f55c88d731f4bdd881600a567`후관련검사/일반push. 이전검토파일/모델/정답은그대로라복구불필요. 신규packet/사용자답/증거는보존하고force/reset/다른worktree/.claude변경없음. 원격SHA검증은remote-sync.json에보존한다.

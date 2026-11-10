# 원본 픽셀 모바일 위치 검토 — 2026-11-10

**개발 진척78/100(usable-card-analysis-v1.13) 유지. 사용자가 잘보인다고확인한일반내장이미지방식을실제위치검토에적용했고,313구역을63개자기완결HTML로나눴다. 새학습/모델추론/사람답0.** 모델개선성과가아니며새손상위치입력은여전히사람의근거가필요하다.

## 소스·범위·기존 근거 보존

- 최종검증소스 `ca79c77c8eae9ce180f9cdc41aa7da64a9544000`,본체 `f65927e3395741a8a1fbea034c990aa70dd78e22`,계약bb3bd0b.
- 기존위치검토의SVG/외부상대사진경로문제를줄이기위해원본바이트를해시검증후한번읽고crop/context를같은원본에서생성한다. 일반img의dataURI로내장하고raw는losslessPNG,전체문맥사진은원래압축바이트그대로다. rawcrop리사이즈/선명화/AI복원없음. 이미지프레임은원래구역픽셀크기이하로표시한다.
- 사용자원문“10개정도 무작위로 확인해봤는데 판정할 수 없는 상태야”는기존feedback에보존,어느ID인지모르므로개별라벨이나313개전체판단으로확장하지않았다. 새원문“화질 점검 자료는 잘 보이네 여하튼 다음 개발 진행해”는display-check표시방식확인으로만기록했다. 새검토UI/터치/다운로드까지사용자확인됐다고말하지않는다.
- 기존canonical packet `397ed4fb79b6ff215a6cd4ec5d582b86b8cd1f9af7db63cbe3dc713c820f10cc`,313선택ID/원래순서/1776행·정답/모델계수·손실·품질기준/oldHTML/runtime/snapshot/기존사람답 불변. 새실험/commonrecord없음. 과거α0공통record20261109T234706-4aeb730c와그snapshot은그대로다.

## 화면·답 전달

`artifacts/surface-grounding-mobile-20261110/review-01.html`부터`review-63.html`,최대5구역/마지막3구역. 전체313선택을중복/누락없이그대로분할했다. 새score기반선별/모델선택/학습자료변경이아니다. 처음전달하는`review-02.html`은FN3+FP2로실제손상위치검토를시작할수있는묶음이다. 전체목록index.html은데스크톱목록이며,휴대폰에한파일만전달됐을때는다른묶음파일을채팅에서직접받아야할수있다. 모든사진은파일안에있어외부이미지파일은필요없다.

- 원본crop를먼저표시,전체원사진은별도펼침. 실제픽셀수를표시하며확대해없는정보가복구됐다고주장하지않는다.
- 새점/기존점은CSS span overlay로표시한다. click좌표는정수floor/ceilcrop의원본정규화범위를역산한다. 기존region box밖의1픽셀여백클릭도조용히이동시키지않고거절한다. 키보드좌표입력유지.
- 모델지도는저장patchscore/top2기하로만별도PNG에반투명지도·노랑/청록지원을그린다. raw원본PNG는모델색상과분리한다. 모델지원사각형은실제손상정답/인과/제한수용영역이아니다.
- 기존정상/결함은그대로이며새위치/정상설명또는cannot_localize만받는다. 완료된구역정답재요청없음. 미확인을정상으로추정하지않으며normal_explanation은자동음성학습정답이아니다.
- 각항목「이 설명 기록」→「JSON 파일 저장」→채팅첨부. 다른묶음에서도기존JSON을불러오면전체답을유지해합쳐저장한다. 파일명에packet접두어·묶음번호·전체기록수를넣는다. 기존copy/보이는textarea/빈답저장비활성/중복충돌거절/원문메모/partial답을유지했다.
- 화면에는필요한id/target/imageSHA/box/selected/knownpoints만1776순서그대로투영해내장하여큰patch배열중복을피했다. kind=surface_grounding_display_projection이고원래packet_id를참조한다. **투영본은canonicalpacket대체물이아니다.** JSON응답schema는그대로이며Python답검증에는원래packet.json을사용한다.

## 검증과 측정

기존합성Python/Node+추가검사통과(checks.log):

- 단일픽셀신호를포함한원본crop의PNG디코딩후RGBbytes정확일치;fractionalbox[.1234,.2045,.7744,.9033]의정수crop[55,91,347,405]→292×314픽셀/bounds정확일치. 원본사진SHA변경거절.
- JSnativecropbounds좌표역변환·원구역밖거절·기존점/새marker표시수식,답schema/pointkind/unknown/target/image/packetbinding/nooverwrite/원문보존과BlobUTF-8다운로드검증통과. 묶음파일명/다른묶음응답호환도검사했다. 실제폰브라우저실행을대신하는검사는아니다.
- subset중복/원선택밖index거절,현재페이지5사례·전체canonical상태불변·투영필드정확보존을검증했다.
- 함수정의report3/reviewJS7/checks4/Nodechecks5/builder0(각≤7),builder→render→panel→crop_view3전이·JSevent→validate→exactKeys최대3전이. 재귀/새모델callback없음.

실제전체산출물검산(postflight.json):

- 63페이지/313선택ID원래순서정확일치,중복0. 매파일3~5사례/원본·전체문맥·모델지도일반img각3개,SVG0/외부이미지참조0.
- **313개raw PNG전부원본에서잘라낸RGBbytes와정확일치**,표시width/height·정수bounds정확일치. 전체원사진내장bytes의SHA도원래row와일치.
- 매파일1776개투영행의id/정답/사진SHA/box/selected/knownpoints와원래packet_id일치. 기존packet/oldHTML SHA와공통run의runtime source_hashes 불변.
- 첫페이지4.6522MiB,최대9.1283MiB,전체63파일합352.2201MiB. 전체를한번에폰에전달하지않는다. 메모리/폰성능실측절감률은없다. 최초미공개f659패키지는`artifacts/surface-grounding-mobile-20261110-initial-f65927e`에보존한뒤최종ca79소스로다시정적패키징했다. 모델재생/학습재시도는없다.
- hostOSopen `review-02.html` exit0로열기요청성공. **새화면실제렌더/터치좌표/브라우저다운로드는미확인**이며사용자확인은이전display-check에한한다. file콘텐츠관찰정책우회/외부서버/터널/다른browser0.

## 변경·위험·롤백·남은 근거

변경7파일: tools/diagnostics/surface-grounding-20261110/{report.py,review.js,checks.py,review_checks.cjs},신규tools/diagnostics/surface-grounding-mobile-20261110.py,task/이report. 핵심diff는native내장픽셀·정확좌표·CSSmarker·별도raster모델지도·5건분할·표시투영·같은JSON답유지다. 원본사진/모델/라벨/손실/fallback/진척조건 변경0. 저장된α0 AUC0.931924955·누락57/370(15.4054%)·오탐167/1406(11.8777%)를그대로표시하며새성능측정/향상은없다(변화0%p).

리스크: 원본자체가손상을관찰하기어려울수있음,새UI의폰조작미확인,최대9.13MiB파일이일부뷰어에서부담일수있음,파일별답을저장하기전새로고침하면유실될수있음. 일부응답만가능하고불명확하면cannot_localize로남긴다. 확인안된약10건을다시확정정답으로쓰거나자동라벨하지않았다. 다음모델가설을정하려면실제위치/설명근거가여전히필요하다.

롤백은후속의존확인후`./develop -- git revert ca79c77c8eae9ce180f9cdc41aa7da64a9544000 f65927e3395741a8a1fbea034c990aa70dd78e22`후관련검사·일반push. 생성HTML/기록/사람답은보존하고원본모델/정답복구는필요없다. force/reset/기존worktree/.claude정리없음. 원격동기화증거는remote-sync.json에기록한다.

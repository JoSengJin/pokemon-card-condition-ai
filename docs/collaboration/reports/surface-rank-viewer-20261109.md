# 오순위 사진쌍 viewer 인수·완료 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 사용자가Claude에전달하지못한viewer를 **Codex가단독인수해구현·검증·main반영**했다. 사진쌍15개의두사진/관련구역·사람정답·점수·fold·margin과전체204사진/1776구역을볼수있다. **새학습/사진추론/통계fit0,모델성능변화없음**이다. Claude구현/리뷰/합의는없었다.

## 산출물과 사용

- 실제HTML: `artifacts/surface-rank-viewer-20261109/report.html`.
- 검증: 같은폴더 `checks.log`, `verification.json`, `opening-status.txt`.
- 구현/검증소스: `e89935306c6b7ebc23c56946d7edf7353923633d`. 인수계약7e0ffaa,결과문서커밋과구분한다.
- CLI: `.venv/bin/python tools/diagnostics/surface-rank-viewer-20261109/render.py --input artifacts/experiments/20261109T123217-c4241d83/rank_report.json --output artifacts/surface-rank-viewer-20261109/report.html`.
- 표준라이브러리만사용하는정적HTML/CSS. 서버/JS/CDN/API/새의존성없음. 작은화면1열/큰화면2열의선언적CSS를넣었으며실제브라우저반응형렌더는미확인이다.

## 변경 파일과 핵심 diff

신규구현 `tools/diagnostics/surface-rank-viewer-20261109/{render.py,checks.py,fixture.json}` 3개. 새인수task `docs/collaboration/tasks/claude-surface-rank-viewer-20261109.md`,새이결과MD,기존공유task `surface-rank-partition-20261109.md`와Claude프롬프트의소유권/보관상태갱신까지총7개파일이다.

renderer는고정schema v1을검증하고3bucket/전체의쌍분모·쌍비중·오류비중·조건부AUC를표시한다. 동점credit0.5/빈bucket auc=null을구분하고전체AUC를단순평균하지않는다. 15사례각각사람정답결함/정상두사진을나란히배치하고해당구역을강조하며,같은사진의다른두구역도별도강조한다. 각패널의표에는원래점수/threshold출력/TP·TN·FP·FN이있다. 전체사진갤러리는원본구역1776개를모두보존한다.

박스를사람결함점/모델peak로표시하지않고,1e-12범위의좌표반올림오차는검증에허용하되원본JSON을변경하지않는다. SVG만사진경계안으로clip한다. 사진path는입력JSON기준으로resolve한후출력HTML기준상대URL로변환하고공백/#/?를percent-encode한다. 원격URL은거절하고HTML텍스트/속성은escape한다. 파일이없으면명시적missing을표시하고,출력경로가원본JSON과같으면쓰기전에거절한다. 입력내용·사진·점수·라벨·기준·모델·손실은수정하지않는다.

## 실행한 검증과 근거

`.venv/bin/python tools/diagnostics/surface-rank-viewer-20261109/checks.py` 통과:

- 합성fixture5구역/3사진/3관계의사진쌍과대상6패널,같은사진의두구역/다른fold사례.
- 동점0.5credit·쌍0의auc=null·원래JSON불변·HTML파싱/escaping·공백/#/?사진경로/missing표시.
- 실제CLI성공,원본JSON으로출력을지정할때거절/원본SHA보존.
- 잘못된provenance/정답·출력불일치/NaN/큰box범위/쌍credit/AUC/share/사례관계/원격사진URL거절.
- 최초합성검사에서macOS의/var별칭과resolve된/private/var의혼합으로상대경로가길어지는문제를발견했다. render_document가입출력경로를함께resolve하도록수정후해당회귀검사와전체합성을통과했다. 사진경로변경/복사는없다.
- AST 함수수render6/checks1(파일당7이하). 실제project호출은main→render_document→photo_panel→zone_table최대3전이(기준4이하). 동적project callback/재귀없음.

실제적용검증 `verification.json` 통과:

- 고정입력 `artifacts/experiments/20261109T123217-c4241d83/rank_report.json`,원진단record는completed/exit0. 이번viewer는표시만하므로새experiment/성능평가record를만들지않았다.
- 15쌍/대상30패널·204사진갤러리/1776원본구역ID,반복사례를포함한234이미지참조경로존재와원본204사진SHA일치.
- 모든저장score/15margin표시,HTML파싱,전체구역의사람정답/출력일치.
- 원공통record의hashmanifest는rank_report.json을직접포함하지않는다. 따라서“record검증만으로rank_report도동결검증됐다”고주장하지않았다. 원래11개동결입력SHA를확인하고저장score/원진단analysis로total/buckets/examples/photos를다시계산하여전체payload일치와source_record/source_sha일치를확인했다. 새추론/fit은없었다.
- viewerSHA256 `1200dd3d05ac99025e6793fd06ced557cd7bdc8de206003d382d9c9eb503b07f`,입력JSON SHA256 `b930b7ca6063269d89470c4ab44c0d1ac8ca7dfe75846da90c3e76f5323cbeac`.

## 모델 수치와 한계

기존α0의결함370/정상1406,전체520220쌍/오순위35414/동점0/AUC0.931924954826804를그대로표시한다. FN57/370(15.4054%),FP167/1406(11.8777%),이전대비변화0%p. 원래FN≤67/FP≤112품질기준은바꾸지않았으며FP167로미충족인상태도그대로다. 관찰제한누락/오탐은미평가다.

오순위사례는각bucket margin상위5쌍으로대표성/시각원인/인과를증명하지않는다. 다른fold비교는다른학습head와사진분포의효과를분리하지못한다. 반복개발OOF·독립일반화미확인이다. 이번완료는검토화면구현과저장근거검증이며AUC향상/모델채택이아니다. PROGRESS_CRITERIA.md/development-progress.json의78/100v1.13을확인하고보존했다.

## 열기·리스크·롤백

macOS open명령 exit0. 같은대화에서file:콘텐츠관찰이브라우저보안정책으로차단된이력을존중해다른browser/서버/터널/스크린샷등으로우회하지않았고 **실제render미확인**으로기록했다. 사진파일·표시값·HTML구조의정적검증과실제렌더확인을구분한다. 원본이미지업로드/외부전송없음.

리스크/미검증: 실제브라우저/모바일레이아웃의육안확인,오류원인의시각판정,독립일반화/실제모델개선은하지않았다. 조회출력은현재저장자료의snapshot이며새정답을받거나모델오류를이유로라벨을바꾸지않았다. 입력의희귀정상/반사/무늬를원인으로단정하지않는다.

운영모델변경은없다. 코드롤백필요시실행잠금/후속의존을확인한뒤viewer커밋e899353을일반gitrevert하고합성검증/일반push한다(인수/결과문서는별도상태갱신). force/reset/이전실험snapshot덮어쓰기/증거삭제없음. 비소유.claude/와다른세션worktree/브랜치/미통합작업은보존했고새worktree는없다.

에튜 포인트: 파일경로와브라우저URL은다르다. 예를들어파일명이normal #?.png이면src에는normal%20%23%3F.png가필요하다. 이번에는입출력경로를먼저resolve해macOS경로별칭을통일하고상대경로를percent-encode해동일한사진을가리키도록했다.

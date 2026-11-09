# 저장 OOF 순위 분해와 Claude 페어코딩 준비 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. Codex는저장α0 점수의순위분해코드/합성검증/공통진단/사진별HTML을완료했고,Claude에는별도viewer구현프롬프트를준비했다. **새학습/추론0,모델성능변화없음**이다. Claude가실제로검토/구현했다고주장하지않는다.

## 결과와 개선 판단에 주는 근거

직접대조α0의1776구역(결함370/정상1406)/204사진,520220쌍을그대로사용했다. 전체AUC0.931924954826804,FN57/370(15.4054%),FP167/1406(11.8777%)를보존했다. 이전대비누락률/오탐률변화0%p,관찰제한누락/오탐미평가. 다른정답/분모를혼합하지않는다.

|쌍관계|쌍수|전체쌍비중|오순위수|전체오류비중|조건부AUC|
|---|---:|---:|---:|---:|---:|
|같은사진|1520|0.2922%|173|0.4885%|0.886184211|
|다른사진·같은fold|100493|19.3174%|6923|19.5488%|0.931109630|
|다른fold|418207|80.3904%|28318|79.9627%|0.932287121|
|전체|520220|100%|35414|100%|0.931924955|

동점0. tie발생시0.5credit을사용한다. AUC=1−error_credit/pairs이며전체AUC는bucket AUC의쌍수가중평균이다. 조건부AUC의단순평균이아니다. threshold기준FN/FP와쌍순위오류도다르다.

같은사진조건부분리는더약하지만분모가작다. 다른모든쌍의순서가고정이라는산술가정에서이173오류만없애도전체AUC증가상한은0.0003325516이다. 실제헤드재학습은다른쌍도변경하므로이를훈련결과/counterfactual예측으로사용하지않는다.

다른fold오류약80%는쌍비중약80%와비슷하고조건부AUC도다른사진·같은fold보다낮지않다. 따라서이집계만으로“fold calibration이주원인”이라주장하지않는다. 다른fold는서로다른훈련head의score비교이며사진/정답분포와모델차이의인과분리가안됐다. 다음표현변수를바로추가할증거로확대하지않고,viewer로큰오순위사진쌍을대조할수있게연결했다.

## 실제 실행/검증

- 검증/실행소스 `2cd12bb1975c5d5374b2b3a14ac5cf176246d32c`. task/prompt기준463c892,최초진단09a556b,좌표검사보완2cd12bb. 결과문서커밋과구분한다.
- 성공공통기록 `artifacts/experiments/20261109T123217-c4241d83/record.json`, **completed/exit0**,diagnostic_valid=true. 명령 `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-rank-partition-20261109-boundary/plan.json -- .venv/bin/python artifacts/surface-rank-partition-20261109-boundary/worker.py`.
- 첫기록 `20261109T123119-8d52c6c6`은failed:저장box9개의1.0000000000000002경계를엄격한0..1검사가거절했다. 원본좌표를보존하고검증허용오차1e-12를추가,합성경계accept/1.01reject검사후별도기록으로실행했다. 이실패를모델성능으로해석하지않고옛runtime/snapshot/log를보존했다.
- `.venv/bin/python tools/experiments/surface-rank-partition-20261109/checks.py`:30개독립nestedloop oracle에서3bucket쌍수/오류/동점/credit/AUC일치,동점/빈bucket/zeroerror/행순열·example순서불변/잘못된score·ID·fold·사진그룹·box경계검사통과. AST 함수수analysis4/worker0/checks2(analysis의정렬key lambda포함),7이하. worker→partition→validate최대2전이,정렬callback포함3전이이하;재귀/모델callback없음.
- postflight:공통record해시/동결입력11개/사진204장SHA/1776행·저장scoreidentity/520220쌍합계/AUC1e-12재현/15example정답과score방향/204photos와1776zones schema검증통과. 사진추가추론/학습/정규화통계fit0.
- 기존모델품질FN≤67/FP≤112는변경하지않아FP167로미통과를유지한다. 공통result의모델acceptance실패와저장점수진단의성공을구분한다.
- 공통반환후development-cycle/latest.json은별도20261024 ai_calls_forbidden pointer그대로다. 이번record의evaluation을진단상태로사용하며새model adoption/development_handoff/token_report를꾸미지않는다. 실제학습/외부AI/자동review0.

## Claude 작업 분리

프롬프트: `docs/collaboration/prompts/claude-surface-rank-viewer-20261109.md`. Claude기준SHA는좌표보완을포함한2cd12bb1975c5d5374b2b3a14ac5cf176246d32c. 별도worktree/branch에서 `tools/diagnostics/surface-rank-viewer-20261109/{render.py,checks.py,fixture.json}` 및전용task만수정한다. Codexanalysis/worker/checks·공유schema·모델·main/다른작업파일을수정하지않는다.

고정입력schema v1은task에포함. 실제입력은완료공통record의rank_report.json이다. Claude는실제사진/정답/기본checkout의artifacts·venv를복사/공유하지않고합성fixture만사용한다. JSON→정적HTML CLI,전체구역·3bucket/쌍분모·오순위사례두사진과구역을표시한다. 학습/추론/API/모델CLI/하위agent/자동review/직접main push금지. 전달은전체SHA/변경파일/함수수·호출경로/합성검사/미검증/리스크/롤백이며Codex가반환후별도검증한다.

이viewer는아직Claude가실행/전달하지않았고통합완료가아니다. 프롬프트만으로Claude검토합의/구현이일어났다고보고하지않는다. Codex가만든이번보고서는1회성진단HTML이며Claude의재사용가능한viewer소스를대신구현한것이아니다.

## 변경·HTML·리스크·롤백

변경파일6개: 신규tools/experiments/surface-rank-partition-20261109/{analysis.py,worker.py,checks.py},task MD,Claude prompt MD,이report MD. 핵심diff는저장score쌍분할·정확동점credit·사례선정·고정schema출력이며모델/손실/특징/threshold/라벨수정없음. 기존α0/실패표현/과거증거와비소유.claude/보존.

HTML `artifacts/surface-rank-partition-20261109/report.html`:실제204사진/1776구역의사람정답·저장score·출력·FNFP·분모/0%p변화,3bucket쌍분모/비중/조건부AUC,15쌍링크를표시한다. example은각bucket margin상위5개로대표성/인과/학습선별을주장하지않는다. 구역박스는최고patch/사람결함점이아니다. HTML파싱/개수/사진경로대조통과,macOS open exit0. 같은대화의file:콘텐츠관찰보안정책차단을우회/재시도하지않아 **실제render미확인**. 외부서버/터널/업로드0.

리스크/미검증:저장OOF진단은오류의시각원인·사진분포·모델간보정·새표현성능을증명하지않는다. 독립일반화미확인,관찰제한성능/실제viewer실자료render미검증. raw split의test표시는독립시험이아니다. PROGRESS_CRITERIA.md/development-progress.json의78/100v1.13유지. 속도/정확도개선을주장하지않는다.

운영변경없음. 필요하면의존/lock확인뒤코드2cd12bb→09a556b를역순으로일반gitrevert하고관련검증/push한다(문서충돌검토). 과거/이번실험삭제·snapshot덮어쓰기·force/reset없음. 신규worktree생성0,기존다른세션/미통합/최근통합rollback checkout보존. Claude작업공간을임의정리하지않는다.

에튜 포인트: 전체AUC는정상·결함의모든쌍을센다. 예를들어같은사진1520쌍은전체520220쌍의0.2922%라서조건부AUC가낮아도전체오류기여는작을수있다. 그래서조건부오류율과쌍분모를함께보고개선우선순위를판단했다.

# 국소 대비 특징 단일 가설 결과 — 2026-11-09

개발 진척 **78/100(v1.13) 유지**. 원본384차원에 국소 절대잔차384차원을 추가한 후보는 **직접 α0 대비 AUC 하락·누락/오탐 증가로 가설 미지지, 운영 미채택**이다. 손실 계수·threshold 탐색은 하지 않았다.

## 실행과 고정 조건

- 검증/실행 소스: `42dc2b1182bc8d39c876d7f27759dc070f33bcaf`. 계약 커밋 `2b1d5eb`, 최초 구현 `3e0939a`, 메모리 보완 `42dc2b1`. 결과 문서 커밋과 구분한다.
- 완료 공통기록: `artifacts/experiments/20261109T105308-99e918d6/record.json`, **completed/exit0**. 2026-11-09 19:53:08→20:25:59 KST. worker 경과1968.33초(32.81분). 통제된 속도 비교 아님.
- 첫 시도: `artifacts/experiments/20261109T103853-3fa5c0b6/record.json`, **interrupted/-15**. 특징1776×1024×768 완료 후 첫fold 반복 로그 전,16GiB RAM·시스템swap44272.75MiB 확인. Mac 부담을 줄이려고 Codex가 worker에 SIGTERM을 보냈다. OOM/optimizer 실패/성능실패로 추정하지 않는다. 첫 실행의 snapshot·mirror·계획·console을 보존했다.
- 첫 계획의1회 제한은 Codex가 정한 실행계획이며 사용자의 별도 제한이 아니었다. 성능 결과 없는 자원 중단 후 같은 사용자 승인 가설을 메모리 보완해 추가1회 실행했다. 가설1개/시도2회/완료평가1회. 그 뒤 추가 실행·자동반복·탐색·외부AI 호출0.
- 최종 계획: `artifacts/surface-local-contrast-streamed-20261109/plan.json`, SHA256 `6b37b645a6d3b01a02462a32744147e712f55382b16c93044aaeaafb70457c25`.
- 실행: `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-local-contrast-streamed-20261109/plan.json -- .venv/bin/python artifacts/surface-local-contrast-streamed-20261109/worker.py`. 고유console noclobber. 자동review/Codex/Gemini0.
- 유일 과학 변수: `x → concat(x,abs(x-valid_local_mean3x3))`. 32×32 grid, 자기 자신 포함, grid밖/invalid 이웃 제외. 원본384차원 보존, invalid 위치 추가특징0. 768차원 선형 head, 추가 정규화·스케일 선택 없음.
- 대조는 α0/정상bag1/결함bag1의 `20261108T215307-941b3aaa`. 정상계수2 후보를 대조 손실로 사용하지 않았다.
- N+D+G+L2·α0·L2=1·정상upperLSE tau0.1·결함/출력max·sigmoid·threshold0.5·라벨/마스크/5fold/seed20261031·class/group mass·center정의·영초기화·CPU백본 고정.1000반복/1250평가·최종gradient1e-5/내부1e-7 유지.

## 같은1776구역 실측

|대조|FN/370|누락률|FP/1406|오탐률|AUC|
|---|---:|---:|---:|---:|---:|
|원래 품질 대조|67|18.1081%|201|14.2959%|0.916650648|
|직접 α0 대조|57|15.4054%|167|11.8777%|0.931924955|
|국소 대비 후보|61|16.4865%|171|12.1622%|0.925992849|
|후보−α0|+4|+1.0811%p|+4|+0.2845%p|−0.005932106|

직접 α0 대비 사진그룹 paired bootstrap95% **[-0.011486472,-0.000749598]**(2000회/seed20261107). AUC차>0·CI하한>0의 표현 개선 gate는 둘 다 미충족이다. 같은 반복 개발CV에서 이 고정 표현의 악화 근거이며, 독립 일반화나 모든 국소 대비 특징의 실패로 확대하지 않는다.

원래 품질 대조 대비 FN−6(−1.6216%p), FP−30(−2.1337%p), AUC+0.009342201,95%구간[0.003379800,0.015482812]. 이 구간을 직접 α0 비교의 구간으로 바꾸지 않는다.

|기존 채택 AND 기준|실측|판정|
|---|---|---|
|FN≤67/370|61|통과|
|FP≤112/1406|171|미달|
|원래 AUC 대비증가≥0.03|+0.009342201|미달|
|원래 대비paired95%하한>0|+0.003379800|통과|
|5fold수렴·근거유효|모두 내부목표1e-7|통과|

직접 α0 대비 신규누락13·누락회복9·신규오탐32·오탐회복28. 전체 ID는 `analysis.json/error_changes`와1776행CSV에 보존. OOF오류로 학습 선별·가중·정답변경을 하지 않았다. 관찰 제한 누락/오탐은 이번에 미평가다. 원라벨179/1597 보조평가는 별도evaluation에 보존하며 확정정답370/1406과 혼합하지 않는다.

## 메모리 보완과 실행 검증

기존 fit의 전체float64확장/center차감/positive-mass전체재복제 대신, 원본float32특징을 보존하고8bag씩 float64선형곱과gradient를 계산했다. 모든학습mass가양수인경우 불필요한x[keep] 복사만 생략한다. center는 기존과 같은float64 bag평균/가중합. 총loss/계수/optimizer/정지기준을 바꾸지 않았다. 차원 증가에 따른 파라미터수와L2기하 변화는 입력표현 변경의 일부다.

- `.venv/bin/python tools/experiments/surface-local-contrast-20261109/checks.py`: 독립loop masked3×3 oracle·경계·패딩·행분리·상수/단일유효·원본보존·잘못된입력거절·zero-added-weight 목적함수/gradient일치·768D합성fit 통과. 실제사진/학습호출0.
- `.venv/bin/python tools/experiments/surface-local-contrast-20261109/checks_streamed.py`: 1/8/9/19행 dense-vs-streamed forward/backward·전체loss/5개성분gradient·768D실제합성fit과최종감사 통과. 투영gradient최대차8.5265e-14. 손실오차1e-12/gradient오차1e-10 기준 유지.
- `postflight.json`: 공통record 파일해시·동결입력206개·사진204장 SHA, 동일1776행/라벨,5fold훈련행/target/mass/mask의α0일치, train/eval사진/그룹겹침0, 유한768계수모델5개 검증 통과.
- 실제5fold 반복수126/124/117/120/120,평가수133/134/128/125/129. 최대gradient는 각9.2749e-8/9.3156e-8/9.8556e-8/9.7192e-8/7.4731e-8. component/fit최종theta SHA일치. gradient성분합 최대오차4.54e-16,loss성분합5.56e-16. 산술항loss/gradient는 정확히0.
- AST 함수수 worker0/features1/checks1/objective3/streamed_linear2/checks_streamed1,각7이하. 학습bag경로 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss 4전이. custom projection경로 worker→fit→loss_and_grad→StreamedLinear.apply→forward/backward 4전이(프레임워크 연결 포함). 기존direction2전이. 재귀/추가callback 없음.
- 공통실행기 반환후 `artifacts/development-cycle/latest.json`도 확인했다. 이 세션과 무관한20261024 `ai_calls_forbidden` pointer를 유지하며 이번handoff/token_report로 주장하지 않는다. 이번record에는development_handoff 없음. 실제채택/판정은이번record·evaluation 기준,운영모델변경0.

## 변경 파일·리스크·롤백·인계

신규파일8개: `tools/experiments/surface-local-contrast-20261109/`의 worker.py/features.py/checks.py/objective.py/streamed_linear.py/checks_streamed.py6개, task MD, 이 결과MD. 기존운영소스는 수정하지 않았다. task는실행전 계약/자원보완의동결입력으로보존하고 최종상태는이보고서의 completed/quality_failed/not_adopted를따른다.

핵심diff는 원본특징에국소절대잔차연결,기존α0목적함수의메모리제한투영,직접α0 AUC/CI비교추가다. 훈련변수·손실계수·threshold조정은없다. `.claude/`와기존다른세션worktree/브랜치/증거는편집·정리하지않았다. 새worktree없음;최근통합rollback checkout1개와미통합다른작업보존.

HTML: `artifacts/surface-local-contrast-streamed-20261109/report.html`,CSV1776행. 사진204장 위구역1776개의사람정답·α0/후보점수·FN/FP·분모/%p·개발CV구분·리스크/롤백을표시. HTML파싱/개수/경로/저장점수대조통과. macOS open은exit0. CUA확인은Mac잠금/자동해제실패·browser transport closed로 **실제렌더미확인**. 외부서버/터널/업로드0. 구역박스를최고반응patch/사람결함점으로표시하지않았다.

리스크/미검증: 국소대비가인쇄/반사를강조할가능성은가설이며개별오류의시각원인/인과분해는안했다. 반복CV·부분재판정·단일seed,독립일반화미확인. 시스템swap을이worker단독사용량/peakmemory로주장하지않고,통제된속도/메모리효과미측정. 후보의수렴·합성일치를성능향상/진척으로계산하지않는다. PROGRESS_CRITERIA.md/development-progress.json의78/100 v1.13을유지한다.

운영미채택이므로복원할운영변경은없다. 코드롤백이필요하면후속의존/실행잠금을확인후메모리보완42dc2b1·후보3e0939a를역순으로일반git revert하고검증/push한다(문서충돌은검토). force/reset/과거snapshot일괄덮어쓰기/실험증거삭제없음. 후속계수/threshold/특징탐색0.

에튜 포인트: custom autograd는같은수식의순전파/역전파를직접구현한다. 이번에는8bag씩 X곱과X전치곱을계산해전체float64특징복제를피했다. 예를들어각묶음의Xᵀg를더하면전체선형곱의gradient가된다. 이수치일치를검증했지만실제AUC는하락해표현가설을채택하지않았다.

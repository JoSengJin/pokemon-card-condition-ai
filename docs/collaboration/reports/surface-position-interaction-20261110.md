# 위치 조건부 표현 단일 가설 결과 — 2026-11-10

개발 진척 **78/100(v1.13) 유지**. 위치 조건부1152차원 표현은 **α0 대비 AUC 하락·누락/오탐 증가로 가설 미지지, 운영 미채택**이다. 손실 가중치·대조군·성공 기준은 바꾸지 않았다. 메모리 전체 복제를 피한 계산은 검증했지만 성능 개선으로 이어지지 않았다.

## 실행과 고정 조건

- 검증/실행 소스: `efe63c34c5a5c9ce4191a3a7500417b6cc2dc3a3`. 계약 d22ab8d, 구현 efe63c3. 결과 문서 커밋과 실행 소스를 구분한다.
- 공통 기록: `artifacts/experiments/20261109T210729-0a9c06cc/record.json`, **completed/exit0**, 5fold 완료. KST2026-11-10 06:07:29→06:48:45. worker 경과2472.81초(41.21분), 순수 학습 시간이나 통제된 속도 비교가 아니다.
- 계획: `artifacts/surface-position-interaction-20261110/plan.json`, SHA256 `8928450f2a207afc0076bd16dc700a37c247491b9d1b741ea52900cc4a9f9aa7`.
- 명령: `PYTHONUNBUFFERED=1 CARD_CONDITION_AUTO_CHILD=1 ./experiment --plan artifacts/surface-position-interaction-20261110/plan.json -- .venv/bin/python artifacts/surface-position-interaction-20261110/worker.py`. 고유 console noclobber. 가설1개/공통실행1회/fold학습5회, 재시도·추가 가설·실험 밖 추가 학습/추론·자동review·Gemini/Codex API 호출0.
- 유일 과학 변수: 원본384D → `[x,u*x,v*x]`1152D. 기존3×3구역명의 열/행을 u/v=-1,0,+1로 고정한다. 같은 구역의 모든 유효 토큰에 같은 좌표를 적용하며 정답·점수·fold 통계로 좌표를 정하지 않는다. 원본384D 보존, invalid의 추가 성분0, 선형1152계수와 공유scalar bias. 구역별bias/threshold 추가0.
- 직접 α0 대조는 `20261108T215307-941b3aaa`(FN57/370,FP167/1406,AUC0.931924954826804). 원래 품질 reference는 `20261106T210640-0eb1bdc0`. 실패한 다른 표현으로 대조를 교체하지 않았다.
- N+D+G+L2,α0/정상bag1/결함bag1/L2=1/정상tau0.1/결함·출력max/sigmoid/threshold0.5/라벨/mask/1776행/5fold/seed20261031/CPU백본/zero초기값/group-classmass/center정의 고정. maxiter1000/maxeval1250(초기평가 포함),최종gradient1e-5/내부1e-7 유지. 표현 확장에 따른 계수 수와 L2 기하 변화는 입력 변경의 일부이며 별도 튜닝하지 않았다.

## 같은1776구역 성능

|대조|FN/370|누락률|FP/1406|오탐률|AUC|
|---|---:|---:|---:|---:|---:|
|원래 품질 대조|67|18.1081%|201|14.2959%|0.916650648|
|직접 α0 대조|57|15.4054%|167|11.8777%|0.931924955|
|위치 조건부 후보|88|23.7838%|169|12.0199%|0.909963093|

직접 α0 대비 **FN+31(+8.3784%p),FP+2(+0.1422%p),AUC−0.021961862**. paired photo-group bootstrap95% **[-0.031065732,-0.013991562]**(2000회/seed20261107). 차이와 구간이 음수로 이 고정 표현은 개발CV에서 악화됐다. 독립 일반화나 모든 위치 표현의 실패로 확대하지 않는다.

원래 품질 대조 대비 FN+21(+5.6757%p),FP−32(−2.2760%p),AUC−0.006687555,95%[-0.014939064,+0.001587706]. 이 구간은 직접 α0 비교의 구간과 다르며, 원래 대조보다 통계적으로 악화됐다고도 주장하지 않는다.

|사전 AND 기준|실측|판정|
|---|---|---|
|직접α0 AUC차>0·paired하한>0|차−0.021961862/하한−0.031065732|표현개선 미달|
|FN≤67/370|88|미달|
|FP≤112/1406|169|미달|
|원래 AUC 대비증가≥0.03|−0.006687555|미달|
|원래 대비paired95%하한>0|−0.014939064|미달|
|5fold 수렴·분리·근거 유효|모두 내부1e-7 도달|통과|

직접 α0 대비 신규누락38/누락회복7,신규오탐47/오탐회복45. 전체 ID와 구역별 보조 집계는 analysis.json,1776행 comparison.csv에 보존했다. 구역별 집계는 새 채택 기준이나 가중치 선택에 사용하지 않았다. 오류ID로 학습 선별·가중·라벨 수정0. 관찰 제한 누락/오탐은 미평가. 원라벨179/1597 보조 평가는 evaluation.json에 분리하며 확정정답370/1406과 혼합하지 않는다.

## 1152D 메모리 확인

`[x,u*x,v*x]` 전체를 저장하지 않고 `[x,u*valid,v*valid]`386채널을 저장한다. 학습에서는 float64 세384D 내적과 중심 보정을 사용하며 custom backward가 같은1152D gradient를 계산한다. 유효 토큰 평균을 쓰는 기존 center 정의는 그대로1152D에서 계산한다. 채점은8bag씩 명시적1152D float32를 잠시 만들어 기존 maskedmax/sigmoid 식을 유지한다.

|대상|크기|구분|
|---|---:|---|
|전체1152D float32 특징|7.8047GiB|산술상 크기, 전체 저장 안 함|
|전체1152D float64 특징|15.6094GiB|산술상 특징배열 크기, 전체 생성 안 함|
|실제386D float32 저장|2.6151GiB|전체1776행 compact 특징|
|학습 투영 기본float64 청크|24MiB|최대8×1024×384|
|center 구역별float64 임시확장|최대9MiB|전체 학습배열 확장 아님|
|채점float32 임시확장|최대36MiB|8bag씩|
|기록된 worker 최고 RSS|5.002838GiB(5371756544bytes)|특징 준비·5fold 학습/채점 완료시점까지의 프로세스 resident high-water|

물리RAM16GiB. 특징 준비와 각fold 종료의6개 sample 모두 high-water5371756544bytes였다. 별도 부트스트랩/worker종료직전 sample은 없어 이 범위를 넘는 전체종료 peak라고 주장하지 않는다. 전체배열 산술 크기와 프로세스 RSS는 다른 양이며 둘의 비율을 실측 절감률로 쓰지 않는다.

시스템 swap은 실험전4059.94MiB→종료후7490.44MiB(+3430.50MiB)로 증가했다. 다른 프로세스를 통제하지 않았고 worker별 swap을 측정하지 않아 이 worker로 귀속할 수 없다. RSS는 swap/가상메모리와 다르다. 따라서 메모리 부담0·swap없음·이전후보 대비 절감률을 주장하지 않는다. memory-preflight.json,공통record의memory-audit.json,postflight.json에 측정 범위와 수치를 보존했다.

## 합성 및 실행 검증

`.venv/bin/python tools/experiments/surface-position-interaction-20261110/checks.py` 통과:

- 9구역의 고정u/v,원본384D/mask 보존,정답·score 변경에 대한 표현 불변,알 수 없는 구역/비유한입력/잘못된mask 거절.
- 1/8/9/19bag에서 명시적dense1152D 대비 분해 계산의 최대 출력차9.99e-16,gradient차4.97e-14. 출력1e-12/gradient1e-10 허용오차로 검증했다.
- 전체loss·5개성분 gradient의dense 일치,상호작용 계수0일 때 기존384D 손실·원래계수/bias gradient 일치,18bag 합성1152D 학습/최종성분감사,원래float32 채점식과2e-6 이내 일치.
- 9×1024토큰 메모리 smoke에서 projection최대8행/3145728개384D원소를 확인했다. 실제 사진을 합성검사에 사용하지 않았다.
- AST 함수수 features3/position_linear2/objective3/worker0/checks1,각7이하. 학습bag경로 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss4전이,custom autograd경로도최대4전이. forward/backward 내부 분해는추가project함수호출없이계산. 채점경로 worker→score_position→expand_tokens2전이. 재귀/추가callback없음.

실제postflight 검증 통과:

- 공통record 파일SHA·동결입력229개·사진204장SHA·같은1776행/정답/사진group 분리.
- 5fold 학습행/mass/mask/target의α0 정확일치. position-contract.json의모든ID/area/u/v를기존GLARE_AREAS로재구성해일치,정답/점수사용false와추가구역bias0 확인.
- 유한1152계수+bias 모델5개,fit/component의최종thetaSHA 일치,gradient1153차원/성분합 일치. 산술rankloss/gradient는정확히0.
- 반복수156/166/201/161/160,평가수166/172/217/169/170. 최종gradient7.6240e-8/7.4889e-8/6.4169e-8/8.0402e-8/7.7256e-8. gradient성분합최대오차5.63e-16,loss성분합3.34e-16.
- 공통실행기 반환 뒤 development-cycle/latest.json의 별도20261024 ai_calls_forbidden pointer를 확인·보존했다. 이번record에development_handoff/token_report는 없으며 과거pointer를 이번채택 근거로 바꾸지 않았다.

## 변경·HTML·리스크·롤백

변경파일7개: 신규 `tools/experiments/surface-position-interaction-20261110/{features.py,position_linear.py,objective.py,worker.py,checks.py}` 5개와 task/이결과MD. 핵심diff는고정위치상호작용·386D압축저장/동치내적·1152D center/계수·메모리계측이다. 기존bag/rank수식·계수·optimizer는보존했다. 수정전기존소스는건드리지않고신규격리파일/runtime만추가,새파일만baseline=null로공통snapshot에등록했다. 기존모델/백본/라벨/데이터/기록/fallback변경0.

사진별HTML `artifacts/surface-position-interaction-20261110/report.html`은204장/1776구역의사람정답·α0/후보저장점수·출력·FNFP·분모/%p/AUC/CI와메모리범위를표시한다. HTML파싱/개수/경로/저장점수대조통과,CSV1776행. macOS open exit0. 이전file:콘텐츠관찰보안정책차단을존중해다른browser/서버/터널로우회하거나재시도하지않아 **실제render미확인**. 원본구역을사람결함점/모델peak로표시하지않았고외부업로드0.

리스크/미검증: 위치별결함빈도를학습했는지/추가용량으로과적합했는지/특정인쇄·반사가원인인지는분해검증하지않았다. 15선택사례에서정한가설을전체개발평가로검증했고그고정후보는기각됐다. 같은코딩의scale/새L2/좌표변형을뒤따라탐색하지않았다. 반복개발CV·부분재판정·단일seed이며독립일반화미확인. 관찰제한/통제속도·메모리비교/worker별swap미측정. 합성동치·수렴·메모리구현을모델개선으로혼동하지않는다. 고정진척78/100v1.13은유지한다.

운영미채택으로복원할운영변경은없다. 코드롤백필요시실행잠금/후속의존을확인후후보efe63c3을일반gitrevert하고관련검사/일반push한다. 문서상태는별도갱신하고force/reset/이전snapshot덮어쓰기/실험증거삭제없음. 비소유.claude/와다른세션worktree·브랜치·고유증거는보존,신규worktree없음.

에튜 포인트: 벡터를연결하는대신분배법칙으로같은계산을할수있다. `[x,u*x,v*x]`와1152계수의내적은`w0·x+u*(wu·x)+v*(wv·x)`다. 이번에는이식의출력과역전파동치를검증해큰배열복제를피했다. 계산동치는분류일반화개선을보장하지않아실제AUC가하락한후보는채택하지않았다.

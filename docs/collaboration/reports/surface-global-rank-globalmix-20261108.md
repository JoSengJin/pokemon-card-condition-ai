# 전체 학습쌍 LME 50% · 단일 실험 중단 결과 — 2026-11-08

개발 진척 **78/100(v1.13) 유지**. 목적함수1줄 변경과 합성검증은 완료했다. 실제 실험은1회 시작했으나 **실행 중단으로 후보 성능을 얻지 못했다**. 추가 재시도0, 운영 채택0.

## 실제 상태와 원인

- 검증 소스 SHA `70d7ac9f59f405e488e6baa9812be6c4d3ed6032`.
- 명령: `./experiment --plan artifacts/surface-global-rank-globalmix-20261108/plan.json -- .venv/bin/python artifacts/surface-global-rank-globalmix-20261108/worker.py`.
- `artifacts/experiments/20261108T002449-6e4ad830/record.json`: **status=interrupted, stage=execute, error_kind=orphaned_process, return_code=null, end_time_inferred=true**.
- 시작2026-11-08 09:24:49 KST. 고아상태 발견/기록시각09:28:17 KST이며 실제종료시각을 뜻하지 않는다.
- 마지막 관찰 stdout은 `feature_extraction / rows1776 / device=cpu`. 대기연결 중단 후 기존 unified exec세션은 Unknown process id였고, `ps -p 57813,57817 -o pid,ppid,etime,time,%cpu,state,command` 결과 부모·자식 모두 없음(exit1)을 확인했다.
- 공통기록의 `running` 잔존은 기존 `card_condition.experiment_record.records()`로 감독PID부재를 확인해 표준 interrupted/orphaned_process로 보정했다. 새 실험이나 새 모델 요청을 시작하지 않았다. `verify()`로 동결기록 파일 hash도 확인했다.
- 정확한 종료signal/종료코드/프로세스소멸 이유는 기록이 없어 **미확인**이다. 대화 대기중단 이후 프로세스 부재는 확인했지만 모델수렴 실패, gradient 문제, 평가한도초과로 단정하지 않는다.
- training-progress/training-diagnostics/fit-diagnostics/Armijo trace/checkpoint/models/observations/evaluation/result 파일이 없다. 완료fold0/5, 실제최적화 반복·평가횟수 미확인. 후보 FN/FP/AUC나 사전기준 판정을 만들어내지 않았다. 이미시작한실험을다시실행하지 않았다.

## 기존 모델 대비 결과

동일1776구역, 확정결함370·정상1406, 204사진그룹, threshold0.5. 기준은 `20261106T210640-0eb1bdc0` completed revised 모델이다. 이전후보 성공값으로 이번중단결과를 대체하지 않았다.

|지표|기존 모델(과거 저장평가)|이번 후보|변화|유지한 사전기준|판정|
|---|---:|---|---|---|---|
|누락률|67/370 =18.1081%|미측정|미측정|FN≤67|판정불가|
|오탐률|201/1406 =14.2959%|미측정|미측정|FP≤112|판정불가|
|AUC|0.916650648|미측정|미측정|기준대비+0.03이상|판정불가|
|AUC차 사진그룹bootstrap95%하한|—|미측정|미측정|하한>0|판정불가|
|실제수렴|—|진단없음|—|최종gradient≤1e-5|판정불가|

**전체 판정은 실행중단/판정불가**다. 합성 통과를 실제모델 수렴·성능통과로 대체하지 않는다. 반복개발CV이며 독립일반화 개선도 미확인이다.

## 변경 파일과 핵심 diff

신규 추적소스:

- `tools/experiments/surface-global-rank-globalmix-20261108/objective.py`
- 같은폴더 `worker.py`, `metrics.py`, `armijo_direction.py`, `checks.py`
- `docs/collaboration/tasks/surface-global-rank-globalmix-20261108.md`
- 이 보고서.

이전실험 소스/기록은 유지하고 새경로로 격리했다. `objective.py`는 직전 pairmix와 정확히 다음1줄만 다르다:

```diff
-lme=(torch.logsumexp(pair_loss,dim=1)-math.log(pair_loss.shape[1])).mean()
+lme=torch.logsumexp(pair_loss.reshape(-1),dim=0)-math.log(pair_loss.numel())
```

`loss=loss+.5*arithmetic+.5*lme` 그대로. worker는새가설ID만다르고 metrics/direction은바이트동일이다. 모든학습쌍·tau0.1 정상upperLSE·결함max·출력max/sigmoid·0.5threshold·사람정답·분할·기존bagloss/mass/L2/init/seed/특징백본·CPU환경을유지했다. optimizer의방향/Armijo/중복차단/상대곡률/정렬0.01도그대로다.

최종gradient≤1e-5(내부목표1e-7), fit당1,000반복/초기평가포함1,250평가 한도를 변경하지 않았다. 실제한도준수의완료검산은 실행중단으로 할수없다. 상한을늘리거나추가최종closure호출을넣지않았다.

## 실행한 검증

- `.venv/bin/python tools/experiments/surface-global-rank-globalmix-20261108/checks.py`: 통과. 독립적 `softplus(logmeanexp(normal_z)+logmeanexp(−defect_z))` 수식과실제 loss/autograd gradient 대조. 전쌍LME/50:50값·gradient·산술기여바닥·양축순열·동일쌍반복정규화·singleton·극단유한값확인.
- 계승검사통과: 실제합성fit수렴, 35step L-BFGS방향/history20, 엄격Armijo감소/진단계수, 동일파라미터차단,1250평가강제종료fixture,상대곡률,정렬재시작,normaltau0.1upperLSE/mask/결함hardmax.
- compile/AST통과: objective3 / direction1 / metrics4 / worker0 / checks3함수(파일당7이내). 기존 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss **4전이**,worker→fit→direction2전이. 새함수/callback/재귀없음.
- `checks.json`에검사및소스hash기록. 실행직전 CPU환경확인. 실행뒤 plan 입력SHA 전부불변, 모델/정답/분할수정0. 공통기록snapshot무결성검사통과.
- 독립시험·후보사진평가·새외부AI·재시도·기준완화0. 실제학습수렴검증과성능검증은미완료다.

## HTML·진척·인계

`artifacts/surface-global-rank-globalmix-20261108/report.html`: 중단상태/미측정표시, 기존204사진·1776사람구역과기준모델저장출력만표시한다. **이번후보점수/색상/정확도변화는없다**. 사진/구역수·참조경로존재·기준점수정렬을검사했다. 정답/기존출력을새모델추론으로표시하지않았다.

직전CUA file프로토콜정책거절을존중하며 현재CUA도제공되지않아 HTML열기/렌더는미실행이다. 다른경로우회/외부서버/업로드는사용하지않았다. 링크로로컬파일을제공한다.

PROGRESS_CRITERIA.md/development-progress.json v1.13의78/100을유지한다. 추가완료마일스톤이나운영품질개선없음. `artifacts/development-cycle/latest.json`은과거20261024handoff/ai_calls_forbidden을가리키며이번실험handoff는생성되지않았다. 과거handoff로이번실험을완료처리하지않았다.

## 리스크·롤백

전쌍LME가약한결함이상치를강조해오탐이나수렴을악화시킬수있다는가설리스크는실측되지않았다. 실제실행중단원인은OS수준로그가없어미확인이다. 합성수렴과모델수렴은별개다. 후보가없으므로운영채택하지않았다.

롤백: 신규격리소스커밋 `70d7ac9`와이번보고서/task커밋만revert해일반push. 기존모델/라벨/분할/운영소스는변경이없어복원불필요. 중단 record/동결plan/reference/snapshot/diff/검사증거는보존한다. `.claude/`는기존비소유항목으로건드리지않았다.

에튜 포인트: log-mean-exp의집계축을바꾸면어려운결함에도지수적가중치가걸린다. 수식/gradient합성통과는구현정확성을보일뿐, 중단된실험의누락률·오탐률·AUC를알려주지는않는다.

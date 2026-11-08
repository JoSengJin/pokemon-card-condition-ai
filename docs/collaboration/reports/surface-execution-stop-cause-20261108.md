# 실험 프로세스 종료 원인 추가 진단 — 2026-11-08

개발 진척 **78/100(v1.13) 유지**. 재실험·새추론·모델/실행기 수정0. 기존실험의종료원인을 **대화턴취소와연동된 unified exec 명령종료**로 더좁혔다. OS종료signal/발신주체까지확정한것은아니다.

## 새로 찾은 직접 근거

현재chat자체 실행로그의 좁은시간구간만조회했다. 원본전체/인증정보를복사하지않고필요한timestamp/status/PID만 `artifacts/surface-execution-stop-cause-20261108/timeline.json`에추출했다. 출처는 `rollout-2026-11-07T15-39-57-01a1b4bc-3b10-7783-acbf-c3fdf1b4eb1f.jsonl`이다(메모리 요약이 아닌 실제 실행 이벤트).

|KST시각|실제기록|출처line|
|---|---|---:|
|09:24:49.608|공통record 시작, supervisor57813 / worker57817|record.json|
|09:27:01.532|대기도구 `aborted by user after6.4s`|4180|
|09:27:01.575|`turn_aborted`, reason=`interrupted`|4183|
|09:27:01.584|실험명령 process_id10716이 `failed`, 도구 exit_code=`-1`로종료|4184|
|09:27:39.753|`write_stdin: Unknown process id10716`|4211|
|09:27:48.812|`ps`로 supervisor57813/worker57817 모두없음(exit1,헤더만)|4217|
|09:28:17.204|표준기록조회가 orphaned_process로보정|record.json|

턴취소와실험명령종료가 **9ms차이**로기록된다. 이사건은단순한화면관찰연결끊김만으로끝난것이아니라 실제실행명령의수명도끝난사건이다. 이것이이번에더확인한원인단서다. 다만 `-1`은도구CommandExecution의값이지 Python `subprocess.returncode`를수거한값이아니다. **SIGHUP/SIGKILL/SIGTERM으로변환해단정하지않는다.**

명령완료이벤트의누적출력은 `feature_extraction, rows1776, devicecpu`와 xFormers비가용경고3개뿐이다. Python traceback/학습완료/fold별수렴진단은없다. 실행명령에기록된duration은133.7607초지만 실제모델최적화시간이나기록복구시각과혼동하지않는다.

## 실행기 코드와 맞춘 해석

- `card_condition/experiment_record.py:279-283`: supervisor는SIGINT/SIGTERM을잡아KeyboardInterrupt로처리한다.
- 같은파일 `:287-291`: worker를 `start_new_session=True`로시작하고 `child.wait(timeout=timeout)`한다. stdout/stderr 인자를지정하지않아외부도구콘솔을그대로상속하며실험폴더콘솔파일은없다.
- `:301-305`: timeout이면time_budget, 정상수신SIGINT/SIGTERM이면signal을기록한다.
- `:308-324`: finally에서남은worker그룹에SIGTERM,5초후필요시SIGKILL을보내고 return_code/finished_at/record를저장한다.
- `:46-58`: records조회는감독PID가없어진running을 `interrupted/orphaned_process`로보정한다. 이는**사후발견분류**이며 실제kill주체나signal을뜻하지않는다.
- CLI `:330-340`은 `run(ROOT,plan,command)`만호출해 timeout인자를주지않는다. 이번직접CLI실험의 `_run` timeout은기본None이므로60초도구대기나1,250모델평가한도가 supervisor wallclock timeout으로동작한것은아니다.

정상Python예외/worker비정상종료를부모가수거했다면 child_exit/failed 또는 KeyboardInterrupt/signal과최종return_code가남아야한다. 실제record는종료후에도running/return_code=null이었고별도조회에서야보정됐다. 따라서 **감독 finally의종료저장까지정상완주하지못했다**는근거가강하다. 취소와동시에외부실행수명이끝나부모·자식모두종료된경로에부합한다. finally가왜실행되지못했는지(강제kill/호스트정리/기타치명오류)의최종OS수준경로는알수없다.

`start_new_session=True`는worker의OS세션/프로세스그룹을나누는설정이지, 외부실행호스트가취소해도계속살아남는보장이아니다. 이미있는이옵션을또추가하거나L-BFGS한도를늘려해결할문제가아니다.

## 다른 원인의 범위

|가설|근거에따른현재판단|
|---|---|
|대화실행취소에연동된외부명령종료|턴취소9ms뒤동일실험명령종료. 가장강한직접단서|
|정상SIGINT/SIGTERM처리완료|signal/return_code/최종record저장이없어해당정상경로와맞지않음|
|supervisor wallclock timeout|직접CLI는timeout=None; time_budget표시없음|
|L-BFGS수렴실패/1000회·1250평가초과|학습진단/Armijo로그/예외기록없음. 입증못함|
|Python예외/네이티브크래시|traceback/해당날Python진단보고서없음. 부재만으로완전배제못함|
|메모리압박/OOM/SIGKILL|해당PID/시간대macOS로그조회0건. 커널메모리종료를확정하거나완전배제할근거없음|
|xFormers경고|선택적가속미사용경고이며예외가아님. 종료원인이라는근거없음|

macOS `/usr/bin/log show`는09:24:40~09:28:20 KST, PID57813/57817문자열필터로조회했고exit0/이벤트0이었다. DiagnosticReports의해당날Python/메모리/Codex파일명도매칭0. 로그가비어있다는것을OOM미발생증명으로사용하지않는다.

## 다음 최소 보완안 — 제안만

**우선은모델/실행기패치보다 공통실험의 stdout/stderr를실험별로영속화하는실행설정한개를제안한다.** 기존Popen은출력FD를상속하므로부모와worker출력을동시에보존할수있다.

```sh
PYTHONUNBUFFERED=1 ./experiment --plan <동결계획.json> -- <기존worker명령>   > artifacts/<새작업ID>/console.log 2>&1
```

위는실행예시문자열이며이번에실행하지않았다. 기존worker의단계print/경고/예외/실행기종료출력을 로컬한파일에보존하고버퍼에남는양을줄이는목적이다. 원본사진·환경변수전체·API키는로그에추가하지않는다. 기록분류는기존 records복구를그대로쓴다. 동일실험재시도나프로세스자동재시작을넣지않는다.

이보완은 **증거유실을줄이는것이며외부취소를무력화하거나강제종료를막는기능은아니다**. 이사건에서취소없는독립실행수명이필요한지는실행호스트/운영방식에관한별도결정이다. 취소뒤몰래계속학습하는daemon/nohup전환은최소수정안에포함하지않는다. 새 signal-handler/finally를덧붙여도 SIGKILL이나호스트정리에대한보장은못한다.

유지/구조:

- 모델목적함수·전체쌍LME절반/산술절반·tau0.1·출력·라벨·분할·학습입력 그대로.
- 함수/호출층추가0. 모델의 worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss **4전이** 그대로. 새wrapper함수/콜백/백그라운드감독없음.
- 최종gradient≤1e-5(내부1e-7), fit당1000반복/초기포함1250평가. FN≤67/370·FP≤112/1406·AUC증가≥0.03·사진bootstrap하한>0 유지.
- 기존실행기파일은18개함수정의(기존상태)여서불필요한함수추가/구조확장을하지않는방향이다. 이번제안은그파일도수정하지않는다. 새실험worker는0함수정의다.

향후이실행설정을적용할때는합성부모·자식이stdout/stderr에쓴고정문구의파일존재, 정상종료/SIGTERM시 기존record상태, 중단뒤 새모델실행없음을검증하면된다. 이번에는테스트/실험을재실행하지않았다. 기존 `tests/test_experiment_record.py:335`의SIGTERM보존테스트와 `:294`의orphan복구테스트를코드로확인했을뿐이번통과라고보고하지않는다.

## 이번 변경·검증·롤백

- 이번신규변경은이보고서와 `docs/collaboration/tasks/surface-execution-stop-cause-20261108.md`뿐. 기존턴에서staged상태로남은단일실험중단보고서/task도함께정리하며그내용을이번실험으로표시하지않는다.
- Git제외 `artifacts/surface-execution-stop-cause-20261108/{timeline.json,report.html}`. 원본rollout전체/OS로그/사진은Git에넣지않는다.
- 실제검증은실행기/worker/테스트코드정적대조,실행이벤트시간대조,좁은OS로그/DiagnosticReports조회,원래record및소스hash확인,문서diff검사다. 모델추론/학습/합성실행/실험재시도0.
- 실제모델성능은여전히미측정이다. 원래단일실험의interrupted분류를완료나수렴실패로바꾸지않았다. 개발진척78/100유지.
- HTML은이번원인타임라인과근거/제안만표시한다. 현재CUA미제공및이전로컬file정책제한으로열기·렌더는미실행이며우회하지않는다.
- 리스크:로그영속화도강제종료직전버퍼/OS캐시자료까지보장하지않고정확한kill주체를자동증명하지않는다. 외부취소가다시발생하면학습도중단될수있다.
- 롤백:이번문서커밋만revert, ignored진단근거보존. 실행설정/모델/실행기코드는미수정이므로복원할실행동작없음.

에튜 포인트: `finally`는Python제어가돌아오는예외/일반signal에대해서만정리를할수있다. 외부호스트가실행수명을종료하면저장을못할수있어, 사전에로그를파일로흘리고사후orphan분류와구분하는것이중요하다.

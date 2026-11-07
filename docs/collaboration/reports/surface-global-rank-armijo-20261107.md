# L-BFGS 방향 유지 · Armijo 단일 실험과 실패 후 진단 보완

개발 진척 **78/100(v1.13) 유지**. 실제 실험은 첫 fold의 평가 예산 소진으로 실패했다. 추가 실제 실험 없이 진단 보완과 합성 검증만 수행했다.

## 실제 실험 결과

- 실행 소스: `7b19527` (실험 뒤 진단 보완과 구분).
- record: `artifacts/experiments/20261107T102832-b7c09a39/record.json`, `status=failed`, `error_kind=child_exit`.
- 벽시계 35.94분, CPU 특징 추출/학습 포함.
- 첫 fold 347회차, 실제 평가 **1250/1250**, 완료 fold **0/5**.
- 최종 채택 상태의 최대 gradient **0.0014649829686065874**, 기준1e-5의 **146.50배**. loss **0.5433133682506849**.
- 후보 OOF/observations/result/models가 없어 FN/FP/AUC를 산출하지 못했다.

|지표|기존 동결 모델|후보·변화|사전 기준|
|---|---|---|---|
|누락률|67/370 = 18.11%|산출 불가|FN<=67|
|오탐률|201/1406 = 14.30%|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|증가>=0.03 AND 사진그룹bootstrap95%하한>0|

실행·수렴 기준 미통과, 성능 기준 미평가. 실패를 성능0/악화로 해석하지 않는다. 독립 일반화 미확인.

## 로그로 확인한 실패 원인

trial1249개 중 채택346·거절903. 모든 trial 파라미터 SHA가 서로 다르며 중복 평가 차단 발생0이다. 따라서 이번 예산 소진은 동일 파라미터 재평가 탓이 아니다.

마지막 채택 step들(iter342/344/345/346)은 실제 loss 감소가 **1.1102230246251565e-16**, 즉 해당 loss의 float64 **1ULP**였다. 파라미터는 약1e-11씩 움직이고 활성 최대 패치가2~7구역 바뀌었다. loss는 극소 감소해도 gradient는 약0.001~0.003으로 남았다. 마지막 거절 trial들도 활성 패치7구역이 바뀌고 loss가 증가해 채택되지 않았다. 최대 패치 전환과 수렴 정체의 동반 발생은 확인했지만, 어느 구역/손실 항이 지배했는지와 인과는 아직 미확인이다.

로그를 차분형 Armijo 검사로 재검산했을 때, 채택346개 중 충분감소 부등식을 위반한 행은0이다. 단순히 합산형 bound 반올림으로 잘못 채택된 행이 원인이라는 근거는 없다. 작은 loss 감소를 gradient 수렴으로 바꾸지 않았으며 기존 gradient 검사는 그대로 거절했다.

## 구현과 구조 검증

신규 실험 소스:
- `worker.py`: 기존 입력/분할/대조군을 유지하고 직접 fitter 호출. optimizer monkeypatch 제거.
- `objective.py`: 평평한 학습 반복문, 동일 loss/gradient, Armijo c1=1e-4·step절반·엄격 감소, 동일 파라미터 차단, 정밀 trial 로그 및 평가 한도.
- `armijo_direction.py`: 설치 PyTorch와 같은 L-BFGS 두 루프·곡률 쌍 보관·history20·초기 step 공식.
- `metrics.py`: 기존 구현을 바이트 그대로 보존.
- `checks.py`: 합성 계약 검사. 실제 학습 실험이 아니다.

함수 수 objective3, direction1, metrics4, worker0, checks3으로 모두7이하. 변경된 프로젝트 호출 경로는 `worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss` **4전이**, `worker→fit→lbfgs_direction` **2전이**다. optimizer/추적 callback을 제거했고 다른 객체 callback으로 깊이를 숨기지 않았다. 텐서/자동미분 라이브러리 내부 구현을 프로젝트 호출 계층으로 재작성한 것은 아니다.

합성 검증: 설치 PyTorch와35단계 방향 일치(history20교체 포함), 기존 loss/gradient 일치, 작은 fixture 수렴, Armijo 엄격 감소, trial 로그 수=평가수-초기1, 동일 파라미터 차단,1250평가 한도 fixture 모두 통과. py_compile/함수수AST/git diff--check 통과. 실제 실험 소스 snapshot SHA/1776reference/FN67/FP201 검산. 총1249trial+초기1=1250 검산.

## 실패 후 보완 — 실제 재실험0

실패 원인에서 새로 필요한 증거만 추가했다. `objective.py`에 loss ULP·감소 ULP수·요구 감소량·bound 반올림 여부·활성 패치 전환 구역 인덱스를 기록하도록 보완했다. 마지막 채택 theta/center/gradient/active patch/L-BFGS state를 **실패 진단용 checkpoint**로 저장하도록 추가했다. 추가 loss 평가나 optimizer 동작 변경은 없다.

`checks.py`에서 새 로그 필드와1250평가 실패 fixture checkpoint를 읽어 검증했다. 전체 합성 검사를 다시 통과했다. 이 checkpoint 저장은 **실패 후 추가한 기능**이라 이번 실제 실패의 checkpoint를 소급 생성하지 않았다. 이번 실제 record/snapshot/trial 로그는 보존했고, 보완판의 실데이터 동작/수렴 개선은 미검증이다.

## 유지 조건·리스크·롤백

최종gradient<=1e-5/내부목표1e-7, 최대1000회/총평가1250회, 기존 손실·라벨·분할·mass·L2·영초기값·백본·seed·threshold0.5·성능 사전 기준을 유지했다. Armijo step 선택 변경 외의 모델 가설은 추가하지 않았다. 원본 labels/운영 모델/진척 기준/fallback 변경0.

Armijo가 loss를 줄이는 것과 raw gradient 수렴·모델 품질 개선은 다르다. 비매끄러운 최소점에서 raw gradient 기준이 충족될지는 미확인이고, 기준을 임의로 완화하지 않았다. 보완판은 증거 보존 개선이지 성능 개선이 아니다.

롤백은 이번 신규 소스·문서 커밋만 revert 후 일반push. 실제 실험 record/snapshot/trial 및 실패 진단은 보존한다. 운영 모델·라벨 복구는 필요 없다.

공통 실행기 반환 뒤 latest.json은 이전20261024 handoff를 계속 가리켰다. 이번 handoff/next_steps/token_report는 생성되지 않았으며 과거 기록으로 이번 실패를 대체하지 않았다. 추가 실제 재시도/독립 시험/전체 회귀/외부AI 호출0.

HTML: `artifacts/surface-global-rank-armijo-20261107/report.html`. 실제 실패 진단·사전 기준과 명시적으로 표시한 기존 대조군32사진 저장 출력. 후보 출력 없음. 열기·렌더 결과는 별도 기록한다.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.

# 상대 곡률 갱신 문턱 · 단일 실험 결과

개발 진척 **78/100(v1.13) 유지**. 곡률 갱신 중단은 해소됐으나 최종 gradient 기준을 만족하지 못해 실패했다. 추가 재시도0.

## 실제 실행 결과

- 검증 소스 `d7a19ea`.
- record: `artifacts/experiments/20261107T130918-738ab3ed/record.json`, status=failed, error_kind=child_exit.
- 벽시계 44.13분(CPU 특징 추출/학습 포함).
- 첫 fold **651회차 진입**, 채택 이동650회. **실제 평가1250/1250**, 최대 반복1000 유지.
- 종료 사유 **evaluation_budget**. 완료 fold0/5, observations/result/models/후보OOF 없음.
- 최종 채택 상태의 loss **0.5433133452462825**, 최대 gradient **0.001616523441034068**. 기존1e-5 기준의 **161.65배**.
- 실제 실패 checkpoint가 저장됐고 gradient·평가수·유한성 검산을 통과했다.

## 사전 성능 기준과 판정

|지표|기존 동결 모델|후보·변화|사전 기준|
|---|---|---|---|
|누락률|67/370 = 18.11%|산출 불가|FN<=67|
|오탐률|201/1406 = 14.30%|산출 불가|FP<=112|
|AUC|0.91665065|산출 불가|증가>=0.03 AND 사진그룹bootstrap95%하한>0|

실행·수렴 기준 미통과, 성능 기준 미평가. 실패를 모델성능0/악화로 해석하지 않는다. 독립 일반화 미확인. 학습 loss 감소를 정확도 개선으로 보고하지 않는다.

## 실제 곡률 로그로 확인한 원인

초기화 이후 곡률 검사650회 모두 갱신됐다. **288개는 s·y<=1e-10**으로 기존 절대 문턱 아래였지만 상대 문턱을 통과했다. 마지막100회도 모두 갱신했다. 따라서 이번 결과는 더 이상 곡률 메모리가 갱신되지 않아 멈춘 경우가 아니다. 절대 문턱 제거만으로 수렴할 것이라는 기대는 이번 결과에서 지지되지 않았다.

마지막 기록: s·y=4.494080996089325e-13, s_norm=4.065072149469965e-7, y_norm=0.005836370752550896, 상대 문턱2.028206104635643e-22, 갱신true, H_diag=1.3193352026741787e-8. 작아진 이동에서도 gradient 차이가 크게 남는 상태다. 전체 H_diag 범위7.580933354095515e-10~0.1499419303490781이며 유한했다. 이 변화가 원인이라는 인과는 아직 미확인이다.

trial1249개는 모두 서로 다른 파라미터이고 중복 차단0. 채택650·거절599. 채택625회에서 최대 패치가 바뀌었다. 마지막 채택 step=1에서도 최대 패치3구역이 바뀌며 gradient가0.00135558→0.00161652로 증가했다. 전체 채택 상태의 최소 gradient도0.0009422327838691652로 최종 수렴 기준의94.22배였다. 이는 곡률 갱신이 이어지는 상황에서도 패치 전환과 gradient 정체가 지속됐다는 근거이며, raw gradient 기준이 원리적으로 불가능하다는 증명은 아니다.

## 구현·검증

신규 `tools/experiments/surface-global-rank-relative-20261107/`:
- `armijo_direction.py`: 유일한 최적화 변수 변경. `s·y>1e-10` 대신 `finite(s·y) AND s·y>numel(y)*eps(dtype)*norm(y)*norm(s)` 적용.
- `objective.py`: 같은 계산에서 s·y,두norm,상대문턱,갱신여부,H_diag를 기록. 기존 ULP/패치 인덱스/실패 checkpoint 유지.
- `worker.py`: 새 가설ID/경로. 입력·라벨·대조군 동일.
- `metrics.py`: 기존 바이트 그대로 복사.
- `checks.py`: 기존 합성검사와 상대 문턱 경계검사.

함수 수 objective3/direction1/metrics4/worker0/checks3으로 각각7이하. `worker→fit→loss_and_grad→detail_bag_loss→point_bag_loss` **4전이**, `worker→fit→lbfgs_direction` **2전이** 유지. 새 callback/재귀 없음.

합성 검증 통과: 작은 양의 곡률 채택/음수·영벡터·거의직교·비유한값 거절/규모 변화 불변; 기존 loss·gradient 일치; smooth fixture의35방향 단계와 history20 교체 일치; 작은 fixture 수렴; Armijo 엄격 감소; 동일 파라미터 차단;1250평가 fixture; 정밀 로그/checkpoint. py_compile/AST함수수/diff-check 통과.

실제 검산: record의실행소스SHA 및plan의실제import소스·입력SHA 불변,1776reference/FN67/FP201 동일, trial1249+초기1=1250, checkpoint gradient/평가수 검산. 실제 성능 실험1회, 추가 재시도0. 전체회귀/독립시험/외부AI0.

## 조건 유지·리스크·롤백

최종gradient<=1e-5/내부목표1e-7, 최대1000회/총평가1250회, 기존 Armijo·중복 차단·loss·label·fold·mass·L2·영초기값·amax·백본·seed·threshold0.5 및 FN/FP/AUC기준 유지. 실제모델/fallback/원답/진척배점 수정0. 이번 상대 문턱은 수렴/품질 개선 근거가 없어 운영 채택하지 않는다.

리스크: 작은 곡률 쌍을 받아도 비매끄러운 목적의 raw gradient는 정체할 수 있다. H_diag 변화와 최적화 정체의 세부 인과는 미확인이다. 이번 실행 뒤 소스·기준 추가 변경/재시도 없음.

롤백은 신규 소스/문서 커밋만 revert후 일반push. record/snapshot/로그/checkpoint는 보존한다. 운영 모델·라벨 복구 불필요.

공통 실행기 반환 후 latest.json은 과거20261024 handoff를 계속 가리켰다. 이번 handoff/next_steps/token_report는 없으며 과거 기록으로 실패를 대체하지 않았다.

HTML `artifacts/surface-global-rank-relative-20261107/report.html`: 실제진단/사전기준과 명시적으로 표시한 기존대조군32사진 저장출력. 후보출력 없음. 열기·렌더 결과는 별도 기록한다.

HTML open exit0: 열기 요청 성공, 실제 렌더 미확인. git diff --check 통과.
